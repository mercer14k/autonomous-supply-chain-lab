import gzip
import json
from pathlib import Path

from supply_lab.ai.orchestrator import parse_actions
from supply_lab.domain.engine import ENGINE_VERSION, advance, initial_state, state_hash
from supply_lab.domain.models import Dataset, EpisodeConfig, State


def replay_archive(path: Path):
    # Only use archives from a trusted local source. Bound decompression to prevent archive bombs.
    with gzip.open(path, "rb") as file:
        raw = file.read(256 * 1024 * 1024 + 1)
    if len(raw) > 256 * 1024 * 1024:
        raise ValueError("Archive exceeds 256 MiB decompressed limit")
    archive = json.loads(raw)
    if archive["engine_version"] != ENGINE_VERSION:
        raise ValueError("Archive requires a different engine version")
    data = Dataset.model_validate(archive["dataset"])
    config = EpisodeConfig.model_validate(archive["config"])
    state = initial_state(data)
    matches = []
    for index, frame in enumerate(archive["frames"]):
        if frame["payload"]["day"] != index:
            raise ValueError("Missing or unordered archive frame")
        state, _ = advance(data, state, config, parse_actions(frame["payload"]))
        matches.append(state_hash(state) == frame["state_hash"])
    verified = all(matches) and state_hash(state) == state_hash(State.model_validate(archive["state"]))
    return {
        "verified": verified,
        "days_replayed": len(matches),
        "state_hash": state_hash(state),
        "model_called": False,
    }
