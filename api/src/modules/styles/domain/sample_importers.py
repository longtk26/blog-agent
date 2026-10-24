from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RawSampleItem:
    origin: str  # "sanity" | "local"
    remote_id: str  # Sanity document _id or relative path
    title: str
    tags: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    content: str = ""
    meta_sanity_id: str | None = None


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        # Replace Z with +00:00 for fromisoformat compatibility
        clean = value.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


async def fetch_sanity_samples(
    project_id: str,
    dataset: str,
    api_version: str,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[RawSampleItem]:
    """Fetch all post documents from Sanity via GROQ query."""
    groq_query = '*[_type == "post"] { _id, title, description, tags, publishedAt, content }'
    url = f"https://{project_id}.api.sanity.io/v{api_version}/data/query/{dataset}?query={quote(groq_query)}"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
        should_close = True

    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning(f"Sanity sample fetch returned {resp.status_code}: {resp.text[:300]}")
            return []

        data = resp.json()
        documents = data.get("result", [])
        samples: list[RawSampleItem] = []

        for doc in documents:
            if not isinstance(doc, dict):
                continue
            doc_id = doc.get("_id")
            content = doc.get("content") or ""
            if not doc_id or not content.strip():
                continue

            # Extract tags (could be list of strings or list of {value: ...})
            raw_tags = doc.get("tags") or []
            tags: list[str] = []
            for t in raw_tags:
                if isinstance(t, dict) and "value" in t:
                    tags.append(str(t["value"]))
                elif isinstance(t, str):
                    tags.append(t)

            samples.append(
                RawSampleItem(
                    origin="sanity",
                    remote_id=doc_id,
                    title=doc.get("title") or doc_id,
                    tags=tags,
                    published_at=parse_iso_datetime(doc.get("publishedAt")),
                    content=content,
                    meta_sanity_id=doc_id,
                )
            )

        return samples
    finally:
        if should_close:
            await client.aclose()


def fetch_local_samples(blogs_dir: str | Path) -> list[RawSampleItem]:
    """Scan local blogs directory for markdown articles and resolve meta mappings."""
    base_path = Path(blogs_dir)
    if not base_path.exists() or not base_path.is_dir():
        logger.warning(f"Blogs directory does not exist: {base_path}")
        return []

    # Check for .publish-meta.json
    publish_meta: dict[str, Any] = {}
    meta_file = base_path / ".publish-meta.json"
    if meta_file.is_file():
        try:
            publish_meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read .publish-meta.json: {e}")

    samples: list[RawSampleItem] = []
    for md_path in base_path.rglob("*.md"):
        # Skip files in hidden directories
        if any(part.startswith(".") for part in md_path.parts):
            continue

        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read {md_path}: {e}")
            continue

        if not content.strip():
            continue

        rel_path = md_path.relative_to(base_path)
        rel_str = str(rel_path).replace("\\", "/")
        rel_no_ext = rel_str[:-3] if rel_str.endswith(".md") else rel_str

        # Resolve Sanity ID mapping if known
        meta_entry = publish_meta.get(rel_no_ext) or publish_meta.get(rel_str)
        meta_sanity_id = meta_entry.get("sanity") if isinstance(meta_entry, dict) else None

        # Extract title from first H1 or filename
        title = md_path.stem.replace("_", " ").replace("-", " ").title()
        for line in content.split("\n"):
            m = re.match(r"^#\s+(.+)$", line)
            if m:
                title = m.group(1).strip()
                break

        # Derive tags from parent directories
        tags = [p for p in rel_path.parent.parts if p and not p.startswith(".")]

        samples.append(
            RawSampleItem(
                origin="local",
                remote_id=rel_str,
                title=title,
                tags=tags,
                published_at=None,
                content=content,
                meta_sanity_id=meta_sanity_id,
            )
        )

    return samples
