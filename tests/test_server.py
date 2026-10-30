"""test_server.py: Tests for FastAPI backend server."""
import json
from fastapi.testclient import TestClient
from server.main import app
from server.recognition import RecognitionError

client = TestClient(app)


def test_health_never_exposes_secrets():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["default_mode"] == "replay"
    assert data["upload_analysis_available"]
    assert data["inference_authentication_required"]
    assert data["inference_access"] == "per-user-session"
    assert "keys_configured" not in data


def test_store_endpoint():
    res = client.get("/api/store")
    assert res.status_code == 200
    data = res.json()
    assert data["store_name"] == "Straive Demo Bookstore"
    assert "bays" in data
    assert len(data["bays"]) >= 16


def test_scan_endpoint_f3():
    res = client.get("/api/scan/bay_f3")
    assert res.status_code == 200
    data = res.json()
    assert data["bay_id"] == "bay_f3"
    assert data["model"] == "Claude Opus 5.5"
    assert len(data["shelf_items"]) > 0
    assert len(data["planogram_items"]) > 0
    assert len(data["action_tasks"]) > 0


def test_scan_invalid_bay():
    res = client.get("/api/scan/bay_invalid_99")
    assert res.status_code == 404


def parse_events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_replay_stream_does_not_claim_live_model_or_verification():
    res = client.post("/api/scan/stream", json={"bay_id": "bay_a1", "mode": "replay"})
    assert res.status_code == 200
    events = parse_events(res)
    assert [e["status"] for e in events] == ["replay", "complete"]
    assert events[-1]["result"]["mode"] == "replay"
    assert events[-1]["result"]["model"] == "Gemini 3.8 Flash"
    assert not events[-1]["result"]["harness"]["rotated_verification"]


def test_live_requires_a_per_user_foundry_session():
    res = client.post("/api/scan/stream", json={"bay_id": "bay_f3", "mode": "live"})
    assert res.status_code == 401
    assert "Sign in" in res.json()["detail"]
    health = client.get("/api/health").json()
    assert health["live_mode_available"]
    assert all(health["live_available_by_difficulty"].values())


def test_legacy_personal_provider_keys_do_not_replace_per_user_sign_in(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("LLM_PROXY_TOKEN", "test-only")
    assert client.get("/api/health").json()["inference_authentication_required"]
    assert client.post("/api/scan/stream", json={"bay_id": "bay_f3", "mode": "live"}).status_code == 401


def test_scan_request_rejects_unknown_modes_models_and_paths():
    for payload in (
        {"bay_id": "../store", "mode": "replay"},
        {"bay_id": "bay_f3", "mode": "fake"},
        {"bay_id": "bay_f3", "model_id": "unmeasured-model"},
        {"bay_id": "bay_f3", "custom_image_b64": "different photo"},
    ):
        assert client.post("/api/scan/stream", json=payload).status_code == 422


def test_live_stream_runs_recognition_and_compares_actual_output(monkeypatch, tmp_path):
    monkeypatch.setattr("server.main.PHOTOS_DIR", tmp_path)
    (tmp_path / "f.jpg").write_bytes(b"test photo supplied to mocked recognition")
    calls = []
    async def recognize(raw, profile, emit, token):
        calls.append((raw, profile, token))
        await emit({"step": 1, "status": "reading", "message": "real work"})
        return [], {"mode": "live", "model": profile.name, "effort": "high"}
    monkeypatch.setattr("server.main.run_recognition", recognize)
    token = "transient-user-token"
    events = parse_events(client.post("/api/scan/stream", json={"bay_id": "bay_f3", "mode": "live"},
                                      headers={"Authorization": f"Bearer {token}"}))
    assert [e["status"] for e in events] == ["reading", "comparing", "complete"]
    result = events[-1]["result"]
    assert result["mode"] == "live"
    assert result["shelf_items"] == []
    assert result["metrics"]["matched_count"] == 0
    assert len(calls) == 1
    assert calls[0][1].model_id == "gemini-3.1-pro-preview"
    assert calls[0][2] == token
    assert token not in events[-1]["result"].values()


def test_streamed_failure_does_not_substitute_replay(monkeypatch):
    async def fail(raw, profile, emit, token):
        raise RecognitionError("Provider unavailable")
    monkeypatch.setattr("server.main.run_recognition", fail)
    events = parse_events(client.post("/api/scan/stream", json={"bay_id": "bay_f3", "mode": "live"},
                                      headers={"Authorization": "Bearer transient-token"}))
    assert events == [{"status": "error", "message": "Provider unavailable", "code": "inference"}]


def test_server_will_not_start_multiple_paid_scans(monkeypatch):
    class BusyLock:
        def locked(self):
            return True
    monkeypatch.setattr("server.main._live_scan_lock", BusyLock())
    res = client.post("/api/scan/stream", json={"bay_id": "bay_f3", "mode": "live"},
                      headers={"Authorization": "Bearer transient-token"})
    assert res.status_code == 409


def test_unknown_api_route_does_not_return_the_frontend():
    assert client.get("/api/nonexistent-route").status_code == 404
