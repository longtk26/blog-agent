from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
import respx
import httpx

from src.modules.styles.domain.sample_importers import (
    fetch_sanity_samples,
    fetch_local_samples,
    parse_iso_datetime,
)


def test_parse_iso_datetime():
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("") is None
    dt = parse_iso_datetime("2026-03-15T10:30:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 3


@pytest.mark.asyncio
@respx.mock
async def test_fetch_sanity_samples():
    project_id = "test_project"
    dataset = "production"
    api_version = "2024-01-01"

    mock_response = {
        "result": [
            {
                "_id": "post_123",
                "title": "Introduction to LoRA",
                "tags": [{"value": "ai"}, "deep-learning"],
                "publishedAt": "2026-01-10T12:00:00Z",
                "content": "# Intro to LoRA\n\nLoRA reduces trainable parameters.",
            },
            {
                "_id": "post_empty",
                "title": "Empty Post",
                "content": "",
            },
        ]
    }

    respx.get(url__startswith=f"https://{project_id}.api.sanity.io").mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    samples = await fetch_sanity_samples(
        project_id=project_id,
        dataset=dataset,
        api_version=api_version,
        token="test_token",
    )

    assert len(samples) == 1
    sample = samples[0]
    assert sample.origin == "sanity"
    assert sample.remote_id == "post_123"
    assert sample.title == "Introduction to LoRA"
    assert sample.tags == ["ai", "deep-learning"]
    assert sample.meta_sanity_id == "post_123"
    assert "reduces trainable parameters" in sample.content


def test_fetch_local_samples(tmp_path: Path):
    blogs_dir = tmp_path / "blogs"
    blogs_dir.mkdir()

    # Create .publish-meta.json
    meta = {
        "ai/lora_guide": {
            "sanity": "sanity_lora_999",
            "published": True,
        }
    }
    (blogs_dir / ".publish-meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # Create subfolder and md files
    ai_dir = blogs_dir / "ai"
    ai_dir.mkdir()
    (ai_dir / "lora_guide.md").write_text("# Understanding LoRA Fine-Tuning\n\nContent here.", encoding="utf-8")
    (ai_dir / "draft.md").write_text("# Draft Article\n\nDraft content.", encoding="utf-8")

    samples = fetch_local_samples(blogs_dir)
    assert len(samples) == 2

    lora_sample = next(s for s in samples if "lora_guide" in s.remote_id)
    assert lora_sample.origin == "local"
    assert lora_sample.title == "Understanding LoRA Fine-Tuning"
    assert lora_sample.meta_sanity_id == "sanity_lora_999"
    assert "ai" in lora_sample.tags

    draft_sample = next(s for s in samples if "draft" in s.remote_id)
    assert draft_sample.meta_sanity_id is None
