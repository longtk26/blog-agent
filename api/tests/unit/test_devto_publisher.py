import json
import uuid
import httpx
import pytest
import respx

from src.modules.publishing.infrastructure.adapters.devto_publisher import DevtoPublisher
from src.modules.publishing.ports.output.publisher import PublishError
from src.modules.shared.domain.entities import ArticleRevisionEntity, PublicationTarget, RevisionAuthor


@pytest.fixture
def publisher():
    return DevtoPublisher(
        api_key="test-devto-key-xyz",
        base_url="https://dev.to/api",
    )


@pytest.fixture
def revision():
    return ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Testing Dev.to Publisher",
        slug="testing-devto-publisher",
        description="A test post for dev.to",
        tags=["python", "fastapi"],
        markdown="# Testing Dev.to Publisher\n\nThis is content with $x = 10$.\n",
        created_by=RevisionAuthor.AI,
        content_hash="rev-hash-123",
    )


@pytest.mark.asyncio
@respx.mock
async def test_first_publish_creates_post(publisher: DevtoPublisher, revision: ArticleRevisionEntity):
    # 1. me/all endpoint returns empty list
    respx.get("https://dev.to/api/articles/me/all?page=1&per_page=100").respond(
        status_code=200,
        json=[],
    )

    # 2. POST /articles creates new draft
    post_route = respx.post("https://dev.to/api/articles").respond(
        status_code=201,
        json={
            "id": 991122,
            "url": "https://dev.to/owner/testing-devto-publisher-991122",
            "published": False,
        },
    )

    outcome = await publisher.publish(
        task_id=revision.task_id,
        revision=revision,
        options={"mode": "draft"},
    )

    assert post_route.called
    req = json.loads(post_route.calls.last.request.content)
    assert req["article"]["title"] == "Testing Dev.to Publisher"
    assert req["article"]["published"] is False
    assert req["article"]["tags"] == ["python", "fastapi"]
    assert post_route.calls.last.request.headers["api-key"] == "test-devto-key-xyz"

    assert outcome.destination == PublicationTarget.DEVTO
    assert outcome.remote_document_id == "991122"
    assert outcome.remote_url == "https://dev.to/owner/testing-devto-publisher-991122"


@pytest.mark.asyncio
@respx.mock
async def test_first_publish_adopts_existing_matching_article(
    publisher: DevtoPublisher, revision: ArticleRevisionEntity
):
    # me/all returns an existing article matching canonical_url
    canonical_url = f"https://leon-pham.vercel.app/posts/{revision.slug}"
    respx.get("https://dev.to/api/articles/me/all?page=1&per_page=100").respond(
        status_code=200,
        json=[
            {
                "id": 883311,
                "title": "Old Title",
                "canonical_url": canonical_url,
                "url": "https://dev.to/owner/old-title-883311",
            }
        ],
    )

    put_route = respx.put("https://dev.to/api/articles/883311").respond(
        status_code=200,
        json={
            "id": 883311,
            "url": "https://dev.to/owner/testing-devto-publisher-883311",
            "published": False,
        },
    )

    outcome = await publisher.publish(
        task_id=revision.task_id,
        revision=revision,
    )

    assert put_route.called
    assert outcome.remote_document_id == "883311"


@pytest.mark.asyncio
@respx.mock
async def test_later_publish_updates_with_existing_remote_id(
    publisher: DevtoPublisher, revision: ArticleRevisionEntity
):
    put_route = respx.put("https://dev.to/api/articles/554433").respond(
        status_code=200,
        json={
            "id": 554433,
            "url": "https://dev.to/owner/testing-devto-publisher-554433",
            "published": True,
        },
    )

    outcome = await publisher.publish(
        task_id=revision.task_id,
        revision=revision,
        existing_remote_id="554433",
        options={"mode": "published"},
    )

    assert put_route.called
    req = json.loads(put_route.calls.last.request.content)
    assert req["article"]["published"] is True
    assert outcome.remote_document_id == "554433"


@pytest.mark.asyncio
@respx.mock
async def test_devto_rate_limit_retry_after(publisher: DevtoPublisher, revision: ArticleRevisionEntity):
    # First attempt: 429 with retry-after=0.1
    # Second attempt: 200 OK
    respx.put("https://dev.to/api/articles/123").mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "0.05"}, text="rate limited"),
            httpx.Response(200, json={"id": 123, "url": "https://dev.to/123"}),
        ]
    )

    outcome = await publisher.publish(
        task_id=revision.task_id,
        revision=revision,
        existing_remote_id="123",
    )

    assert outcome.remote_document_id == "123"


@pytest.mark.asyncio
@respx.mock
async def test_devto_validation_error_fails_immediately(publisher: DevtoPublisher, revision: ArticleRevisionEntity):
    # 422 Unprocessable Entity (e.g. invalid tags)
    respx.put("https://dev.to/api/articles/123").respond(
        status_code=422,
        json={"error": "Tag contains invalid characters", "status": 422},
    )

    with pytest.raises(PublishError) as exc_info:
        await publisher.publish(
            task_id=revision.task_id,
            revision=revision,
            existing_remote_id="123",
        )

    assert exc_info.value.retryable is False
    assert exc_info.value.status_code == 422
    assert "Tag contains invalid characters" in exc_info.value.message


@pytest.mark.asyncio
@respx.mock
async def test_unpublish_sets_published_false(publisher: DevtoPublisher):
    unpub_route = respx.put("https://dev.to/api/articles/777/unpublish").respond(status_code=200)

    await publisher.unpublish("777")
    assert unpub_route.called
