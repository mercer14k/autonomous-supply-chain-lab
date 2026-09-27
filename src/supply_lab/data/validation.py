import hashlib
import json
from datetime import datetime, timezone

from pydantic import ValidationError

from supply_lab.domain.models import Dataset

MAX_UPLOAD = 10 * 1024 * 1024


def validate_bytes(raw: bytes) -> tuple[Dataset | None, dict]:
    report = {
        "source_id": hashlib.sha256(raw).hexdigest(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "accepted": False,
        "errors": [],
        "warnings": [],
        "record_count": 0,
    }
    if len(raw) > MAX_UPLOAD:
        report["errors"].append({"location": "file", "message": "Dataset exceeds 10 MiB"})
        return None, report
    try:
        dataset = Dataset.model_validate(json.loads(raw))
    except (ValueError, ValidationError, UnicodeError) as error:
        if isinstance(error, ValidationError):
            report["errors"] = [
                {"location": ".".join(map(str, e["loc"])), "message": e["msg"]}
                for e in error.errors(include_input=False)
            ][:100]
        else:
            report["errors"] = [{"location": "file", "message": "Malformed UTF-8 JSON"}]
        return None, report
    report["accepted"] = True
    report["dataset_id"] = dataset.id
    groups = [
        dataset.skus,
        dataset.suppliers,
        dataset.plants,
        dataset.warehouses,
        dataset.markets,
        dataset.disruptions,
    ]
    report["record_count"] = sum(len(g) for g in groups)
    for sku in dataset.skus:
        if sku.daily_demand is None:
            report["warnings"].append(
                {"record_id": sku.id, "message": "Missing initial forecast: abstain until history exists"}
            )
        elif sku.daily_demand == 0:
            report["warnings"].append(
                {"record_id": sku.id, "message": "Zero-demand item: no replenishment expected"}
            )
    return dataset, report
