import hashlib
import time
import uuid

import pytest
from fastapi.testclient import TestClient

import src.main as main
from src.modules.publishing.infrastructure.adapters import PublisherRegistry, SanityPublisher
from src.modules.publishing.ports.output.publisher import IPublisher, PublishOutcome
from src.modules.shared.domain.entities import ArticleRevisionEntity, PublicationTarget
from src.modules.shared.domain.value_objects import TaskStatus
from tests.fakes import FakeExtractor, FakeModelFactory, FakeSearchProvider, WritingScript


class MockPublisher(IPublisher):
    def __init__(self, destination: PublicationTarget = PublicationTarget.SANITY):
        self._destination = destination
        self.calls: list[tuple[uuid.UUID, ArticleRevisionEntity, str | None]] = []
        self.unpublish_calls: list[str] = []
        self.fail_times = 0
        self.fail_with: Exception | None = None

    @property
    def destination(self) -> PublicationTarget:
        return self._destination

    async def publish(
        self,
        task_id: uuid.UUID,
        revision: ArticleRevisionEntity,
        existing_remote_id: str | None = None,
        on_asset_uploaded=None,
        options=None,
    ) -> PublishOutcome:
        self.calls.append((task_id, revision, existing_remote_id))
        self.last_options = options
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_with or RuntimeError("Simulated publisher failure")

        doc_id = existing_remote_id or revision.slug
        rendered_hash = hashlib.sha256(revision.markdown.encode("utf-8")).hexdigest()
        remote_prefix = "https://dev.to/articles" if self._destination == PublicationTarget.DEVTO else "https://leon-pham.vercel.app/posts"
        return PublishOutcome(
            destination=self._destination,
            remote_document_id=doc_id,
            remote_url=f"{remote_prefix}/{doc_id}",
            rendered_content_hash=rendered_hash,
            studio_url=f"https://demmqb6o.sanity.studio/structure/post;{doc_id}",
            rendered_markdown=revision.markdown,
        )

    async def unpublish(self, remote_document_id: str) -> None:
        self.unpublish_calls.append(remote_document_id)


@pytest.fixture
def mock_publisher():
    return MockPublisher(PublicationTarget.SANITY)


@pytest.fixture
def mock_devto_publisher():
    return MockPublisher(PublicationTarget.DEVTO)


@pytest.fixture
def script():
    return WritingScript()


@pytest.fixture
def client(monkeypatch, script, mock_publisher, mock_devto_publisher):
    monkeypatch.setattr(main, "get_model_factory", lambda: FakeModelFactory(script))
    monkeypatch.setattr(main, "get_search_provider", lambda: FakeSearchProvider())
    monkeypatch.setattr(main, "get_page_extractor", lambda: FakeExtractor())

    class CustomRegistry(PublisherRegistry):
        def __init__(self):
            self._publishers = {
                PublicationTarget.SANITY.value: mock_publisher,
                PublicationTarget.DEVTO.value: mock_devto_publisher,
            }

    main.app.dependency_overrides[PublisherRegistry] = CustomRegistry
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


def wait_idle(client, task_id, statuses, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/tasks/{task_id}")
        if resp.status_code == 429:
            time.sleep(0.2)
            continue
        body = resp.json()
        if "status" not in body:
            raise AssertionError(f"GET /tasks/{task_id} returned {resp.status_code}: {body}")
        if body["status"] in statuses and not body["is_running"]:
            return body
        time.sleep(0.15)
    raise AssertionError(f"task stuck in {body.get('status')}")


def revisions(client, task_id):
    return client.get(f"/tasks/{task_id}/revisions").json()["items"]


def get_revision(client, revision_id):
    return client.get(f"/revisions/{revision_id}").json()


def start_approved_article(client):
    created = client.post(
        "/tasks",
        json={"topic": "How LoRA fine-tuning works", "publication_targets": ["sanity"]},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    wait_idle(client, task_id, {"awaiting_review"})

    latest_summary = revisions(client, task_id)[0]
    latest = get_revision(client, latest_summary["id"])
    approved = client.post(
        f"/revisions/{latest['id']}/approvals",
        json={
            "destinations": ["sanity"],
            "content_hash": latest["content_hash"],
            "options": {"devto_mode": "draft"},
            "acknowledge_blockers": True,
        },
    )
    assert approved.status_code in (200, 201)
    wait_idle(client, task_id, {"approved"})
    return task_id, latest


def test_gate_failures_return_403_and_make_zero_publisher_calls(client, mock_publisher):
    # 1. Unapproved revision -> 403 APPROVAL_REQUIRED
    created = client.post(
        "/tasks",
        json={"topic": "How LoRA fine-tuning works", "publication_targets": ["sanity"]},
    )
    task_id = created.json()["id"]
    wait_idle(client, task_id, {"awaiting_review"})
    r1 = get_revision(client, revisions(client, task_id)[0]["id"])

    unapproved_res = client.post(f"/revisions/{r1['id']}/publish", json={"destinations": ["sanity"]})
    assert unapproved_res.status_code == 403
    assert unapproved_res.json()["code"] == "APPROVAL_REQUIRED"
    assert len(mock_publisher.calls) == 0

    # 2. Approve r1, then create r2 -> r1 becomes stale -> 403 APPROVAL_STALE
    approved = client.post(
        f"/revisions/{r1['id']}/approvals",
        json={
            "destinations": ["sanity"],
            "content_hash": r1["content_hash"],
            "options": {"devto_mode": "draft"},
            "acknowledge_blockers": True,
        },
    )
    assert approved.status_code in (200, 201)
    wait_idle(client, task_id, {"approved"})

    # Owner edits to create r2
    owner_edit = client.post(
        f"/tasks/{task_id}/revisions",
        json={
            "base_revision_id": r1["id"],
            "markdown": r1["markdown"] + "\n\nExtra note.",
            "metadata": {k: r1[k] for k in ("title", "slug", "description", "tags")},
        },
    )
    assert owner_edit.status_code == 201
    wait_idle(client, task_id, {"awaiting_review"})

    # Attempting to publish r1 now returns 403 APPROVAL_STALE
    stale_res = client.post(f"/revisions/{r1['id']}/publish", json={"destinations": ["sanity"]})
    assert stale_res.status_code == 403
    assert stale_res.json()["code"] == "APPROVAL_STALE"
    assert len(mock_publisher.calls) == 0


def test_successful_publish_and_idempotency(client, mock_publisher):
    task_id, r = start_approved_article(client)

    # Publish
    pub_res = client.post(f"/revisions/{r['id']}/publish", json={"destinations": ["sanity"]})
    assert pub_res.status_code == 200
    items = pub_res.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "succeeded"
    assert items[0]["remote_document_id"] == r["slug"]
    assert items[0]["remote_url"] == f"https://leon-pham.vercel.app/posts/{r['slug']}"
    assert len(mock_publisher.calls) == 1

    # Task is now in published status
    task = client.get(f"/tasks/{task_id}").json()
    assert task["status"] == "published"

    # Publications list endpoint
    list_res = client.get(f"/tasks/{task_id}/publications").json()["items"]
    assert len(list_res) == 1
    assert list_res[0]["status"] == "succeeded"

    # Idempotent retry: publishing same revision again makes ZERO additional adapter calls
    retry_res = client.post(f"/revisions/{r['id']}/publish", json={"destinations": ["sanity"]})
    assert retry_res.status_code == 200
    assert len(mock_publisher.calls) == 1  # Still 1 call!


def test_failed_publish_and_retry(client, mock_publisher):
    task_id, r = start_approved_article(client)

    # Configure publisher to fail on first attempt
    mock_publisher.fail_times = 1
    mock_publisher.fail_with = RuntimeError("Sanity 500 downstream error")

    pub_res = client.post(f"/revisions/{r['id']}/publish", json={"destinations": ["sanity"]})
    assert pub_res.status_code == 200
    items = pub_res.json()["items"]
    assert items[0]["status"] == "failed"
    assert "Sanity 500" in items[0]["last_error"]

    # Task moved to failed
    task = client.get(f"/tasks/{task_id}").json()
    assert task["status"] == "failed"
    assert task["failed_stage"] == "publishing"
    assert task["resumable"] is True

    # Retry endpoint
    retry_res = client.post(f"/tasks/{task_id}/publications/sanity/retry", json={})
    assert retry_res.status_code == 200, f"Retry error: {retry_res.status_code} {retry_res.text}"
    retry_items = retry_res.json()["items"]
    assert retry_items[0]["status"] == "succeeded"

    # Task moved to published
    task_after = wait_idle(client, task_id, {"published"})
    assert task_after["status"] == "published"


def test_edit_published_article_and_republish(client, mock_publisher):
    task_id, r1 = start_approved_article(client)

    # Initial publish
    client.post(f"/revisions/{r1['id']}/publish", json={"destinations": ["sanity"]})
    wait_idle(client, task_id, {"published"})
    initial_pub = client.get(f"/tasks/{task_id}/publications").json()["items"][0]
    initial_published_at = initial_pub["published_at"]

    # Owner edits the published article
    owner_edit = client.post(
        f"/tasks/{task_id}/revisions",
        json={
            "base_revision_id": r1["id"],
            "markdown": r1["markdown"] + "\n\nUpdated section.",
            "metadata": {k: r1[k] for k in ("title", "slug", "description", "tags")},
        },
    )
    assert owner_edit.status_code == 201
    r2 = owner_edit.json()

    # Task returns to awaiting_review and approvals are voided
    task = wait_idle(client, task_id, {"awaiting_review"})
    assert task["status"] == "awaiting_review"

    # Owner approves r2
    client.post(
        f"/revisions/{r2['id']}/approvals",
        json={
            "destinations": ["sanity"],
            "content_hash": r2["content_hash"],
            "options": {"devto_mode": "draft"},
            "acknowledge_blockers": True,
        },
    )
    wait_idle(client, task_id, {"approved"})

    # Republishing r2
    client.post(f"/revisions/{r2['id']}/publish", json={"destinations": ["sanity"]})
    republished_pub = client.get(f"/tasks/{task_id}/publications").json()["items"][0]

    # Preserves published_at!
    assert republished_pub["published_at"] == initial_published_at
    assert republished_pub["remote_document_id"] == initial_pub["remote_document_id"]
    assert republished_pub["article_revision_id"] == r2["id"]


def test_unpublish_flow(client, mock_publisher):
    task_id, r = start_approved_article(client)
    client.post(f"/revisions/{r['id']}/publish", json={"destinations": ["sanity"]})
    assert len(client.get(f"/tasks/{task_id}/publications").json()["items"]) == 1

    # Slug mismatch in confirmation fails
    bad_slug_res = client.post(f"/tasks/{task_id}/unpublish", json={"slug": "wrong-slug", "destinations": ["sanity"]})
    assert bad_slug_res.status_code == 400

    # Matching slug unpublishes successfully
    unpub_res = client.post(f"/tasks/{task_id}/unpublish", json={"slug": r["slug"], "destinations": ["sanity"]})
    assert unpub_res.status_code == 200
    assert len(mock_publisher.unpublish_calls) == 1
    assert mock_publisher.unpublish_calls[0] == r["slug"]
    assert len(unpub_res.json()["items"]) == 0


def test_devto_dual_publishing_and_mode_gate(client, mock_publisher, mock_devto_publisher):
    # 1. Create task with both sanity and devto
    created = client.post(
        "/tasks",
        json={"topic": "How LoRA fine-tuning works", "publication_targets": ["sanity", "devto"]},
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    wait_idle(client, task_id, {"awaiting_review"})

    r = get_revision(client, revisions(client, task_id)[0]["id"])

    # 2. Approve for sanity + devto with draft mode
    approve_res = client.post(
        f"/revisions/{r['id']}/approvals",
        json={
            "destinations": ["sanity", "devto"],
            "content_hash": r["content_hash"],
            "options": {"devto_mode": "draft"},
            "acknowledge_blockers": True,
        },
    )
    assert approve_res.status_code in (200, 201)
    wait_idle(client, task_id, {"approved"})

    # 3. Trying to publish devto with mode=published fails gate check
    bad_mode_res = client.post(
        f"/revisions/{r['id']}/publish",
        json={"destinations": ["devto"], "options": {"mode": "published"}},
    )
    assert bad_mode_res.status_code == 403
    assert len(mock_devto_publisher.calls) == 0

    # 4. Publishing approved draft succeeds for both destinations
    pub_res = client.post(
        f"/revisions/{r['id']}/publish",
        json={"destinations": ["sanity", "devto"]},
    )
    assert pub_res.status_code == 200
    items = pub_res.json()["items"]
    assert len(items) == 2
    assert {i["destination"] for i in items} == {"sanity", "devto"}
    assert all(i["status"] == "succeeded" for i in items)

    # Dev.to publisher received draft mode
    assert mock_devto_publisher.last_options.get("mode") == "draft"

    task = wait_idle(client, task_id, {"published"})
    assert task["status"] == "published"


def test_retry_retries_only_failed_destination(client, mock_publisher, mock_devto_publisher):
    created = client.post(
        "/tasks",
        json={"topic": "How LoRA fine-tuning works", "publication_targets": ["sanity", "devto"]},
    )
    task_id = created.json()["id"]
    wait_idle(client, task_id, {"awaiting_review"})
    r = get_revision(client, revisions(client, task_id)[0]["id"])

    client.post(
        f"/revisions/{r['id']}/approvals",
        json={
            "destinations": ["sanity", "devto"],
            "content_hash": r["content_hash"],
            "options": {"devto_mode": "draft"},
            "acknowledge_blockers": True,
        },
    )
    wait_idle(client, task_id, {"approved"})

    # Make Dev.to publisher fail once
    mock_devto_publisher.fail_times = 1

    pub_res = client.post(
        f"/revisions/{r['id']}/publish",
        json={"destinations": ["sanity", "devto"]},
    )
    assert pub_res.status_code == 200
    pubs = {p["destination"]: p for p in pub_res.json()["items"]}
    assert pubs["sanity"]["status"] == "succeeded"
    assert pubs["devto"]["status"] == "failed"

    # Task is partially published
    wait_idle(client, task_id, {"partially_published"})

    # Retry ONLY devto
    initial_sanity_calls = len(mock_publisher.calls)
    retry_res = client.post(f"/tasks/{task_id}/publications/devto/retry", json={})
    assert retry_res.status_code == 200

    # Sanity publisher was NOT called again!
    assert len(mock_publisher.calls) == initial_sanity_calls
    # Devto publisher was called and now succeeded
    retry_pubs = {p["destination"]: p for p in retry_res.json()["items"]}
    assert retry_pubs["devto"]["status"] == "succeeded"

    wait_idle(client, task_id, {"published"})

