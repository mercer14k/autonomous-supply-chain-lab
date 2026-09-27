import os

import pytest
from fastapi.testclient import TestClient

from supply_lab.data.generator import generate
from supply_lab.services.api import create_app
from supply_lab.services.store import Base, Store


@pytest.fixture
def data():
    return generate(sku_count=12)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WRITE_TOKEN", "test-operator")
    monkeypatch.delenv("READ_TOKEN", raising=False)
    store = Store(os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/test.db")
    if os.getenv("TEST_DATABASE_URL"):
        if not store.engine.url.database.endswith("_test"):
            raise ValueError("TEST_DATABASE_URL must use a dedicated database ending in _test")
        Base.metadata.drop_all(store.engine)
    with TestClient(create_app(store)) as client:
        yield client
    store.engine.dispose()


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-operator", "Idempotency-Key": "test-command-001"}
