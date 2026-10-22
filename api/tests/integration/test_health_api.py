import pytest
from fastapi.testclient import TestClient

from src.configs import config
from src.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_components(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"]["ok"] is True
    assert body["checkpointer"]["ok"] is True
    assert body["llm"]["configured"] is False
    assert body["tracing"] == {"enabled": False, "project": None}
    assert "x-request-id" in response.headers


def test_graph_ping_persists_count_per_thread(client):
    thread_id = "it-health-ping"
    first = client.post("/health/graph", json={"thread_id": thread_id}).json()
    second = client.post("/health/graph", json={"thread_id": thread_id}).json()
    assert second["count"] == first["count"] + 1
    assert second["reply"] == "pong"


def test_graph_ping_with_llm_requires_configured_model(client):
    response = client.post("/health/graph", json={"use_llm": True})
    assert response.status_code == 400
    assert response.json()["code"] == "LLM_NOT_CONFIGURED"


def test_debug_endpoints_hidden_when_debug_off(client, monkeypatch):
    monkeypatch.setattr(config, "debug", False)
    assert client.get("/health/llm").status_code == 404
    assert client.post("/health/graph", json={}).status_code == 404


def test_validation_errors_use_error_body(client):
    response = client.post("/health/graph", json={"thread_id": "bad id!"})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
