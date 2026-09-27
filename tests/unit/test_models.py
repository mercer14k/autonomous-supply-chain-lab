import json

from supply_lab.data.validation import MAX_UPLOAD, validate_bytes


def test_validation_reports_all_or_nothing(data):
    raw = data.model_dump()
    raw["skus"][0]["unit_cost_cents"] = -1
    raw["skus"][1]["supplier_ids"] = ["unknown"]
    accepted, report = validate_bytes(json.dumps(raw).encode())
    assert accepted is None and not report["accepted"] and report["errors"]


def test_references_and_duplicate_ids(data):
    for edit in ["reference", "duplicate"]:
        raw = data.model_dump()
        if edit == "reference":
            raw["markets"][0]["warehouse_id"] = "invalid"
        else:
            raw["skus"][1]["id"] = raw["skus"][0]["id"]
        assert validate_bytes(json.dumps(raw).encode())[0] is None


def test_non_json_and_oversized_files_have_reports():
    assert validate_bytes(b"not json")[1]["errors"]
    assert validate_bytes(b" " * (MAX_UPLOAD + 1))[1]["errors"]


def test_nan_is_rejected(data):
    raw = data.model_dump()
    raw["skus"][2]["daily_demand"] = float("nan")
    assert validate_bytes(json.dumps(raw).encode())[0] is None


def test_inventory_key_separator_is_not_allowed_in_input_ids(data):
    raw = data.model_dump()
    raw["skus"][0]["id"] = "SKU@injected"
    assert validate_bytes(json.dumps(raw).encode())[0] is None
