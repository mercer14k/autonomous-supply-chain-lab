import time

from supply_lab.ai.adapters import PROMPT_VERSION, LocalAdapter
from supply_lab.ai.tools import TOOLS, ToolCall, dispatch
from supply_lab.domain.engine import active_disruptions, propose
from supply_lab.domain.models import Action, Dataset, EpisodeConfig, State


def plan(data: Dataset, state: State, config: EpisodeConfig, adapter=None) -> dict:
    start = time.perf_counter()
    actions, rows = propose(data, state, config.policy)
    missing = [r["id"] for r in rows if r["daily_forecast"] is None]
    active = active_disruptions(data, state.day)
    telemetry = {
        "runtime": config.runtime,
        "model": config.model if config.runtime != "none" else None,
        "prompt_version": PROMPT_VERSION,
        "temperature": 0,
        "max_output_tokens": 1024,
        "context_tokens": 8192 if config.runtime == "ollama" else None,
        "seed": 42,
        "retries": 0,
        "validation_failures": [],
        "tokens": None,
        "model_attempts": 0,
        "fallback": False,
    }
    decisions = []
    if config.policy == "agents":
        for role, tool in TOOLS.items():
            call = ToolCall(agent=role, tool=tool, day=state.day, source_ids=[data.id])
            result = dispatch(call, rows, actions, active)
            decisions.append(
                {
                    "id": f"DEC-{state.day}-{role}",
                    "agent": role,
                    "tool": tool,
                    "kind": "computed",
                    "evidence_ids": result.evidence_ids,
                    "summary": result.summary,
                    "status": result.status,
                    "tool_call": call.model_dump(),
                }
            )
    if config.runtime != "none" and actions:
        # Bound local inference to 12 highest-priority lines per day. Remaining lines retain the documented heuristic.
        focus, rest = actions[:12], actions[12:]
        catalog = {}
        for i, action in enumerate(focus):
            catalog[f"C{i}-standard"] = action.model_copy(update={"tool": "place_order"})
            catalog[f"C{i}-expedite"] = action.model_copy(update={"tool": "expedite_order"})
        allowed_evidence = {e for a in focus for e in a.evidence_ids}
        context = {
            "day": state.day,
            "candidates": {k: v.model_dump() for k, v in catalog.items()},
            "observations": [r for r in rows if r["id"] in allowed_evidence],
            "available_evidence_ids": sorted(allowed_evidence),
        }
        telemetry["model_attempts"] = 1
        try:
            adapter = adapter or LocalAdapter(config.runtime, config.model)
            reply = adapter.decide(context)
            selection = reply.selection
            telemetry["tokens"], telemetry["resolved_model"] = reply.tokens, reply.model
            if not set(selection.evidence_ids) <= allowed_evidence:
                raise ValueError("Model cited unknown evidence")
            if selection.abstain and selection.candidate_ids:
                raise ValueError("Abstention cannot select actions")
            if any(c not in catalog for c in selection.candidate_ids):
                raise ValueError("Model selected an unknown tool candidate")
            chosen = [catalog[c] for c in selection.candidate_ids]
            if len({(a.sku_id, a.warehouse_id) for a in chosen}) != len(chosen):
                raise ValueError("Model selected conflicting candidates")
            if any(not set(a.evidence_ids) <= set(selection.evidence_ids) for a in chosen):
                raise ValueError("Model omitted required supporting evidence")
            actions = chosen + rest
            decisions.append(
                {
                    "id": f"DEC-{state.day}-model",
                    "agent": "procurement",
                    "tool": "select_candidates",
                    "kind": "ai_narrative",
                    "evidence_ids": selection.evidence_ids,
                    "summary": {"rationale": selection.rationale, "selected": selection.candidate_ids},
                    "status": "abstained" if selection.abstain else "completed",
                }
            )
        except Exception as error:
            # Fail closed for inference, retain the deterministic safe policy. No business state has changed.
            telemetry["fallback"] = True
            telemetry["validation_failures"].append(type(error).__name__)
            decisions.append(
                {
                    "id": f"DEC-{state.day}-fallback",
                    "agent": "procurement",
                    "tool": "deterministic_fallback",
                    "kind": "computed",
                    "evidence_ids": [data.id],
                    "status": "fallback",
                    "summary": {
                        "reason": "Local model unavailable or invalid output; validated heuristic used"
                    },
                }
            )
    telemetry["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return {
        "day": state.day,
        "actions": [a.model_dump() for a in actions],
        "decisions": decisions,
        "telemetry": telemetry,
        "missing_evidence": missing,
    }


def parse_actions(plan_data: dict) -> list[Action]:
    return [Action.model_validate(a) for a in plan_data["actions"]]
