import uuid
import pytest

from src.modules.publishing.domain.sanity_renderer import (
    extract_sanity_asset_ref,
    render_for_sanity,
)
from src.modules.shared.domain.entities import ArticleRevisionEntity, RevisionAuthor


class DummyUploader:
    def __init__(self):
        self.uploads: list[tuple[str, str, str]] = []

    async def upload_asset(self, src: str, alt: str = "", title: str = "") -> tuple[str, str]:
        self.uploads.append((src, alt, title))
        asset_id = f"image-{len(self.uploads)}abc-100x100-png"
        cdn_url = f"https://cdn.sanity.io/images/demmqb6o/blogs/{len(self.uploads)}abc-100x100.png"
        return asset_id, cdn_url


def test_extract_sanity_asset_ref():
    url = "https://cdn.sanity.io/images/demmqb6o/blogs/6d8c83cb3b171-1200x630.png"
    assert extract_sanity_asset_ref(url) == "image-6d8c83cb3b171-1200x630-png"
    assert extract_sanity_asset_ref("https://example.com/pic.png") is None


@pytest.mark.asyncio
async def test_render_for_sanity_rewrites_local_images():
    uploader = DummyUploader()
    uploaded_events: list[tuple[str, str, str]] = []

    markdown = """# Title

Here is a diagram:
![Architecture diagram](diagrams/arch.png "System Architecture")

And a chart:
![Chart](diagrams/chart.svg)
"""
    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Title",
        slug="my-post",
        description="Desc",
        tags=["ai", "lora"],
        markdown=markdown,
        created_by=RevisionAuthor.AI,
        content_hash="orig-hash",
    )

    res = await render_for_sanity(
        revision,
        uploader=uploader,
        on_asset_uploaded=lambda s, a, u: uploaded_events.append((s, a, u)),
    )

    # Stored revision markdown is unchanged
    assert revision.markdown == markdown

    # Rendered markdown has CDN URLs and preserved titles
    assert "https://cdn.sanity.io/images/demmqb6o/blogs/1abc-100x100.png" in res.rendered_markdown
    assert '"System Architecture"' in res.rendered_markdown
    assert "https://cdn.sanity.io/images/demmqb6o/blogs/2abc-100x100.png" in res.rendered_markdown

    # Images array has stable keys and references
    assert len(res.images) == 2
    assert res.images[0]["_type"] == "image"
    assert res.images[0]["caption"] == "System Architecture"
    assert res.images[0]["alt"] == "Architecture diagram"
    assert res.images[0]["asset"]["_ref"] == "image-1abc-100x100-png"
    assert res.images[0]["_key"].startswith("img_")

    # Cover image defaults to first image
    assert res.cover_image_asset_ref == "image-1abc-100x100-png"
    assert len(uploaded_events) == 2


@pytest.mark.asyncio
async def test_render_for_sanity_preserves_existing_cdn_urls():
    existing_cdn = "https://cdn.sanity.io/images/demmqb6o/blogs/existing123-800x600.jpg"
    markdown = f"![Cover]({existing_cdn} 'Cover photo')"

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Title",
        slug="my-post",
        description="Desc",
        tags=["test"],
        markdown=markdown,
        created_by=RevisionAuthor.OWNER,
        content_hash="h1",
    )

    uploader = DummyUploader()
    res = await render_for_sanity(revision, uploader=uploader)

    # No new upload for already-hosted CDN images
    assert len(uploader.uploads) == 0
    assert existing_cdn in res.rendered_markdown
    assert len(res.images) == 1
    assert res.images[0]["asset"]["_ref"] == "image-existing123-800x600-jpg"
    assert res.cover_image_asset_ref == "image-existing123-800x600-jpg"
