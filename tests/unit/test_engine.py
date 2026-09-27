from collections import defaultdict

import pytest
from pydantic import ValidationError

from supply_lab.ai.orchestrator import parse_actions, plan
from supply_lab.data.generator import generate
from supply_lab.domain.engine import advance, daily_demand, forecast, initial_state, kpis, propose, state_hash
from supply_lab.domain.models import Action, EpisodeConfig, key


def test_generator_is_reproducible_and_has_required_network():
    first, second = generate(), generate()
    assert first.model_dump() == second.model_dump()
    assert [
        len(first.skus),
        len(first.suppliers),
        len(first.plants),
        len(first.warehouses),
        len(first.markets),
    ] == [200, 8, 2, 3, 12]
    assert all(s.source_id == first.id for s in first.skus)


def test_hand_calculated_cost_and_balance(data):
    data = data.model_copy(deep=True)
    data.skus = [data.skus[2]]
    data.markets = [data.markets[0]]
    data.warehouses = [data.warehouses[0]]
    state = initial_state(data)
    sku, wh = data.skus[0], data.warehouses[0]
    k = key(sku.id, wh.id)
    state.inventory[k] = 0
    config = EpisodeConfig(days=1)
    expected = daily_demand(data, config, 0, sku, data.markets[0])
    updated, frame = advance(data, state, config, [])
    assert updated.total_demand == expected
    assert updated.total_filled == 0
    assert updated.shortage_cents == expected * sku.unit_cost_cents * 2
    assert updated.holding_cents == 0
    assert frame["ledger"][0]["closing"] == 0
    assert state.day == 0


@pytest.mark.parametrize("policy", ["reorder_point", "min_max", "heuristic", "agents"])
def test_conservation_reproducibility_capacities_and_cost(data, policy):
    config = EpisodeConfig(days=30, policy=policy)
    state = initial_state(data)
    for _ in range(config.days):
        actions, _ = propose(data, state, policy)
        prior_hash = state_hash(state)
        updated, frame = advance(data, state, config, actions)
        assert state_hash(state) == prior_hash
        repeated, _ = advance(data, state, config, actions)
        assert state_hash(updated) == state_hash(repeated)
        assert all(
            r["opening"] + r["received"] - r["fulfilled"] == r["closing"] >= 0 for r in frame["ledger"]
        )
        assert sum(o["accepted_quantity"] for o in frame["outcomes"]) == sum(
            p.quantity for p in updated.orders if p.placed_day == state.day
        )
        for wh in data.warehouses:
            occupancy = sum(v for k, v in updated.inventory.items() if k.endswith("@" + wh.id))
            occupancy += sum(
                p.quantity for p in updated.orders if p.warehouse_id == wh.id and p.status == "in_transit"
            )
            assert occupancy <= wh.capacity
        by_supplier, by_plant, by_lane = defaultdict(int), defaultdict(int), defaultdict(int)
        spend = 0
        for po in updated.orders:
            if po.placed_day == state.day:
                by_supplier[po.supplier_id] += po.quantity
                by_plant[po.plant_id] += po.quantity
                by_lane[po.warehouse_id] += po.quantity
                spend += po.quantity * (po.unit_cost_cents + (90 if po.expedited else 20))
        assert spend <= config.daily_budget_cents
        assert all(by_supplier[s.id] <= s.daily_capacity for s in data.suppliers)
        assert all(by_plant[p.id] <= p.daily_capacity for p in data.plants)
        assert all(by_lane[w.id] <= w.lane_capacity for w in data.warehouses)
        state = updated
    assert state.total_filled <= state.total_demand
    assert not any(po.sku_id == "SKU-0001" for po in state.orders)
    metric = kpis(state, data)
    assert (
        metric["total_cost"]
        == metric["procurement_cost"]
        + metric["transport_cost"]
        + metric["holding_cost"]
        + metric["shortage_cost"]
    )


def test_no_lookahead_and_missing_evidence_abstention(data):
    initial = initial_state(data)
    proposal = plan(data, initial, EpisodeConfig())
    assert len(proposal["decisions"]) == 6
    assert len(proposal["missing_evidence"]) == 3
    assert not any(a["sku_id"] == "SKU-0002" for a in proposal["actions"])
    future = data.model_copy(deep=True)
    for event in future.disruptions:
        event.magnitude = 9
    assert propose(data, initial, "agents") == propose(future, initial, "agents")
    next_state, _ = advance(data, initial, EpisodeConfig(), [])
    assert all(r["daily_forecast"] is not None for r in forecast(data, next_state))


def test_paired_demand_is_independent_of_policy(data):
    totals = []
    for policy in ["reorder_point", "min_max", "heuristic"]:
        state = initial_state(data)
        config = EpisodeConfig(days=8, policy=policy)
        for _ in range(8):
            actions, _ = propose(data, state, policy)
            state, _ = advance(data, state, config, actions)
        totals.append(state.total_demand)
    assert len(set(totals)) == 1


def test_invalid_stale_and_duplicate_actions_are_rejected(data):
    state = initial_state(data)
    state.inventory = {k: 0 for k in state.inventory}
    actions, _ = propose(data, state, "heuristic")
    assert actions
    bad = actions[0].model_copy(update={"evidence_ids": ["made-up"]})
    _, frame = advance(data, state, EpisodeConfig(), [bad, actions[0], actions[0]])
    assert [o["status"] for o in frame["outcomes"]] == ["rejected", "accepted", "rejected"]


def test_budget_zero_defers_all_orders(data):
    state = initial_state(data)
    state.inventory = {k: 0 for k in state.inventory}
    actions, _ = propose(data, state, "heuristic")
    updated, frame = advance(data, state, EpisodeConfig(daily_budget_cents=0), actions)
    assert not updated.orders
    assert all(o["status"] == "deferred" for o in frame["outcomes"])


def test_action_schema_disallows_arbitrary_tools_and_float_quantity():
    with pytest.raises(ValidationError):
        Action(
            tool="execute_sql", sku_id="a", warehouse_id="b", supplier_id="c", quantity=5, evidence_ids=["x"]
        )
    with pytest.raises(ValidationError):
        Action(
            tool="place_order",
            sku_id="a",
            warehouse_id="b",
            supplier_id="c",
            quantity=5.0,
            evidence_ids=["x"],
        )


def test_transport_delay_applied_once(data):
    state = initial_state(data)
    state.day = 17
    state.inventory = {k: 0 for k in state.inventory}
    config = EpisodeConfig(days=30)
    actions, _ = propose(data, state, "heuristic")
    state, _ = advance(data, state, config, actions)
    matching = [p for p in state.orders if p.warehouse_id == "WH-02"]
    assert matching
    old = {p.id: p.due_day for p in matching}
    state, _ = advance(data, state, config, [])
    for p in state.orders:
        if p.id in old:
            assert p.due_day == old[p.id] + 3
    state, _ = advance(data, state, config, [])
    assert all(p.due_day == old[p.id] + 3 for p in state.orders if p.id in old)


def test_negative_quantity_cannot_be_parsed():
    with pytest.raises(ValidationError):
        parse_actions(
            {
                "actions": [
                    {
                        "tool": "place_order",
                        "sku_id": "a",
                        "warehouse_id": "b",
                        "supplier_id": "c",
                        "quantity": -1,
                        "evidence_ids": ["x"],
                    }
                ]
            }
        )
