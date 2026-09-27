from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from supply_lab.domain.models import EpisodeConfig
from supply_lab.services.store import Store


def test_concurrent_steps_never_lose_inventory_or_audit_updates(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/concurrent.db")
    store.initialize()
    episode = store.create(EpisodeConfig(days=3), None, str(uuid4()))

    def step(_):
        try:
            return store.step(episode["id"], str(uuid4()))
        except (StaleDataError, IntegrityError):
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(step, range(2)))
    successes = sum(r is not None for r in results)
    final = store.view(store.get_episode(episode["id"]))
    assert final["day"] == successes
    assert len(store.frames(episode["id"])) == successes
    assert store.replay(episode["id"])["verified"]
    store.engine.dispose()
