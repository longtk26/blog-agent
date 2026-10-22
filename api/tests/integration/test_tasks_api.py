import time

import pytest
from fastapi.testclient import TestClient

import src.main as main
from tests.fakes import FakeExtractor, FakeModelFactory, FakeSearchProvider, research_responder


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "get_model_factory", lambda: FakeModelFactory(research_responder))
    monkeypatch.setattr(main, "get_search_provider", lambda: FakeSearchProvider())
    monkeypatch.setattr(main, "get_page_extractor", lambda: FakeExtractor())
    with TestClient(main.app) as test_client:
        yield test_client


def wait_for_status(client, task_id, statuses, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/tasks/{task_id}").json()
        if body["status"] in statuses and not body["is_running"]:
            return body
        time.sleep(0.1)
    raise AssertionError(f"task stuck in {body['status']}")


def test_research_only_lifecycle_over_http(client):
    created = client.post(
        "/tasks",
        json={
            "topic": "  How LoRA fine-tuning works  ",
            "mode": "research_only",
            "audience": "software engineers new to fine-tuning",
            "publication_targets": ["sanity", "sanity"],
            "budgets": {"max_sources": 10},
        },
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["topic"] == "How LoRA fine-tuning works"
    assert task["publication_targets"] == ["sanity"]
    assert task["budgets"]["max_sources"] == 10

    done = wait_for_status(client, task["id"], {"completed"})
    assert done["progress"]["sources_found"] == 4
    assert done["open_questions"]

    sources = client.get(f"/tasks/{task['id']}/sources").json()
    assert sources["total"] == 4
    assert sources["items"][0]["quality_score"] >= sources["items"][-1]["quality_score"]
    assert any(claim["quote_verified"] for item in sources["items"] for claim in item["claims"])
    assert "content_text" not in sources["items"][0]

    brief = client.get(f"/tasks/{task['id']}/research-brief").json()
    assert brief["markdown"].startswith("# Research brief")

    listing = client.get("/tasks", params={"status": "completed"}).json()
    assert [item["id"] for item in listing["items"]] == [task["id"]]

    # SSE replays the full history and ends because the task is at rest
    with client.stream("GET", f"/tasks/{task['id']}/events") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        body = "".join(stream.iter_text())
    assert '"type":"plan_ready"' in body
    assert "event: end" in body
    last_id = max(int(line[4:]) for line in body.splitlines() if line.startswith("id: "))
    with client.stream("GET", f"/tasks/{task['id']}/events", headers={"Last-Event-ID": str(last_id)}) as stream:
        tail = "".join(stream.iter_text())
    assert "id: " not in tail and "event: end" in tail

    promoted = client.post(f"/tasks/{task['id']}/promote", json={"angle": "LoRA from first principles"})
    assert promoted.status_code == 200, promoted.text
    final = wait_for_status(client, task["id"], {"outlining"})
    assert final["mode"] == "article" and final["angle"] == "LoRA from first principles"

    again = client.post(f"/tasks/{task['id']}/promote", json={})
    assert again.status_code == 400 and again.json()["code"] == "INVALID_TRANSITION"

    cancelled = client.post(f"/tasks/{task['id']}/cancel", json={})
    assert cancelled.json()["status"] == "rejected"
    assert client.get("/tasks").json()["total"] == 0  # rejected tasks are archived by default
    assert client.get("/tasks", params={"archived": True}).json()["total"] == 1


def test_validation_and_errors(client):
    assert client.post("/tasks", json={"topic": "hi"}).json()["code"] == "VALIDATION_ERROR"
    assert client.post("/tasks", json={"topic": "valid topic", "unknown": 1}).status_code == 422
    too_many = client.post("/tasks", json={"topic": "valid topic", "budgets": {"max_sources": 10_000}})
    assert too_many.status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/tasks/{missing}").status_code == 404
    assert client.get(f"/tasks/{missing}/events").status_code == 404
    assert client.get(f"/tasks/{missing}/sources").status_code == 404
    assert client.post(f"/tasks/{missing}/retry", json={}).status_code == 404
    assert client.get("/tasks/not-a-uuid").status_code == 422


def test_retry_rejects_non_failed_task(client):
    task = client.post("/tasks", json={"topic": "How LoRA fine-tuning works", "mode": "research_only"}).json()
    wait_for_status(client, task["id"], {"completed"})
    response = client.post(f"/tasks/{task['id']}/retry", json={})
    assert response.status_code == 400 and response.json()["code"] == "INVALID_TRANSITION"
