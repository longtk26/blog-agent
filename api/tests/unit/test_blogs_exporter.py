import json
import uuid
from pathlib import Path

from src.modules.publishing.domain.blogs_exporter import BlogsExporter
from src.modules.shared.domain.entities import ArticleRevisionEntity, RevisionAuthor


def test_blogs_exporter_exports_atomically(tmp_path: Path):
    exporter = BlogsExporter(tmp_path, enabled=True)
    assert exporter.is_available()

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="LoRA Fine-Tuning",
        slug="lora-fine-tuning",
        description="A guide",
        tags=["ai"],
        markdown="# LoRA\n\nContent",
        created_by=RevisionAuthor.AI,
        content_hash="h1",
        metadata={"series": {"name": "llm_guides"}},
    )

    rendered_markdown = "# LoRA\n\nRendered Content with CDN"
    target = exporter.export(revision, "sanity-doc-123", rendered_markdown)

    assert target is not None
    assert target.exists()
    assert target.read_text(encoding="utf-8") == rendered_markdown
    assert target.parent.name == "llm_guides"

    meta_file = tmp_path / ".publish-meta.json"
    assert meta_file.exists()
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert meta["llm_guides/lora-fine-tuning"]["sanity"] == "sanity-doc-123"


def test_blogs_exporter_does_not_overwrite_unowned_files(tmp_path: Path):
    exporter = BlogsExporter(tmp_path, enabled=True)
    folder = tmp_path / "my-post"
    folder.mkdir(parents=True)
    existing_file = folder / "my-post.md"
    existing_file.write_text("User hand-written post", encoding="utf-8")

    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="My Post",
        slug="my-post",
        description="Desc",
        tags=[],
        markdown="# New",
        created_by=RevisionAuthor.AI,
        content_hash="h1",
    )

    target = exporter.export(revision, "doc-456", "# Agent New Post")

    # Hand-written file is protected!
    assert existing_file.read_text(encoding="utf-8") == "User hand-written post"
    # Agent wrote to .agent.md instead
    assert target == folder / "my-post.agent.md"
    assert target.read_text(encoding="utf-8") == "# Agent New Post"
