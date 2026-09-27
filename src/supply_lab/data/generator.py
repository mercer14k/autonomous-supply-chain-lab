"""Synthetic inputs: fixed IDs, provenance, latent ground truth and deliberate edge cases."""

import random

from supply_lab.domain.models import Dataset

EPOCH = "2026-01-01T00:00:00Z"


def generate(seed: int = 42, sku_count: int = 200) -> Dataset:
    rng = random.Random(seed)
    source = f"synthetic-v1-seed-{seed}-n-{sku_count}"

    def record(identifier, **fields):
        return dict(
            id=identifier,
            source_id=source,
            ingested_at=EPOCH,
            lineage={"generator": "1.0", "timestamp_basis": "fixed synthetic epoch"},
            **fields,
        )

    suppliers = [
        record(
            f"SUP-{i + 1:02}",
            name=name,
            lead_days=3 + i % 5,
            daily_capacity=max(800, sku_count * 18),
            reliability=round(0.86 + i * 0.015, 3),
        )
        for i, name in enumerate(
            [
                "Atlas Components",
                "Nord Materials",
                "Pacific Supply",
                "Keystone Works",
                "Summit Industrial",
                "Meridian Parts",
                "Delta Manufacturing",
                "Cedar Supply",
            ]
        )
    ]
    plants = [
        record(f"PLT-{i + 1:02}", name=name, daily_capacity=sku_count * 65, processing_days=1 + i)
        for i, name in enumerate(["Great Lakes Assembly", "Sunbelt Assembly"])
    ]
    warehouses = [
        record(
            f"WH-{i + 1:02}",
            name=name,
            capacity=sku_count * 500,
            transport_days=1 + i,
            lane_capacity=sku_count * 50,
        )
        for i, name in enumerate(["Chicago", "Dallas", "Newark"])
    ]
    cities = [
        "Minneapolis",
        "Detroit",
        "Cleveland",
        "St. Louis",
        "Austin",
        "Houston",
        "Denver",
        "Phoenix",
        "Boston",
        "New York",
        "Philadelphia",
        "Atlanta",
    ]
    markets = [
        record(
            f"MKT-{i + 1:02}",
            name=name,
            warehouse_id=f"WH-{i // 4 + 1:02}",
            demand_weight=round(rng.uniform(0.7, 1.3), 3),
        )
        for i, name in enumerate(cities)
    ]
    categories = ["Sensors", "Fasteners", "Controllers", "Power modules", "Connectors"]
    skus = []
    for i in range(sku_count):
        demand = round(rng.uniform(0.8, 3.2), 2)
        skus.append(
            record(
                f"SKU-{i + 1:04}",
                name=f"{categories[i % 5]} {1000 + i}",
                category=categories[i % 5],
                supplier_ids=[f"SUP-{i % 8 + 1:02}", f"SUP-{(i + 3) % 8 + 1:02}"],
                plant_id=f"PLT-{i % 2 + 1:02}",
                unit_cost_cents=rng.randrange(150, 3000, 25),
                daily_demand=demand,
                truth_daily_demand=demand,
                moq=[5, 10, 20][i % 3],
            )
        )
    skus[0].update(
        daily_demand=0,
        truth_daily_demand=0,
        validation_status="warning",
        lineage={"edge_case": "zero-demand discontinued item"},
    )
    if sku_count > 1:
        skus[1].update(
            daily_demand=None,
            validation_status="warning",
            lineage={"edge_case": "missing initial forecast; agents must abstain until observed"},
        )
    disruptions = [
        record("EVT-001", kind="supplier_outage", target_id="SUP-01", start_day=7, duration=5, magnitude=1),
        record("EVT-002", kind="demand_surge", target_id="MKT-10", start_day=12, duration=7, magnitude=2.5),
        record("EVT-003", kind="transport_delay", target_id="WH-02", start_day=18, duration=4, magnitude=3),
        record("EVT-004", kind="plant_outage", target_id="PLT-02", start_day=22, duration=3, magnitude=1),
    ]
    return Dataset(
        **record(
            source,
            seed=seed,
            skus=skus,
            suppliers=suppliers,
            plants=plants,
            warehouses=warehouses,
            markets=markets,
            disruptions=disruptions,
        )
    )
