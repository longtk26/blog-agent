import asyncio
import re

import httpx
import trafilatura

from src.modules.research.infrastructure.adapters.safe_fetch import safe_fetch
from src.modules.research.ports.output import ExtractedPage, ExtractionError, IPageExtractor

CANONICAL_LINK = re.compile(r"<link[^>]+rel=[\"']canonical[\"'][^>]*>", re.IGNORECASE)
HREF = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)


def _canonical_from_html(html: str) -> str | None:
    match = CANONICAL_LINK.search(html[:200_000])
    if not match:
        return None
    href = HREF.search(match.group(0))
    return href.group(1) if href else None


def _extract(html: str, url: str) -> tuple[str | None, dict]:
    text = trafilatura.extract(
        html, url=url, output_format="txt", include_tables=True, include_comments=False, favor_precision=True
    )
    meta = trafilatura.extract_metadata(html, default_url=url)
    info = {}
    if meta is not None:
        info = {"title": meta.title, "publisher": meta.sitename or meta.hostname, "published_at": meta.date}
    return text, info


class HttpPageExtractor(IPageExtractor):
    """Local fetch (httpx, SSRF-guarded) + trafilatura extraction. Fallback when Tavily is absent or fails."""

    name = "http"

    def __init__(self, timeout_seconds: float, max_bytes: int, allow_private: bool = False):
        self.timeout = httpx.Timeout(timeout_seconds)
        self.max_bytes = max_bytes
        self.allow_private = allow_private

    async def extract(self, url: str) -> ExtractedPage:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                page = await safe_fetch(client, url, max_bytes=self.max_bytes, allow_private=self.allow_private)
        except httpx.HTTPError as exc:
            raise ExtractionError(f"Fetch failed: {type(exc).__name__}") from exc

        html = page.body.decode("utf-8", errors="replace")
        if page.content_type == "text/plain":
            text, info = html, {}
        else:
            text, info = await asyncio.to_thread(_extract, html, page.final_url)
        if not text or not text.strip():
            raise ExtractionError("No readable text extracted")
        return ExtractedPage(
            url=url,
            final_url=page.final_url,
            canonical_url=_canonical_from_html(html),
            title=info.get("title"),
            publisher=info.get("publisher"),
            published_at=info.get("published_at"),
            text=text,
        )
