import httpx
import pytest
from pydantic import ValidationError

from supply_lab.ai.adapters import LocalAdapter, list_local_models
from supply_lab.domain.models import EpisodeConfig


def test_model_choice_is_explicit_and_not_tied_to_a_family():
    assert EpisodeConfig().model == ""
    for runtime in ("ollama", "llamacpp", "vllm"):
        with pytest.raises(ValidationError, match="Choose an installed model"):
            EpisodeConfig(runtime=runtime)
        with pytest.raises(ValidationError, match="Choose an installed model"):
            EpisodeConfig(runtime=runtime, model="  ")
        config = EpisodeConfig(runtime=runtime, model=" research/solver-14b:custom-Q5 ")
        assert config.model == "research/solver-14b:custom-Q5"


@pytest.mark.parametrize(
    "runtime,path", [("ollama", "/api/tags"), ("llamacpp", "/v1/models"), ("vllm", "/v1/models")]
)
def test_catalog_lists_arbitrary_models_without_loading_them(runtime, path):
    def handler(request):
        assert request.method == "GET" and request.url.path == path
        if runtime == "ollama":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "research/model:Q5",
                            "details": {"parameter_size": "14B", "quantization_level": "Q5_K_M"},
                        },
                        {"model": "research/model:Q5"},
                        {"name": "hosted:cloud"},
                        {"name": "hosted:480b-cloud"},
                    ]
                },
            )
        return httpx.Response(200, json={"data": [{"id": "research/model:Q5"}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        catalog = list_local_models(runtime, client)
    assert catalog.available and [m.id for m in catalog.models] == ["research/model:Q5"]
    if runtime == "ollama":
        assert catalog.models[0].quantization == "Q5_K_M"


@pytest.mark.parametrize("body", [{"invalid": []}, {"models": "not a list"}, {"models": [None]}])
def test_invalid_discovery_is_visible_without_breaking_manual_selection(body):
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))) as client:
        catalog = list_local_models("ollama", client)
    assert not catalog.available and catalog.models == []
    assert "exact served model ID" in catalog.message


def test_offline_discovery_and_remote_url_remain_local(monkeypatch):
    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(offline)) as client:
        assert not list_local_models("ollama", client).available
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.com")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("Must not contact external runtime"))
    ) as client:
        assert not list_local_models("ollama", client).available
    with pytest.raises(ValueError, match="local"):
        LocalAdapter("ollama", "anything")


def test_cloud_suffix_is_rejected():
    with pytest.raises(ValueError, match="Cloud"):
        LocalAdapter("ollama", "hosted:480b-cloud")
