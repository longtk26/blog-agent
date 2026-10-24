import base64
import logging

import httpx

from src.configs.config import config
from src.modules.publishing.domain.thumbnail_prompt import build_thumbnail_prompt
from src.modules.publishing.ports.output.thumbnail_generator import IThumbnailGenerator

logger = logging.getLogger(__name__)


class GoogleThumbnailGenerator(IThumbnailGenerator):
    """Generates 16:9 thumbnail illustrations using Google GenAI image generation models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key or (config.google_api_key.get_secret_value() if config.google_api_key else None)
        self.model = model or config.thumbnail_model or "gemini-3.1-flash-image"
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=45.0)

    async def generate_thumbnail(
        self,
        title: str,
        description: str,
        table_of_contents: list[str],
        slug: str = "blog",
    ) -> tuple[bytes, str, str] | None:
        if not self._api_key:
            logger.info("GOOGLE_API_KEY is not configured; skipping automatic thumbnail generation")
            return None

        prompt = build_thumbnail_prompt(title, description, table_of_contents)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self._api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseModalities": ["IMAGE"]
            },
        }

        client = await self._get_client()
        try:
            resp = await client.post(url, json=payload, timeout=45.0)
            if resp.status_code != 200:
                logger.warning(
                    f"Google thumbnail generation failed for '{title}' (status {resp.status_code}): {resp.text[:300]}"
                )
                return None

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning(f"Google thumbnail generation returned no candidates: {data}")
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                if "inlineData" in p:
                    b64_data = p["inlineData"].get("data", "")
                    mime = p["inlineData"].get("mimeType", "image/png")
                    image_bytes = base64.b64decode(b64_data)
                    ext = ".png" if "png" in mime else ".jpg"
                    filename = f"thumbnail_{slug}{ext}"
                    logger.info(f"Generated thumbnail for '{title}' using {self.model} ({len(image_bytes)} bytes)")
                    return image_bytes, filename, mime

            logger.warning(f"No inline image data found in Google response parts for '{title}'")
            return None
        except Exception as exc:
            logger.warning(f"Unexpected error generating thumbnail for '{title}': {exc}")
            return None
        finally:
            if self._client is None:
                await client.aclose()
