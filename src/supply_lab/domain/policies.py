from pydantic import Field

from supply_lab.domain.models import StrictModel


class ShippingFacts(StrictModel):
    evidence_available: bool
    need_replenishment: bool
    days_cover: float = Field(ge=0)
    lead_days: int = Field(ge=1)
    pipeline_days: float = Field(ge=0)


def choose_tool(facts: ShippingFacts) -> str:
    if not facts.evidence_available:
        return "abstain"
    if not facts.need_replenishment:
        return "no_action"
    if facts.days_cover < facts.lead_days / 2 and facts.pipeline_days < 3:
        return "expedite_order"
    return "place_order"
