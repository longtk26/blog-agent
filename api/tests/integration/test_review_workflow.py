import time
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

import src.main as main
from src.libs.database import run_in_session
from src.modules.articles.infrastructure.persistence import RevisionRepository
from src.modules.reviews.domain.approval_gate import ApprovalGate
from src.modules.reviews.infrastructure.persistence import ApprovalRepository
from src.modules.shared.domain.entities import PublicationTarget, TaskMode
from src.modules.shared.domain.value_objects import TaskStatus
from tests.conftest import TEST_DB_URL
from tests.fakes import FakeExtractor, FakeModelFactory, FakeSearchProvider, WritingScript
from tests.integration.workflow_harness import Harness


@pytest.fixture
def script():
    return WritingScript()


@pytest.fixture
def client(monkeypatch, script):
    monkeypatch.setattr(main, "get_model_factory", lambda: FakeModelFactory(script))
    monkeypatch.setattr(main, "get_search_provider", lambda: FakeSearchProvider())
    monkeypatch.setattr(main, "get_page_extractor", lambda: FakeExtractor())
    with TestClient(main.app) as test_client:
        yield test_client


def wait_idle(client, task_id, statuses, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/tasks/{task_id}").json()
        if body["status"] in statuses and not body["is_running"]:
            return body
        time.sleep(0.1)
    raise AssertionError(f"task stuck in {body['status']}")


def revisions(client, task_id):
    return client.get(f"/tasks/{task_id}/revisions").json()["items"]  # newest first


def revision(client, revision_id):
    return client.get(f"/revisions/{revision_id}").json()


def gate(revision_id, destination):
    return run_in_session(
        lambda s: ApprovalGate(ApprovalRepository(s), RevisionRepository(s)).check(uuid.UUID(revision_id), destination)
    )


def edit(client, task_id, base, markdown, **meta):
    metadata = {k: base[k] for k in ("title", "slug", "description", "tags")} | meta
    return client.post(
        f"/tasks/{task_id}/revisions", json={"base_revision_id": base["id"], "markdown": markdown, "metadata": metadata}
    )


def start_article(client):
    created = client.post("/tasks", json={"topic": "How LoRA fine-tuning works", "publication_targets": ["sanity", "devto"]})
    assert created.status_code == 201
    task_id = created.json()["id"]
    wait_idle(client, task_id, {"awaiting_review"})
    return task_id


def test_full_review_loop_over_http(client, script):
    task_id = start_article(client)
    r1 = revision(client, revisions(client, task_id)[0]["id"])
    assert r1["revision_number"] == 1 and r1["created_by"] == "ai"

    # --- E4-S3: owner edit -> new revision, deterministic checks only, workflow not resumed
    owner_md = r1["markdown"].replace("Fine-tuning large models is expensive.", "Fine-tuning big models costs a lot.")
    saved = edit(client, task_id, r1, owner_md)
    assert saved.status_code == 201, saved.text
    r2 = saved.json()
    assert r2["created_by"] == "owner" and r2["revision_number"] == 2 and r2["parent_revision_id"] == r1["id"]
    assert r2["metadata"]["sections_changed"] == ["Introduction"]
    assert [e["kind"] for e in r2["evaluations"]] == ["deterministic"]
    task = client.get(f"/tasks/{task_id}").json()
    assert task["status"] == "awaiting_review" and task["pending_interrupt"]["type"] == "awaiting_review"

    stale = edit(client, task_id, r1, owner_md + "\nMore.")
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_REVISION"
    assert edit(client, task_id, r2, r2["markdown"]).json()["code"] == "NO_CHANGES"
    bad_title = edit(client, task_id, r2, owner_md.replace("# LoRA", "# Other LoRA"))
    assert bad_title.status_code == 201
    assert any(i["rule"] == "META_TITLE" for i in bad_title.json()["evaluations"][0]["issues"])  # H1 != metadata title
    r2 = revision(client, revisions(client, task_id)[0]["id"])
    r2 = edit(client, task_id, r2, owner_md).json()  # back to a clean owner revision (r4)

    # --- E4-S5: scoped AI revision routed by the classifier (target=auto)
    stale_review = client.post(
        f"/tasks/{task_id}/review", json={"action": "revise", "revision_id": r1["id"], "feedback": "Explain QLoRA better"}
    )
    assert stale_review.json()["code"] == "STALE_REVISION"
    asked = client.post(
        f"/tasks/{task_id}/review",
        json={"action": "revise", "revision_id": r2["id"], "feedback": "Explain QLoRA memory savings more concretely"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["status"] == "revision_requested"
    wait_idle(client, task_id, {"awaiting_review"})
    assert script.route_calls == 1

    latest = revisions(client, task_id)[0]
    r_ai = revision(client, latest["id"])
    assert r_ai["created_by"] == "ai" and r_ai["parent_revision_id"] == r2["id"]
    assert latest["feedback"] == "Explain QLoRA memory savings more concretely"
    assert latest["review_target"] == "draft"
    assert latest["sections_changed"] == ["QLoRA Memory Savings"]  # owner's intro edit kept, other sections untouched
    assert latest["out_of_scope"] == []
    assert "Fine-tuning big models costs a lot." in r_ai["markdown"]
    assert r_ai["markdown"].count("(owner-requested)") == 1

    # --- E4-S6: approval bound to the exact hash, latest revision and destinations
    url = f"/revisions/{r_ai['id']}/approvals"
    wrong = client.post(url, json={"destinations": ["sanity"], "content_hash": "0" * 64})
    assert wrong.status_code == 409 and wrong.json()["code"] == "HASH_MISMATCH"
    old = client.post(f"/revisions/{r2['id']}/approvals", json={"destinations": ["sanity"], "content_hash": r2["content_hash"]})
    assert old.json()["code"] == "STALE_REVISION"
    approved = client.post(
        url, json={"destinations": ["sanity", "devto"], "content_hash": r_ai["content_hash"], "options": {"devto_mode": "draft"}}
    )
    assert approved.status_code == 201, approved.text
    rows = {a["destination"]: a for a in approved.json()["items"]}
    assert rows["sanity"]["content_hash"] == r_ai["content_hash"] and rows["devto"]["options"] == {"devto_mode": "draft"}
    task = wait_idle(client, task_id, {"approved"})
    assert task["pending_interrupt"]["type"] == "awaiting_publish"
    assert revisions(client, task_id)[0]["approved_for"] == ["devto", "sanity"]
    assert gate(r_ai["id"], PublicationTarget.SANITY).passed

    again = client.post(url, json={"destinations": ["sanity"], "content_hash": r_ai["content_hash"]})
    assert again.status_code == 409  # not awaiting review any more

    with psycopg.connect(TEST_DB_URL) as conn, pytest.raises(psycopg.errors.RaiseException, match="append-only"):
        conn.execute("UPDATE approvals SET content_hash = %s WHERE article_revision_id = %s", ("f" * 64, r_ai["id"]))

    # --- E4-S7: an edit after approval voids it and sends the thread back to review
    after = edit(client, task_id, r_ai, r_ai["markdown"].replace("costs a lot", "is costly"))
    assert after.status_code == 201
    task = wait_idle(client, task_id, {"awaiting_review"})
    assert task["pending_interrupt"]["type"] == "awaiting_review"
    approvals = client.get(f"/tasks/{task_id}/approvals").json()["items"]
    assert {a["decision"] for a in approvals} == {"superseded"}
    assert gate(r_ai["id"], PublicationTarget.SANITY).reason == "not_latest"
    assert gate(after.json()["id"], PublicationTarget.SANITY).reason == "not_approved"

    # --- metadata-only revision with an explicit target
    meta = client.post(
        f"/tasks/{task_id}/review",
        json={"action": "revise", "revision_id": after.json()["id"], "feedback": "Make the title friendlier",
              "scope": {"target": "metadata"}},
    )
    assert meta.status_code == 200
    wait_idle(client, task_id, {"awaiting_review"})
    latest = revisions(client, task_id)[0]
    assert latest["title"] == "LoRA Fine-Tuning, Explained Simply" and latest["sections_changed"] == ["Title"]
    assert script.route_calls == 1  # explicit target skips the classifier

    # --- E4-S8: reject ends the thread; the task is archived
    rejected = client.post(f"/tasks/{task_id}/review", json={"action": "reject", "reason": "Not this angle"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    wait_idle(client, task_id, {"rejected"})
    assert client.get(f"/tasks/{task_id}").json()["pending_interrupt"] is None  # thread reached END
    assert client.get("/tasks").json()["total"] == 0


def test_clone_reuses_sources(client):
    task_id = start_article(client)
    client.post(f"/tasks/{task_id}/review", json={"action": "reject"})
    original = client.get(f"/tasks/{task_id}/sources").json()["items"]
    usable = [s for s in original if s["status"] in ("assessed", "low_quality")]

    clone = client.post(
        "/tasks",
        json={"topic": "How LoRA fine-tuning works (take 2)", "mode": "research_only", "clone_from_task_id": task_id, "reuse_sources": True},
    )
    assert clone.status_code == 201, clone.text
    clone_id = clone.json()["id"]
    wait_idle(client, clone_id, {"completed"})
    copied = [s for s in client.get(f"/tasks/{clone_id}/sources").json()["items"] if s["round"] == 0]
    assert {s["canonical_url"] for s in copied} == {s["canonical_url"] for s in usable}

    missing = client.post("/tasks", json={"topic": "valid topic", "reuse_sources": True})
    assert missing.status_code == 400


def test_review_requires_waiting_state_and_round_cap(client, monkeypatch):
    task_id = start_article(client)
    latest = revisions(client, task_id)[0]
    bad = client.post(f"/tasks/{task_id}/review", json={"action": "revise", "revision_id": latest["id"]})
    assert bad.status_code == 422  # feedback is required

    monkeypatch.setattr(main.config, "max_review_rounds", 0)
    capped = client.post(
        f"/tasks/{task_id}/review", json={"action": "revise", "revision_id": latest["id"], "feedback": "More detail"}
    )
    assert capped.status_code == 409 and capped.json()["code"] == "REVIEW_ROUNDS_EXCEEDED"


def test_research_target_runs_follow_up_research(client):
    task_id = start_article(client)
    before = client.get(f"/tasks/{task_id}").json()["research_plan"]["questions"]
    latest = revisions(client, task_id)[0]
    asked = client.post(
        f"/tasks/{task_id}/review",
        json={"action": "revise", "revision_id": latest["id"], "feedback": "Add evidence about QLoRA GPU memory numbers",
              "scope": {"target": "research", "sections": ["2. QLoRA Memory Savings"]}},
    )
    assert asked.status_code == 200
    wait_idle(client, task_id, {"awaiting_review"})
    task = client.get(f"/tasks/{task_id}").json()
    assert len(task["research_plan"]["questions"]) > len(before)  # follow-up question appended
    newest = revisions(client, task_id)[0]
    assert newest["review_target"] == "research" and newest["sections_changed"] == ["QLoRA Memory Savings"]


async def test_lost_revision_request_is_handed_back(checkpointer):
    h = Harness(checkpointer)
    task_id = h.create_task(TaskMode.ARTICLE)
    await h.run(task_id)
    await h.store.transition(task_id, TaskStatus.REVISION_REQUESTED, reason="simulated")  # API died before resume

    await h.runner.recover()
    assert h.task(task_id).status == TaskStatus.AWAITING_REVIEW
    assert (await h.runner.pending_interrupt(str(task_id)))["type"] == "awaiting_review"
