"""Daily lost-sales simulation. Currency uses integer cents; actions never mutate input state."""

import hashlib
import math
import random
from collections import defaultdict

from supply_lab.domain.models import Action, Dataset, EpisodeConfig, PurchaseOrder, State, key
from supply_lab.domain.policies import ShippingFacts, choose_tool

ENGINE_VERSION = "1.0"


def active_disruptions(data: Dataset, day: int):
    return [d for d in data.disruptions if d.start_day <= day < d.start_day + d.duration]


def initial_state(data: Dataset) -> State:
    inventory = {}
    for wh in data.warehouses:
        weight = sum(m.demand_weight for m in data.markets if m.warehouse_id == wh.id)
        remaining = wh.capacity
        for sku in data.skus:
            units = min(remaining, int((sku.daily_demand or 0) * weight * 12))
            inventory[key(sku.id, wh.id)] = units
            remaining -= units
    return State(inventory=inventory, initial_inventory=inventory.copy())


def forecast(data: Dataset, state: State) -> list[dict]:
    pipeline = defaultdict(int)
    for po in state.orders:
        if po.status == "in_transit":
            pipeline[key(po.sku_id, po.warehouse_id)] += po.quantity
    suppliers = {s.id: s for s in data.suppliers}
    plants = {p.id: p for p in data.plants}
    disruptions = active_disruptions(data, state.day)
    unavailable = {d.target_id for d in disruptions if d.kind in {"supplier_outage", "plant_outage"}}
    rows = []
    for wh in data.warehouses:
        weight = sum(m.demand_weight for m in data.markets if m.warehouse_id == wh.id)
        for sku in data.skus:
            k = key(sku.id, wh.id)
            history = state.demand_history.get(k, [])
            rate = (
                sum(history[-7:]) / len(history[-7:])
                if history
                else (sku.daily_demand * weight if sku.daily_demand is not None else None)
            )
            supplier = min(
                (suppliers[s] for s in sku.supplier_ids if s not in unavailable),
                key=lambda s: s.lead_days + (1 - s.reliability) * 5,
                default=None,
            )
            lead = (
                (supplier.lead_days if supplier else 30)
                + plants[sku.plant_id].processing_days
                + wh.transport_days
            )
            rows.append(
                {
                    "id": f"OBS-{state.day}-{k}",
                    "source_id": data.id,
                    "sku_id": sku.id,
                    "warehouse_id": wh.id,
                    "name": sku.name,
                    "category": sku.category,
                    "on_hand": state.inventory[k],
                    "pipeline": pipeline[k],
                    "daily_forecast": rate,
                    "days_cover": round(state.inventory[k] / rate, 2) if rate else None,
                    "inventory_position": state.inventory[k] + pipeline[k],
                    "lead_days": lead,
                    "supplier_id": supplier.id if supplier else None,
                    "plant_id": sku.plant_id,
                    "plant_available": sku.plant_id not in unavailable,
                    "unit_cost_cents": sku.unit_cost_cents,
                    "moq": sku.moq,
                    "forecast_basis": "observed trailing 7 days" if history else "synthetic prior",
                }
            )
    return rows


def propose(data: Dataset, state: State, policy: str) -> tuple[list[Action], list[dict]]:
    rows = forecast(data, state)
    actions = []
    for row in sorted(rows, key=lambda r: (r["days_cover"] if r["days_cover"] is not None else 1e9, r["id"])):
        rate = row["daily_forecast"]
        if not rate or not row["supplier_id"] or not row["plant_available"]:
            continue
        lead = row["lead_days"]
        if policy == "reorder_point":
            trigger, target = rate * (lead + 2), rate * (lead + 9)
        elif policy == "min_max":
            trigger, target = rate * 8, rate * 20
        else:
            trigger, target = rate * (lead + 4), rate * (lead + 12)
        if row["inventory_position"] >= trigger:
            continue
        quantity = min(10000, math.ceil((target - row["inventory_position"]) / row["moq"]) * row["moq"])
        shipping = choose_tool(
            ShippingFacts(
                evidence_available=True,
                need_replenishment=True,
                days_cover=row["days_cover"],
                lead_days=lead,
                pipeline_days=row["pipeline"] / rate,
            )
        )
        expedite = policy in {"heuristic", "agents"} and shipping == "expedite_order"
        actions.append(
            Action(
                tool="expedite_order" if expedite else "place_order",
                sku_id=row["sku_id"],
                warehouse_id=row["warehouse_id"],
                supplier_id=row["supplier_id"],
                quantity=quantity,
                evidence_ids=[row["id"], data.id],
            )
        )
    return actions, rows


def daily_demand(data: Dataset, config: EpisodeConfig, day: int, sku, market) -> int:
    # Independent keyed streams guarantee paired-policy demand, independent of action count/order.
    seed = hashlib.sha256(f"{data.id}:{config.seed}:{day}:{sku.id}:{market.id}".encode()).digest()
    rng = random.Random(int.from_bytes(seed[:8], "big"))
    multiplier = math.prod(
        d.magnitude
        for d in active_disruptions(data, day)
        if d.kind == "demand_surge" and d.target_id == market.id
    )
    mean = (
        sku.truth_daily_demand
        * market.demand_weight
        * multiplier
        * (1 + 0.15 * math.sin(day * 2 * math.pi / 7))
    )
    if mean == 0:
        return 0
    return max(0, round(rng.gauss(mean, math.sqrt(mean) * 0.65)))


def kpis(state: State, data: Dataset) -> dict:
    costs = {s.id: s.unit_cost_cents for s in data.skus}
    value = sum(q * costs[k.split("@")[0]] for k, q in state.inventory.items())
    pipeline_value = sum(p.quantity * p.unit_cost_cents for p in state.orders if p.status == "in_transit")
    total_cost = state.procurement_cents + state.transport_cents + state.holding_cents + state.shortage_cents
    average = state.inventory_value_days_cents / state.day if state.day else 0
    return {
        "day": state.day,
        "service_level": state.total_filled / state.total_demand if state.total_demand else None,
        "total_cost": total_cost / 100,
        "procurement_cost": state.procurement_cents / 100,
        "transport_cost": state.transport_cents / 100,
        "holding_cost": state.holding_cents / 100,
        "shortage_cost": state.shortage_cents / 100,
        "total_demand": state.total_demand,
        "total_filled": state.total_filled,
        "lost_units": state.total_demand - state.total_filled,
        "stockout_frequency": state.stockout_lines / state.demand_lines if state.demand_lines else None,
        "on_hand_units": sum(state.inventory.values()),
        "working_capital": (value + pipeline_value) / 100,
        "inventory_value": value / 100,
        "pipeline_value": pipeline_value / 100,
        "inventory_turns_annualized": state.fulfilled_cost_cents / average * 365 / state.day
        if average and state.day
        else None,
        "expedite_usage": state.expedite_units / state.ordered_units if state.ordered_units else 0,
        "open_orders": sum(p.status == "in_transit" for p in state.orders),
    }


def advance(
    data: Dataset, original: State, config: EpisodeConfig, actions: list[Action]
) -> tuple[State, dict]:
    if original.day >= config.days:
        raise ValueError("Episode is already complete")
    state = original.model_copy(deep=True)
    day = state.day
    disruptions = active_disruptions(data, day)
    suppliers = {s.id: s for s in data.suppliers}
    plants = {p.id: p for p in data.plants}
    warehouses = {w.id: w for w in data.warehouses}
    skus = {s.id: s for s in data.skus}
    unavailable = {d.target_id for d in disruptions if d.kind in {"supplier_outage", "plant_outage"}}
    before = state.inventory.copy()
    receipts = defaultdict(int)
    for po in state.orders:
        if po.status != "in_transit":
            continue
        for disruption in disruptions:
            if (
                disruption.kind == "transport_delay"
                and po.warehouse_id == disruption.target_id
                and disruption.id not in po.delays_applied
            ):
                po.due_day += int(disruption.magnitude)
                po.delays_applied.append(disruption.id)
        if po.due_day <= day:
            receipts[key(po.sku_id, po.warehouse_id)] += po.quantity
            state.inventory[key(po.sku_id, po.warehouse_id)] += po.quantity
            po.status = "received"
    used_supplier, used_plant, used_lane = defaultdict(int), defaultdict(int), defaultdict(int)
    occupancy = {
        w.id: sum(q for k, q in state.inventory.items() if k.endswith("@" + w.id)) for w in data.warehouses
    }
    for po in state.orders:
        if po.status == "in_transit":
            occupancy[po.warehouse_id] += po.quantity
    spent, seen = 0, set()
    outcomes = []
    evidence = {r["id"] for r in forecast(data, original)}
    for action in actions:
        sku, supplier, wh = (
            skus.get(action.sku_id),
            suppliers.get(action.supplier_id),
            warehouses.get(action.warehouse_id),
        )
        reason = None
        k = key(action.sku_id, action.warehouse_id)
        if not sku or not supplier or not wh or supplier.id not in sku.supplier_ids:
            reason = "Unknown or unsupported supply relationship"
        elif not set(action.evidence_ids) <= evidence | {data.id} or not set(action.evidence_ids) & evidence:
            reason = "Missing or stale observation evidence"
        elif f"OBS-{day}-{k}" not in action.evidence_ids:
            reason = "Evidence does not match the action inventory line"
        elif k in seen:
            reason = "Duplicate action: first priority wins"
        elif supplier.id in unavailable or sku.plant_id in unavailable:
            reason = "Supplier or plant is disrupted"
        elif action.quantity % sku.moq:
            reason = "Quantity violates minimum order multiple"
        if reason:
            outcomes.append(
                {
                    "action": action.model_dump(),
                    "status": "rejected",
                    "reason": reason,
                    "accepted_quantity": 0,
                }
            )
            continue
        seen.add(k)
        plant = plants[sku.plant_id]
        expedited = action.tool == "expedite_order"
        freight = 90 if expedited else 20
        capacity = min(
            action.quantity,
            supplier.daily_capacity - used_supplier[supplier.id],
            plant.daily_capacity - used_plant[plant.id],
            wh.lane_capacity - used_lane[wh.id],
            wh.capacity - occupancy[wh.id],
            (config.daily_budget_cents - spent) // (sku.unit_cost_cents + freight),
        )
        quantity = max(0, capacity // sku.moq * sku.moq)
        if not quantity:
            outcomes.append(
                {
                    "action": action.model_dump(),
                    "status": "deferred",
                    "reason": "Capacity or daily budget exhausted",
                    "accepted_quantity": 0,
                }
            )
            continue
        used_supplier[supplier.id] += quantity
        used_plant[plant.id] += quantity
        used_lane[wh.id] += quantity
        occupancy[wh.id] += quantity
        spent += quantity * (sku.unit_cost_cents + freight)
        lead = supplier.lead_days + plant.processing_days + wh.transport_days
        if expedited:
            lead = max(2, lead - 3)
        # Reliability delays are keyed to the order identity; never coupled to demand RNG.
        order_id = f"PO-{day:03}-{k}"
        draw = (
            int.from_bytes(hashlib.sha256(f"{config.seed}:{order_id}".encode()).digest()[:4], "big") / 2**32
        )
        lead += 2 if draw > supplier.reliability else 0
        state.orders.append(
            PurchaseOrder(
                id=order_id,
                source_id=data.id,
                ingested_at=f"simulation-day-{day}",
                lineage={"observation": f"OBS-{day}-{k}"},
                sku_id=sku.id,
                warehouse_id=wh.id,
                supplier_id=supplier.id,
                plant_id=plant.id,
                quantity=quantity,
                placed_day=day,
                due_day=day + lead,
                expedited=expedited,
                unit_cost_cents=sku.unit_cost_cents,
            )
        )
        state.procurement_cents += quantity * sku.unit_cost_cents
        state.transport_cents += quantity * freight
        state.ordered_units += quantity
        state.expedite_units += quantity if expedited else 0
        outcomes.append(
            {
                "action": action.model_dump(),
                "status": "accepted" if quantity == action.quantity else "partial",
                "reason": "Validated against evidence, budget and network capacity",
                "accepted_quantity": quantity,
                "order_id": order_id,
            }
        )
    demands, fills = defaultdict(int), defaultdict(int)
    market_totals = defaultdict(lambda: {"demand": 0, "filled": 0})
    # Rotate market priority daily to avoid permanently favouring the first market at a shared DC.
    markets = data.markets[day % len(data.markets) :] + data.markets[: day % len(data.markets)]
    for sku in data.skus:
        for market in markets:
            k = key(sku.id, market.warehouse_id)
            demand = daily_demand(data, config, day, sku, market)
            fill = min(demand, state.inventory[k])
            state.inventory[k] -= fill
            demands[k] += demand
            fills[k] += fill
            market_totals[market.id]["demand"] += demand
            market_totals[market.id]["filled"] += fill
            state.total_demand += demand
            state.total_filled += fill
            state.demand_lines += int(demand > 0)
            state.stockout_lines += int(fill < demand)
            state.shortage_cents += (demand - fill) * sku.unit_cost_cents * 2
            state.fulfilled_cost_cents += fill * sku.unit_cost_cents
    ledger = []
    inventory_value = 0
    for sku in data.skus:
        for wh in data.warehouses:
            k = key(sku.id, wh.id)
            state.demand_history.setdefault(k, []).append(demands[k])
            inventory_value += state.inventory[k] * sku.unit_cost_cents
            assert before[k] + receipts[k] - fills[k] == state.inventory[k] >= 0
            ledger.append(
                {
                    "id": f"LEDGER-{day}-{k}",
                    "source_id": data.id,
                    "day": day,
                    "sku_id": sku.id,
                    "warehouse_id": wh.id,
                    "opening": before[k],
                    "received": receipts[k],
                    "demand": demands[k],
                    "fulfilled": fills[k],
                    "lost": demands[k] - fills[k],
                    "closing": state.inventory[k],
                }
            )
    state.holding_cents += round(inventory_value * 0.0005)
    state.inventory_value_days_cents += inventory_value
    state.day += 1
    metric = kpis(state, data)
    metric["daily_demand"] = sum(demands.values())
    metric["daily_filled"] = sum(fills.values())
    state.metrics.append(metric)
    return state, {
        "day": day,
        "source_id": data.id,
        "engine_version": ENGINE_VERSION,
        "actions": [a.model_dump() for a in actions],
        "outcomes": outcomes,
        "ledger": ledger,
        "markets": dict(market_totals),
        "disruptions": [d.model_dump() for d in disruptions],
        "kpis": metric,
    }


def state_hash(state: State) -> str:
    import json

    return hashlib.sha256(
        json.dumps(state.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
