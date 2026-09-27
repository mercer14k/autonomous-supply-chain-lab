from uuid import uuid4


def headers(auth):
    return {**auth, "Idempotency-Key": str(uuid4())}


def test_health_authorization_and_errors(client, auth):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
    assert client.post("/api/v1/episodes", json={}).status_code == 403
    assert client.get("/api/v1/episodes/missing").status_code == 404
    bad = client.post("/api/v1/episodes", headers=auth, json={"config": {"days": 0}})
    assert bad.status_code == 422 and bad.json()["error"]["trace_id"]
    assert client.get("/api/v1/episodes?limit=99999").status_code == 422


def test_episode_step_is_idempotent_and_replay_matches(client, auth):
    response = client.post("/api/v1/episodes", headers=auth, json={"config": {"days": 3}})
    assert response.status_code == 201, response.text
    ep = response.json()
    assert (
        client.post("/api/v1/episodes", headers=auth, json={"config": {"days": 3}}).json()["id"] == ep["id"]
    )
    conflict = client.post("/api/v1/episodes", headers=auth, json={"config": {"days": 4}})
    assert conflict.status_code == 409
    for day in range(1, 4):
        h = headers(auth)
        result = client.post(f"/api/v1/episodes/{ep['id']}/step", headers=h)
        assert result.status_code == 200, result.text
        assert result.json()["day"] == day
        assert client.post(f"/api/v1/episodes/{ep['id']}/step", headers=h).json()["day"] == day
    replay = client.get(f"/api/v1/episodes/{ep['id']}/replay").json()
    assert replay["verified"] and replay["days_replayed"] == 3
    assert client.post(f"/api/v1/episodes/{ep['id']}/step", headers=headers(auth)).status_code == 409
    exported = client.get(f"/api/v1/episodes/{ep['id']}/export")
    assert exported.status_code == 200 and len(exported.json()["frames"]) == 3


def test_approval_does_not_mutate_state_until_approved(client, auth):
    ep = client.post(
        "/api/v1/episodes", headers=headers(auth), json={"config": {"mode": "approval", "days": 2}}
    ).json()
    url = f"/api/v1/episodes/{ep['id']}"
    pending = client.post(url + "/step", headers=headers(auth)).json()
    assert pending["day"] == 0 and pending["status"] == "awaiting_approval"
    assert pending["kpis"] == ep["kpis"]
    assert client.post(url + "/step", headers=headers(auth)).status_code == 409
    result = client.post(url + "/approval", headers=headers(auth), json={"approve": True}).json()
    assert result["day"] == 1
    client.post(url + "/step", headers=headers(auth))
    result = client.post(url + "/approval", headers=headers(auth), json={"approve": False}).json()
    assert result["day"] == 2
    frame = client.get(url + "/frames/1").json()
    assert frame["approval"] == "rejected" and frame["actions"] == []
    assert client.get(url + "/replay").json()["verified"]


def test_ingestion_report_and_pagination(client, auth, data):
    response = client.post(
        "/api/v1/datasets/import",
        headers=auth,
        files={"file": ("../../evil.json", b"{bad", "application/json")},
    )
    assert response.status_code == 422
    report = response.json()["error"]["report"]
    assert report["filename"] == "evil.json"
    assert client.get("/api/v1/validation-reports/" + report["id"]).json()["errors"]
    valid = client.post(
        "/api/v1/datasets/import",
        headers=auth,
        files={"file": ("data.json", data.model_dump_json(), "application/json")},
    )
    assert valid.status_code == 201
    assert valid.json()["warnings"]
    assert (
        client.post(
            "/api/v1/datasets/import", headers=auth, files={"file": ("x.txt", b"x", "text/plain")}
        ).status_code
        == 415
    )
    ep = client.post("/api/v1/episodes", headers=headers(auth), json={}).json()
    inventory = client.get(f"/api/v1/episodes/{ep['id']}/inventory?limit=5&q=SKU-0001").json()
    assert inventory["total"] == 3 and len(inventory["items"]) == 3


def test_readonly_token_cannot_write(client, auth, monkeypatch):
    monkeypatch.setenv("READ_TOKEN", "readonly")
    assert client.get("/api/v1/datasets").status_code == 403
    reader = {"Authorization": "Bearer readonly"}
    assert client.get("/api/v1/datasets", headers=reader).status_code == 200
    assert (
        client.post(
            "/api/v1/episodes", headers={**reader, "Idempotency-Key": "unique-key-5"}, json={}
        ).status_code
        == 403
    )
