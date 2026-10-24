import base64
import httpx
import pytest
import respx

from src.modules.publishing.domain.thumbnail_prompt import build_thumbnail_prompt
from src.modules.publishing.infrastructure.adapters.google_thumbnail_generator import GoogleThumbnailGenerator


def test_build_thumbnail_prompt_includes_metadata_and_constraints():
    title = "Distributed Rate Limiting with Redis & Token Bucket"
    description = "A deep dive into building ultra-low latency rate limiters."
    toc = ["Architecture Overview", "Token Bucket Algorithm", "Redis Cluster Synchronization"]

    prompt = build_thumbnail_prompt(title, description, toc)

    assert title in prompt
    assert description in prompt
    assert "Architecture Overview" in prompt
    assert "Redis Cluster Synchronization" in prompt
    assert "16:9 widescreen" in prompt
    assert "no text, no words, no letters" in prompt
    assert "dark-mode" in prompt


def test_build_thumbnail_prompt_handles_empty_toc():
    prompt = build_thumbnail_prompt("Simple Title", "Simple Desc", [])
    assert "Simple Title" in prompt
    assert "Simple Desc" in prompt
    assert "16:9" in prompt


@pytest.mark.asyncio
async def test_thumbnail_generator_skips_when_no_api_key():
    gen = GoogleThumbnailGenerator(api_key="")
    result = await gen.generate_thumbnail("Title", "Desc", ["Section 1"], slug="my-post")
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_thumbnail_generator_success():
    fake_png_data = b"\x89PNG\r\n\x1a\nfakeimagebytes"
    b64_content = base64.b64encode(fake_png_data).decode("utf-8")

    api_key = "test-gemini-key"
    model = "gemini-3.1-flash-image"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    respx.post(url).respond(
        status_code=200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": b64_content,
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )

    gen = GoogleThumbnailGenerator(api_key=api_key, model=model)
    result = await gen.generate_thumbnail(
        title="Microservices Observability",
        description="Tracing and metrics with OpenTelemetry",
        table_of_contents=["Traces", "Metrics", "Spans"],
        slug="observability",
    )

    assert result is not None
    img_bytes, filename, mime = result
    assert img_bytes == fake_png_data
    assert filename == "thumbnail_observability.png"
    assert mime == "image/png"


@pytest.mark.asyncio
@respx.mock
async def test_thumbnail_generator_handles_api_error():
    api_key = "test-gemini-key"
    model = "gemini-3.1-flash-image"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    respx.post(url).respond(
        status_code=500,
        text="Internal Server Error",
    )

    gen = GoogleThumbnailGenerator(api_key=api_key, model=model)
    result = await gen.generate_thumbnail("Title", "Desc", [], slug="err-test")
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_thumbnail_generator_handles_empty_candidates():
    api_key = "test-gemini-key"
    model = "gemini-3.1-flash-image"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    respx.post(url).respond(
        status_code=200,
        json={"candidates": []},
    )

    gen = GoogleThumbnailGenerator(api_key=api_key, model=model)
    result = await gen.generate_thumbnail("Title", "Desc", [], slug="empty-test")
    assert result is None
