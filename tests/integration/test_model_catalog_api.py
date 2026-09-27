from supply_lab.ai.adapters import InstalledModel, ModelCatalog


def test_catalog_schema_auth_and_model_selection(client, monkeypatch, auth):
    monkeypatch.setattr(
        "supply_lab.services.api.list_local_models",
        lambda runtime: ModelCatalog(
            runtime=runtime,
            available=True,
            models=[InstalledModel(id="research/model:custom")],
            message="Local models available",
        ),
    )
    response = client.get("/api/v1/models?runtime=ollama")
    assert response.status_code == 200 and response.json()["models"][0]["id"] == "research/model:custom"
    assert client.get("/api/v1/models?runtime=external").status_code == 422
    assert (
        client.post("/api/v1/episodes", headers=auth, json={"config": {"runtime": "ollama"}}).status_code
        == 422
    )
    created = client.post(
        "/api/v1/episodes",
        headers=auth,
        json={"config": {"runtime": "ollama", "model": "research/model:custom"}},
    )
    assert created.status_code == 201
    assert created.json()["config"]["model"] == "research/model:custom"
    monkeypatch.setenv("READ_TOKEN", "reader-secret")
    assert client.get("/api/v1/models?runtime=ollama").status_code == 403
    assert (
        client.get(
            "/api/v1/models?runtime=ollama", headers={"Authorization": "Bearer reader-secret"}
        ).status_code
        == 200
    )
