import hashlib
from unittest.mock import AsyncMock
import uuid
import httpx
import pytest
import respx

from src.libs.exceptions import ConflictException
from src.modules.publishing.infrastructure.adapters.sanity_publisher import SanityPublisher
from src.modules.publishing.ports.output.publisher import PublishError
from src.modules.shared.domain.entities import ArticleRevisionEntity, RevisionAuthor


@pytest.fixture
def publisher():
    return SanityPublisher(
        project_id="demmqb6o",
        dataset="blogs",
        api_version="2025-01-20",
        token="test-write-token-12345",
        site_base_url="https://leon-pham.vercel.app",
        studio_base_url="https://demmqb6o.sanity.studio",
    )


@pytest.mark.asyncio
@respx.mock
async def test_collision_check(publisher: SanityPublisher):
    # Existing document
    respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/taken-slug").respond(
        status_code=200,
        json={"documents": [{"_id": "taken-slug", "_type": "post"}]},
    )
    # Available document (404)
    respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/available-slug").respond(
        status_code=404,
    )
    # Available document (200 with empty documents array - real Sanity behavior)
    respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/empty-docs-slug").respond(
        status_code=200,
        json={"documents": []},
    )

    assert await publisher.check_collision("taken-slug") is True
    assert await publisher.check_collision("available-slug") is False
    assert await publisher.check_collision("empty-docs-slug") is False


@pytest.mark.asyncio
@respx.mock
async def test_publish_collision_raises_slug_taken(publisher: SanityPublisher):
    respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/my-slug").respond(
        status_code=200,
        json={"documents": [{"_id": "my-slug", "_type": "post"}]},
    )

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="My Title",
        slug="my-slug",
        description="My Desc",
        tags=["ai"],
        markdown="# Content\n\nBody",
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    with pytest.raises(ConflictException) as exc_info:
        await publisher.publish(revision.task_id, revision)
    assert "taken" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_publish_success_flow(publisher: SanityPublisher):
    content = "# My Title\n\nPublished body text.\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # 1. Mutate endpoint -> 200
    mutate_route = respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    ).respond(status_code=200, json={"results": [{"id": "my-post"}]})

    # 2. Doc endpoint: 404 for collision check, then 200 for readback
    doc_route = respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/my-post")
    doc_route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"documents": [{"_id": "my-post", "_type": "post", "content": content}]}),
    ]

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="My Title",
        slug="my-post",
        description="My Desc",
        tags=["ai", "fine-tuning"],
        markdown=content,
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    outcome = await publisher.publish(revision.task_id, revision)

    assert outcome.remote_document_id == "my-post"
    assert outcome.remote_url == "https://leon-pham.vercel.app/posts/my-post"
    assert outcome.studio_url == "https://demmqb6o.sanity.studio/structure/post;my-post"
    assert outcome.rendered_content_hash == content_hash

    # Check mutation payload structure
    sent_payload = mutate_route.calls[0].request.read().decode("utf-8")
    assert '"createIfNotExists"' in sent_payload
    assert '"patch"' in sent_payload
    assert '"setIfMissing"' in sent_payload
    assert '"publishedAt"' in sent_payload
    assert '"updatedAt"' in sent_payload


@pytest.mark.asyncio
@respx.mock
async def test_publish_readback_hash_mismatch_raises(publisher: SanityPublisher):
    content = "# Title\n\nContent\n"

    respx.post("https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync").respond(
        status_code=200, json={"results": []}
    )
    doc_route = respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/mismatch-post")
    doc_route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"documents": [{"_id": "mismatch-post", "content": "Tampered or corrupted content"}]}),
    ]

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Title",
        slug="mismatch-post",
        description="Desc",
        tags=[],
        markdown=content,
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    with pytest.raises(PublishError) as exc_info:
        await publisher.publish(revision.task_id, revision)
    assert "hash mismatch" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_publish_fails_immediately_on_4xx(publisher: SanityPublisher):
    respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/err-post").respond(status_code=404)
    mutate_route = respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    ).respond(status_code=401, text="Unauthorized: invalid write token")

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Title",
        slug="err-post",
        description="Desc",
        tags=[],
        markdown="# Text",
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    with pytest.raises(PublishError) as exc_info:
        await publisher.publish(revision.task_id, revision)

    assert not exc_info.value.retryable
    assert exc_info.value.status_code == 401
    # Only 1 call made, no retries on 4xx
    assert len(mutate_route.calls) == 1


@pytest.mark.asyncio
@respx.mock
async def test_publish_retries_on_5xx_and_succeeds(publisher: SanityPublisher):
    content = "# Content\n"
    # Doc endpoint: 404 for collision check, then 200 for readback
    doc_route = respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/retry-post")
    doc_route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"documents": [{"_id": "retry-post", "content": content}]}),
    ]

    # First attempt: 503 Service Unavailable, second attempt: 200 OK
    mutate_route = respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    )
    mutate_route.side_effect = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(200, json={"results": []}),
    ]

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Title",
        slug="retry-post",
        description="Desc",
        tags=[],
        markdown=content,
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    outcome = await publisher.publish(revision.task_id, revision)
    assert outcome.remote_document_id == "retry-post"
    assert len(mutate_route.calls) == 2


@pytest.mark.asyncio
@respx.mock
async def test_unpublish_sends_delete_mutations(publisher: SanityPublisher):
    mutate_route = respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    ).respond(status_code=200, json={"results": []})

    await publisher.unpublish("my-post")

    sent_payload = mutate_route.calls[0].request.read().decode("utf-8")
    assert '"delete"' in sent_payload
    assert '"my-post"' in sent_payload
    assert '"drafts.my-post"' in sent_payload


@pytest.mark.asyncio
@respx.mock
async def test_publish_generates_and_attaches_thumbnail_when_no_cover_image():
    # Setup mock thumbnail generator
    mock_generator = AsyncMock()
    fake_png = b"\x89PNG\r\n\x1a\nthumb_bytes"
    mock_generator.generate_thumbnail.return_value = (fake_png, "thumbnail_thumb-post.png", "image/png")

    pub = SanityPublisher(
        project_id="demmqb6o",
        dataset="blogs",
        api_version="2025-01-20",
        token="test-token",
        thumbnail_generator=mock_generator,
    )

    content = "# Title\n\n## Section One\nText 1\n\n## Section Two\nText 2\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Asset upload route
    respx.post("https://demmqb6o.api.sanity.io/v2025-01-20/assets/images/blogs?filename=thumbnail_thumb-post.png").respond(
        status_code=200,
        json={"document": {"_id": "image-thumb123", "url": "https://cdn.sanity.io/images/demmqb6o/blogs/thumb123.png"}},
    )

    # Mutation route
    mutate_route = respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    ).respond(status_code=200, json={"results": []})

    # Doc route: 404 collision check, then 200 readback
    doc_route = respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/thumb-post")
    doc_route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"documents": [{"_id": "thumb-post", "content": content}]}),
    ]

    uploaded_assets = []
    def on_upload(src: str, asset_id: str, cdn_url: str):
        uploaded_assets.append((src, asset_id, cdn_url))

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Modern Blog Post",
        slug="thumb-post",
        description="Great description",
        tags=["tech"],
        markdown=content,
        created_by=RevisionAuthor.AI,
        content_hash="h1",
        metadata={"outline": {"sections": [{"heading": "Section One"}, {"heading": "Section Two"}]}},
    )

    outcome = await pub.publish(revision.task_id, revision, on_asset_uploaded=on_upload)
    assert outcome.remote_document_id == "thumb-post"

    # Verify generator was called with extracted TOC headings
    mock_generator.generate_thumbnail.assert_called_once_with(
        title="Modern Blog Post",
        description="Great description",
        table_of_contents=["Section One", "Section Two"],
        slug="thumb-post",
    )

    # Verify asset was uploaded and registered in callback
    assert len(uploaded_assets) == 1
    assert uploaded_assets[0] == ("thumbnail://generated", "image-thumb123", "https://cdn.sanity.io/images/demmqb6o/blogs/thumb123.png")

    # Verify mutation patch sets image field
    sent_payload = mutate_route.calls[0].request.read().decode("utf-8")
    assert '"image"' in sent_payload
    assert '"image-thumb123"' in sent_payload


@pytest.mark.asyncio
@respx.mock
async def test_publish_continues_gracefully_if_thumbnail_fails():
    mock_generator = AsyncMock()
    mock_generator.generate_thumbnail.side_effect = RuntimeError("Generation failed")

    pub = SanityPublisher(
        project_id="demmqb6o",
        dataset="blogs",
        api_version="2025-01-20",
        token="test-token",
        thumbnail_generator=mock_generator,
    )

    content = "# Post without thumb\n\nContent\n"
    respx.post(
        "https://demmqb6o.api.sanity.io/v2025-01-20/data/mutate/blogs?returnIds=true&visibility=sync"
    ).respond(status_code=200, json={"results": []})

    doc_route = respx.get("https://demmqb6o.api.sanity.io/v2025-01-20/data/doc/blogs/fallback-post")
    doc_route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json={"documents": [{"_id": "fallback-post", "content": content}]}),
    ]

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Fallback Post",
        slug="fallback-post",
        description="Desc",
        tags=[],
        markdown=content,
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    outcome = await pub.publish(revision.task_id, revision)
    assert outcome.remote_document_id == "fallback-post"

