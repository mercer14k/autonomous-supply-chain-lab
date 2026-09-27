import csv
import gzip
import hashlib
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from supply_lab.ai.orchestrator import parse_actions, plan
from supply_lab.data.generator import generate
from supply_lab.domain.engine import ENGINE_VERSION, advance, initial_state, kpis, state_hash
from supply_lab.domain.models import EpisodeConfig
from supply_lab.domain.policies import ShippingFacts, choose_tool

GOLD_CASES = [
    {
        "evidence_available": False,
        "need_replenishment": True,
        "days_cover": 0,
        "lead_days": 8,
        "pipeline_days": 0,
        "expected": "abstain",
    },
    {
        "evidence_available": True,
        "need_replenishment": False,
        "days_cover": 30,
        "lead_days": 8,
        "pipeline_days": 0,
        "expected": "no_action",
    },
    {
        "evidence_available": True,
        "need_replenishment": True,
        "days_cover": 1,
        "lead_days": 8,
        "pipeline_days": 0,
        "expected": "expedite_order",
    },
    {
        "evidence_available": True,
        "need_replenishment": True,
        "days_cover": 7,
        "lead_days": 8,
        "pipeline_days": 0,
        "expected": "place_order",
    },
    {
        "evidence_available": True,
        "need_replenishment": True,
        "days_cover": 1,
        "lead_days": 8,
        "pipeline_days": 5,
        "expected": "place_order",
    },
    {
        "evidence_available": True,
        "need_replenishment": True,
        "days_cover": 4,
        "lead_days": 8,
        "pipeline_days": 0,
        "expected": "place_order",
    },
]


def tool_accuracy():
    correct = sum(
        choose_tool(ShippingFacts(**{k: v for k, v in case.items() if k != "expected"})) == case["expected"]
        for case in GOLD_CASES
    )
    return {
        "accuracy": correct / len(GOLD_CASES),
        "correct": correct,
        "total": len(GOLD_CASES),
        "scope": "deterministic shipping-tool routing fixtures, not LLM accuracy",
    }


def metadata():
    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "engine_version": ENGINE_VERSION,
        "timing_scope": "in-process simulation and planning, excludes database and HTTP",
        "currency": "USD modeled, integer cents internally",
    }


def run_episode(
    seed: int,
    days: int,
    sku_count: int,
    policy: str,
    runtime="none",
    model="",
    archive_dir: Path | None = None,
):
    data = generate(42, sku_count)
    config = EpisodeConfig(seed=seed, days=days, policy=policy, runtime=runtime, model=model)
    state = initial_state(data)
    latencies, tokens, attempts, failures, rejected, proposed, deferred = [], [], 0, 0, 0, 0, 0
    archived_frames = []
    start = time.perf_counter()
    for _ in range(days):
        proposal = plan(data, state, config)
        state, frame = advance(data, state, config, parse_actions(proposal))
        if archive_dir is not None:
            frame.update(
                decisions=proposal["decisions"],
                telemetry=proposal["telemetry"],
                approval="autonomous",
                source_id=data.id,
            )
            archived_frames.append({"payload": frame, "state_hash": state_hash(state)})
        t = proposal["telemetry"]
        latencies.append(t["latency_ms"])
        if t["tokens"] is not None:
            tokens.append(t["tokens"])
        attempts += t["model_attempts"]
        failures += len(t["validation_failures"])
        rejected += sum(o["status"] == "rejected" for o in frame["outcomes"])
        deferred += sum(o["status"] == "deferred" for o in frame["outcomes"])
        proposed += len(frame["outcomes"])
    result = {
        "policy": policy,
        "seed": seed,
        "days": days,
        "sku_count": sku_count,
        "dataset_id": data.id,
        "runtime": runtime,
        "model": model if runtime != "none" else None,
        **kpis(state, data),
        "runtime_seconds": round(time.perf_counter() - start, 4),
        "decision_latency_mean_ms": round(statistics.mean(latencies), 3),
        "decision_latency_p95_ms": sorted(latencies)[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "tokens_per_model_decision": statistics.mean(tokens) if tokens else None,
        "model_attempts": attempts,
        "model_failures": failures,
        "model_failure_rate": failures / attempts if attempts else None,
        "invalid_action_rate": rejected / proposed if proposed else 0,
        "deferred_actions": deferred,
        "agent_tool_selection_accuracy": None,
        "state_hash": state_hash(state),
    }
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        model_suffix = hashlib.sha256(model.encode()).hexdigest()[:8] if runtime != "none" else "none"
        filename = f"{policy}-{runtime}-{model_suffix}-seed-{seed}.json.gz"
        archive = {
            "engine_version": ENGINE_VERSION,
            "dataset": data.model_dump(),
            "config": config.model_dump(),
            "frames": archived_frames,
            "state": state.model_dump(),
            "result": result,
            "metadata": metadata(),
        }
        encoded = json.dumps(archive, separators=(",", ":")).encode()
        (archive_dir / filename).write_bytes(gzip.compress(encoded, mtime=0))
        result["episode_archive"] = "episodes/" + filename
    return result


def benchmark(output: Path, seeds=(42, 73, 101), days=30, sku_count=200, models=(), runtime="ollama"):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for policy in ["reorder_point", "min_max", "heuristic", "agents"]:
        for seed in seeds:
            rows.append(run_episode(seed, days, sku_count, policy, archive_dir=output / "episodes"))
    for model in models:
        for seed in seeds:
            rows.append(
                run_episode(seed, days, sku_count, "agents", runtime, model, archive_dir=output / "episodes")
            )
    report = {
        "metadata": metadata(),
        "methodology": {
            "seeds": list(seeds),
            "days": days,
            "sku_count": sku_count,
            "dataset_seed": 42,
            "paired_demand": True,
            "warmup_days": 0,
            "terminal_salvage": False,
            "agents_no_llm_equivalent_to_heuristic": True,
        },
        "tool_routing_fixtures": tool_accuracy(),
        "results": rows,
    }
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    with (output / "results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Measured benchmark results",
        "",
        f"Measured {report['metadata']['measured_at']} on {platform.system()} {platform.machine()}, Python {platform.python_version()}, {os.cpu_count()} logical CPUs.",
        "",
        f"{sku_count} SKUs; {days} days; paired seeds {list(seeds)}. Costs are modeled, not real operating savings.",
        "No-LLM agents deliberately share the heuristic policy. LLM accuracy is null without independently labeled model decisions.",
        "",
        "| Policy / runtime | Seed | Fill rate | Modeled cost | Lost units | Stockout lines | Working capital | Annual turns | Expedite | Mean plan ms | Run s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['policy']} / {r['model'] or 'none'} | {r['seed']} | {r['service_level']:.2%} | ${r['total_cost']:,.2f} | {r['lost_units']:,} | {r['stockout_frequency']:.2%} | ${r['working_capital']:,.0f} | {r['inventory_turns_annualized'] or 0:.2f} | {r['expedite_usage']:.2%} | {r['decision_latency_mean_ms']:.2f} | {r['runtime_seconds']:.2f} |"
        )
    lines += [
        "",
        "Timing excludes database and HTTP. See results.json for model failures, invalid actions, state hashes and configuration.",
        "Tool-routing fixture accuracy is a software correctness measure; it is not evidence of local-model intelligence.",
    ]
    (output / "summary.md").write_text("\n".join(lines) + "\n")
    return report
