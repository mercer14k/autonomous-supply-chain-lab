import argparse
import json
import time
import tracemalloc
from pathlib import Path
from uuid import uuid4

from supply_lab.data.generator import generate
from supply_lab.domain.models import Dataset, EpisodeConfig
from supply_lab.evaluation.benchmark import benchmark, metadata, run_episode
from supply_lab.evaluation.replay import replay_archive
from supply_lab.evaluation.tool_selection import evaluate_tools
from supply_lab.services.store import Store


def main():
    parser = argparse.ArgumentParser(description="Autonomous Supply Chain Lab reproducible workflows")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--skus", type=int, default=200)
    gen.add_argument("--output", type=Path, default=Path("data/sample/network.json"))
    bench = commands.add_parser("benchmark")
    bench.add_argument("--output", type=Path, default=Path("data/benchmarks"))
    bench.add_argument("--seeds", type=int, nargs="+", default=[42, 73, 101])
    bench.add_argument("--days", type=int, default=30)
    bench.add_argument("--skus", type=int, default=200)
    bench.add_argument("--models", nargs="*", default=[])
    bench.add_argument("--runtime", choices=["ollama", "llamacpp", "vllm"], default="ollama")
    perf = commands.add_parser("performance")
    perf.add_argument("--skus", type=int, default=1000)
    perf.add_argument("--days", type=int, default=10)
    perf.add_argument("--output", type=Path, default=Path("data/benchmarks/performance.json"))
    demo = commands.add_parser("demo")
    demo.add_argument("--days", type=int, default=10)
    replay = commands.add_parser("replay")
    replay.add_argument("episode_id")
    schema = commands.add_parser("schema")
    schema.add_argument("--output", type=Path, default=Path("data/schemas/network.schema.json"))
    tools = commands.add_parser("evaluate-tools")
    tools.add_argument("--models", nargs="+", required=True)
    tools.add_argument("--runtime", choices=["ollama", "llamacpp", "vllm"], default="ollama")
    tools.add_argument("--output", type=Path, default=Path("data/benchmarks/tool-selection.json"))
    archive = commands.add_parser("replay-file")
    archive.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "replay-file":
        report = replay_archive(args.path)
        print(json.dumps(report, indent=2))
        if not report["verified"]:
            raise SystemExit(1)
    elif args.command == "evaluate-tools":
        report = evaluate_tools(args.output, args.runtime, args.models)
        print(
            json.dumps(
                {"results": [{"model": r["model"], "accuracy": r["accuracy"]} for r in report["results"]]}
            )
        )
    elif args.command == "generate":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(generate(args.seed, args.skus).model_dump_json(indent=2) + "\n")
        print(f"Generated {args.skus} SKUs: {args.output}")
    elif args.command == "schema":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(Dataset.model_json_schema(), indent=2) + "\n")
    elif args.command == "benchmark":
        report = benchmark(args.output, args.seeds, args.days, args.skus, args.models, args.runtime)
        print(f"Measured {len(report['results'])} episodes. Results: {args.output}/summary.md")
    elif args.command == "performance":
        tracemalloc.start()
        start = time.perf_counter()
        result = run_episode(42, args.days, args.skus, "heuristic")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        output = {
            "metadata": metadata(),
            "result": result,
            "wall_seconds_with_tracemalloc": time.perf_counter() - start,
            "peak_python_allocated_bytes": peak,
            "memory_scope": "tracemalloc Python allocations, not process RSS",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n")
        print(f"Performance report: {args.output}")
    elif args.command == "demo":
        store = Store()
        store.initialize()
        episode = store.create(EpisodeConfig(days=max(30, args.days)), None, str(uuid4()))
        for _ in range(args.days):
            episode = store.step(episode["id"], str(uuid4()))
        print(
            json.dumps(
                {"episode_id": episode["id"], "day": episode["day"], "kpis": episode["kpis"]}, indent=2
            )
        )
    elif args.command == "replay":
        result = Store().replay(args.episode_id)
        print(json.dumps(result, indent=2))
        if not result["verified"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
