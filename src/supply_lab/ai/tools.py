"""Strict specialist capability boundary; no arbitrary code, SQL, or tool lookup."""

from typing import Literal

from pydantic import Field, model_validator

from supply_lab.domain.models import StrictModel

Role = Literal["demand", "inventory", "supplier_risk", "procurement", "logistics", "incident_response"]
Tool = Literal[
    "forecast_demand",
    "inspect_inventory",
    "assess_supplier_risk",
    "propose_orders",
    "select_shipping",
    "assess_incidents",
]
TOOLS = {
    "demand": "forecast_demand",
    "inventory": "inspect_inventory",
    "supplier_risk": "assess_supplier_risk",
    "procurement": "propose_orders",
    "logistics": "select_shipping",
    "incident_response": "assess_incidents",
}


class ToolCall(StrictModel):
    agent: Role
    tool: Tool
    day: int = Field(ge=0)
    source_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def capability(self):
        if TOOLS[self.agent] != self.tool:
            raise ValueError("Tool is not allowed for this specialist")
        return self


class ToolResult(StrictModel):
    call: ToolCall
    status: Literal["completed", "abstained"]
    evidence_ids: list[str]
    summary: dict


def dispatch(call: ToolCall, observations: list[dict], actions: list, disruptions: list) -> ToolResult:
    """Read-only specialist tools, operating on engine observations, not raw model text."""
    missing = [r["id"] for r in observations if r["daily_forecast"] is None]
    if call.tool == "forecast_demand":
        summary = {
            "forecast_units": round(sum(r["daily_forecast"] or 0 for r in observations), 2),
            "missing_evidence": missing,
        }
    elif call.tool == "inspect_inventory":
        summary = {
            "reviewed_lines": len(observations),
            "at_risk_lines": sum(
                bool(r["daily_forecast"]) and r["days_cover"] < r["lead_days"] for r in observations
            ),
        }
    elif call.tool == "assess_supplier_risk":
        summary = {"unavailable_suppliers": [d.target_id for d in disruptions if d.kind == "supplier_outage"]}
    elif call.tool == "propose_orders":
        summary = {"proposed_orders": len(actions), "proposed_units": sum(a.quantity for a in actions)}
    elif call.tool == "select_shipping":
        summary = {"expedite_candidates": sum(a.tool == "expedite_order" for a in actions)}
    else:
        summary = {"active_incidents": [d.id for d in disruptions]}
    return ToolResult(
        call=call,
        status="abstained" if call.agent == "demand" and missing else "completed",
        evidence_ids=call.source_ids + [d.id for d in disruptions],
        summary=summary,
    )
