import httpx
import pytest

from supply_lab.ai.adapters import LocalAdapter, ModelReply, Selection
from supply_lab.ai.orchestrator import plan
from supply_lab.domain.engine import initial_state, state_hash
from supply_lab.domain.models import EpisodeConfig


class BrokenAdapter:
    def decide(self, _):
        raise TimeoutError("offline")


class HallucinatingAdapter:
    def decide(self, _):
        return ModelReply(
            Selection(candidate_ids=["run-shell"], evidence_ids=["invented"], abstain=False, rationale="bad"),
            30,
            "fake-test-model",
        )


class GoodAdapter:
    def decide(self, evidence):
        first = next(iter(evidence["candidates"]))
        return ModelReply(
            Selection(
                candidate_ids=[first],
                evidence_ids=evidence["available_evidence_ids"],
                abstain=False,
                rationale="Uses observed stock evidence.",
            ),
            30,
            "test-model",
        )


@pytest.mark.parametrize("adapter", [BrokenAdapter(), HallucinatingAdapter()])
def test_llm_failure_never_mutates_state_and_records_fallback(data, adapter):
    state = initial_state(data)
    state.inventory = {k: 0 for k in state.inventory}
    before = state_hash(state)
    deterministic = plan(data, state, EpisodeConfig())
    actual = plan(data, state, EpisodeConfig(runtime="ollama", model="research/model:custom"), adapter)
    assert actual["actions"] == deterministic["actions"]
    assert actual["telemetry"]["fallback"]
    assert actual["telemetry"]["validation_failures"]
    assert state_hash(state) == before


def test_valid_model_uses_only_typed_catalog_actions(data):
    state = initial_state(data)
    state.inventory = {k: 0 for k in state.inventory}
    result = plan(data, state, EpisodeConfig(runtime="ollama", model="research/model:custom"), GoodAdapter())
    assert not result["telemetry"]["fallback"]
    assert result["telemetry"]["tokens"] == 30
    assert result["decisions"][-1]["kind"] == "ai_narrative"


def test_runtime_blocks_remote_urls(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://example.com")
    with pytest.raises(ValueError, match="local"):
        LocalAdapter("ollama", "any")


@pytest.mark.parametrize("runtime", ["ollama", "llamacpp", "vllm"])
def test_local_adapter_protocol_contract(runtime):
    selection = {"candidate_ids": [], "evidence_ids": [], "abstain": True, "rationale": "Evidence missing."}
    import json

    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "research/solver:custom-quant"
        assert body["messages"][0]["role"] == "system"
        if runtime == "ollama":
            assert request.url.path == "/api/chat" and body["format"]["type"] == "object"
            return httpx.Response(
                200,
                json={
                    "model": "test",
                    "message": {"content": json.dumps(selection), "thinking": "never-store-this"},
                    "prompt_eval_count": 5,
                    "eval_count": 7,
                },
            )
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(
            200,
            json={
                "model": "test",
                "choices": [{"message": {"content": json.dumps(selection)}}],
                "usage": {"total_tokens": 12},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        reply = LocalAdapter(runtime, "research/solver:custom-quant", client).decide({})
    assert reply.tokens == 12 and reply.selection.abstain
    assert "thinking" not in reply.__dict__


def test_cloud_tag_is_not_a_local_model():
    with pytest.raises(ValueError, match="Cloud"):
        LocalAdapter("ollama", "example:cloud")
