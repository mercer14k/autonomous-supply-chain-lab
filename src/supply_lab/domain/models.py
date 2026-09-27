from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Record(StrictModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    source_id: str = Field(min_length=1, max_length=100)
    ingested_at: str
    validation_status: Literal["valid", "warning"] = "valid"
    lineage: dict[str, str] = Field(default_factory=dict)


class Supplier(Record):
    name: str
    lead_days: int = Field(ge=1, le=30)
    daily_capacity: int = Field(ge=1)
    reliability: float = Field(ge=0, le=1)


class Plant(Record):
    name: str
    daily_capacity: int = Field(ge=1)
    processing_days: int = Field(ge=1, le=10)


class Warehouse(Record):
    name: str
    capacity: int = Field(ge=1)
    transport_days: int = Field(ge=1, le=15)
    lane_capacity: int = Field(ge=1)


class Market(Record):
    name: str
    warehouse_id: str
    demand_weight: float = Field(gt=0, le=10)


class SKU(Record):
    name: str
    category: str
    supplier_ids: list[str] = Field(min_length=1)
    plant_id: str
    unit_cost_cents: int = Field(ge=1)
    daily_demand: float | None = Field(default=None, ge=0, le=1000)
    truth_daily_demand: float = Field(ge=0, le=1000)
    moq: int = Field(ge=1, le=10000)


class Disruption(Record):
    kind: Literal["supplier_outage", "plant_outage", "transport_delay", "demand_surge"]
    target_id: str
    start_day: int = Field(ge=0)
    duration: int = Field(ge=1)
    magnitude: float = Field(ge=1, le=10)


class Dataset(Record):
    seed: int
    skus: list[SKU] = Field(min_length=1, max_length=5000)
    suppliers: list[Supplier] = Field(min_length=1, max_length=100)
    plants: list[Plant] = Field(min_length=1, max_length=50)
    warehouses: list[Warehouse] = Field(min_length=1, max_length=20)
    markets: list[Market] = Field(min_length=1, max_length=200)
    disruptions: list[Disruption] = Field(max_length=200)

    @model_validator(mode="after")
    def relationships(self):
        if len(self.skus) * len(self.markets) > 100_000:
            raise ValueError("Dataset exceeds 100,000 SKU-market demand lines per day")
        groups = [self.skus, self.suppliers, self.plants, self.warehouses, self.markets, self.disruptions]
        ids = [r.id for group in groups for r in group]
        if len(ids) != len(set(ids)):
            raise ValueError("Record identifiers must be globally unique")
        suppliers = {s.id for s in self.suppliers}
        plants = {p.id for p in self.plants}
        warehouses = {w.id for w in self.warehouses}
        markets = {m.id for m in self.markets}
        for s in self.skus:
            if not set(s.supplier_ids) <= suppliers or s.plant_id not in plants:
                raise ValueError(f"Unknown supply relationship for {s.id}")
        if any(m.warehouse_id not in warehouses for m in self.markets):
            raise ValueError("Unknown market warehouse")
        targets = {
            "supplier_outage": suppliers,
            "plant_outage": plants,
            "transport_delay": warehouses,
            "demand_surge": markets,
        }
        if any(d.target_id not in targets[d.kind] for d in self.disruptions):
            raise ValueError("Unknown disruption target")
        return self


class EpisodeConfig(StrictModel):
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
    days: int = Field(default=30, ge=1, le=365)
    policy: Literal["reorder_point", "min_max", "heuristic", "agents"] = "agents"
    mode: Literal["autonomous", "approval"] = "autonomous"
    runtime: Literal["none", "ollama", "llamacpp", "vllm"] = "none"
    model: str = Field(default="", max_length=150)
    daily_budget_cents: int = Field(default=10_000_000, ge=0, le=1_000_000_000)

    @model_validator(mode="after")
    def local_agents(self):
        if self.runtime != "none" and self.policy != "agents":
            raise ValueError("Local models require the agents policy")
        self.model = self.model.strip()
        if self.runtime != "none" and not self.model:
            raise ValueError("Choose an installed model ID for the selected local runtime")
        return self


class Action(StrictModel):
    tool: Literal["place_order", "expedite_order"]
    sku_id: str
    warehouse_id: str
    supplier_id: str
    quantity: int = Field(strict=True, ge=1, le=10000)
    evidence_ids: list[str] = Field(min_length=1, max_length=10)


class PurchaseOrder(Record):
    id: str = Field(min_length=1, max_length=250)
    sku_id: str
    warehouse_id: str
    supplier_id: str
    plant_id: str
    quantity: int
    placed_day: int
    due_day: int
    expedited: bool
    unit_cost_cents: int
    status: Literal["in_transit", "received"] = "in_transit"
    delays_applied: list[str] = Field(default_factory=list)


class State(StrictModel):
    day: int = 0
    inventory: dict[str, int]
    initial_inventory: dict[str, int]
    orders: list[PurchaseOrder] = Field(default_factory=list)
    demand_history: dict[str, list[int]] = Field(default_factory=dict)
    metrics: list[dict] = Field(default_factory=list)
    total_demand: int = 0
    total_filled: int = 0
    stockout_lines: int = 0
    demand_lines: int = 0
    procurement_cents: int = 0
    transport_cents: int = 0
    holding_cents: int = 0
    shortage_cents: int = 0
    fulfilled_cost_cents: int = 0
    inventory_value_days_cents: int = 0
    expedite_units: int = 0
    ordered_units: int = 0


def key(sku_id: str, warehouse_id: str) -> str:
    return f"{sku_id}@{warehouse_id}"
