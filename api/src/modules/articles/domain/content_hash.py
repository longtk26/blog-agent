import hashlib
import json


def compute_content_hash(
    *,
    title: str,
    slug: str,
    description: str,
    tags: list[str],
    markdown: str,
    diagram_asset_hashes: list[str] | None = None,
) -> str:
    """SHA-256 over a canonical JSON of everything a reader/publisher sees.

    Computed server-side only; approvals (Epic 4) and publications (Epic 5) bind to this value,
    so any change to text, metadata or diagram assets produces a different hash.
    """
    canonical = json.dumps(
        {
            "title": title,
            "slug": slug,
            "description": description,
            "tags": list(tags),
            "markdown": markdown.replace("\r\n", "\n"),
            "diagram_asset_hashes": sorted(diagram_asset_hashes or []),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
