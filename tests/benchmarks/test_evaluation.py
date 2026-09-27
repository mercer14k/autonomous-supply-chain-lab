from supply_lab.evaluation.benchmark import run_episode, tool_accuracy


def test_harness_uses_identical_exogenous_demand_and_no_fabricated_model_metrics():
    first = run_episode(42, 3, 8, "heuristic")
    second = run_episode(42, 3, 8, "agents")
    assert first["state_hash"] == second["state_hash"]
    assert first["total_demand"] == second["total_demand"]
    assert second["tokens_per_model_decision"] is None
    assert second["agent_tool_selection_accuracy"] is None
    assert second["runtime_seconds"] > 0
    assert tool_accuracy()["accuracy"] == 1


def test_self_contained_benchmark_archive_replays_without_model(tmp_path):
    import gzip
    import json

    from supply_lab.evaluation.replay import replay_archive

    result = run_episode(73, 4, 12, "agents", archive_dir=tmp_path / "episodes")
    with gzip.open(tmp_path / result["episode_archive"], "rt") as file:
        assert json.load(file)["config"]["model"] == ""
    restored = replay_archive(tmp_path / result["episode_archive"])
    assert restored["verified"] and restored["days_replayed"] == 4
    assert restored["state_hash"] == result["state_hash"]
    assert not restored["model_called"]
