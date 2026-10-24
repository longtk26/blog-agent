import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from src.modules.shared.domain.entities import ArticleRevisionEntity


SANITY_CDN_IMAGE_REGEX = re.compile(
    r"/images/[^/]+/[^/]+/([a-zA-Z0-9]+)-([0-9x]+)\.([a-zA-Z0-9]+)"
)

# Match markdown images: ![alt](image_src "optional title")
MARKDOWN_IMAGE_REGEX = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+[\"'](?P<title>[^\"']*)[\"'])?\)"
)


class IAssetUploader(Protocol):
    async def upload_asset(self, src: str, alt: str = "", title: str = "") -> tuple[str, str]:
        """Upload asset and return (asset_ref, cdn_url)."""
        ...


@dataclass
class RenderForSanityResult:
    rendered_markdown: str
    rendered_content_hash: str
    cover_image_asset_ref: str | None
    images: list[dict[str, Any]]


def extract_sanity_asset_ref(cdn_url: str) -> str | None:
    match = SANITY_CDN_IMAGE_REGEX.search(cdn_url)
    if match:
        return f"image-{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


async def render_for_sanity(
    revision: ArticleRevisionEntity,
    uploader: IAssetUploader | None = None,
    on_asset_uploaded: Callable[[str, str, str], None] | None = None,
) -> RenderForSanityResult:
    """Pure and deterministic render transform. The revision itself is never modified."""
    markdown = revision.markdown
    matches = list(MARKDOWN_IMAGE_REGEX.finditer(markdown))

    cache: dict[str, tuple[str, str]] = {}
    image_replacements: list[tuple[str, str, str, str | None, str, str]] = []
    # (raw_match, alt, src, title, cdn_url, asset_ref)

    for m in matches:
        raw_match = m.group(0)
        alt = m.group("alt")
        src = m.group("src")
        title = m.group("title")

        # 1. Existing Sanity CDN URL
        if src.startswith("https://cdn.sanity.io/images/"):
            asset_ref = extract_sanity_asset_ref(src)
            if asset_ref:
                image_replacements.append((raw_match, alt, src, title, src, asset_ref))
                continue

        # 2. Remote URL or data URL without uploader
        if (src.startswith("http://") or src.startswith("https://") or src.startswith("data:")) and not uploader:
            continue

        # 3. Upload via uploader if available
        if uploader is not None:
            if src not in cache:
                asset_ref, cdn_url = await uploader.upload_asset(src, alt=alt, title=title or "")
                cache[src] = (asset_ref, cdn_url)
                if on_asset_uploaded:
                    on_asset_uploaded(src, asset_ref, cdn_url)
            else:
                asset_ref, cdn_url = cache[src]

            image_replacements.append((raw_match, alt, src, title, cdn_url, asset_ref))

    # Replace occurrences in markdown
    rendered_markdown = markdown
    for raw_match, alt, src, title, new_url, _ in image_replacements:
        title_part = f' "{title}"' if title else ""
        replacement = f"![{alt}]({new_url}{title_part})"
        rendered_markdown = rendered_markdown.replace(raw_match, replacement)

    # Build images[] array with stable keys
    images_array: list[dict[str, Any]] = []
    for _, alt, _, title, _, asset_ref in image_replacements:
        stable_key = f"img_{hashlib.sha256(asset_ref.encode('utf-8')).hexdigest()[:12]}"
        images_array.append(
            {
                "_key": stable_key,
                "_type": "image",
                "asset": {
                    "_type": "reference",
                    "_ref": asset_ref,
                },
                "alt": alt or "",
                "caption": title or "",
            }
        )

    # Choose cover: specified in metadata or first image
    cover_ref: str | None = None
    meta_cover = revision.metadata.get("cover_image") if revision.metadata else None
    if meta_cover and isinstance(meta_cover, str):
        # Match against uploaded assets
        matched = next((ref for _, _, src, _, _, ref in image_replacements if meta_cover in (src, ref)), None)
        cover_ref = matched or meta_cover
    elif image_replacements and len(image_replacements[0]) > 5:
        cover_ref = image_replacements[0][5]

    rendered_hash = hashlib.sha256(rendered_markdown.encode("utf-8")).hexdigest()

    return RenderForSanityResult(
        rendered_markdown=rendered_markdown,
        rendered_content_hash=rendered_hash,
        cover_image_asset_ref=cover_ref,
        images=images_array,
    )
