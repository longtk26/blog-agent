import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Callable

from src.configs import config
from src.configs.logger import get_logger
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer

logger = get_logger(__name__)
from src.modules.publishing.domain.sanity_renderer import IAssetUploader, RenderForSanityResult
from src.modules.shared.domain.entities import ArticleRevisionEntity
from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity


@dataclass
class RenderForDevtoResult:
    title: str
    body_markdown: str
    rendered_content_hash: str
    tags: list[str]
    canonical_url: str | None = None
    main_image: str | None = None
    description: str | None = None


def slugify_devto_heading(heading_text: str) -> str:
    """Forem/Dev.to heading slugification algorithm:
    1. Strip markdown links, formatting (bold, code, italics)
    2. Lowercase
    3. Remove punctuation except hyphens/underscores/whitespace
    4. Replace whitespace and underscores with a single hyphen
    5. Strip leading and trailing hyphens
    """
    text = heading_text.strip()
    # Strip markdown links [label](url) -> label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Strip inline code, bold, italics, strikethrough, html
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    # Lowercase
    text = text.lower()
    # Remove all characters except alphanumeric, whitespace, and hyphens
    text = re.sub(r"[^\w\s-]", "", text)
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Strip leading and trailing hyphens
    return text.strip("-")


def sanitize_devto_tags(tags: list[str] | None) -> list[str]:
    """Dev.to accepts at most 4 tags: lowercase alphanumeric, hyphens allowed, no spaces or '#'."""
    if not tags:
        return []
    clean_tags: list[str] = []
    for t in tags:
        cleaned = re.sub(r"[^\w-]", "", t.lower().lstrip("#")).strip("-")
        if cleaned and cleaned not in clean_tags:
            clean_tags.append(cleaned)
        if len(clean_tags) == 4:
            break
    return clean_tags


def clean_latex_math(math_content: str) -> str:
    """Clean common LaTeX mathematical symbols into readable ASCII/Unicode text."""
    clean = math_content.strip()
    clean = re.sub(r"\\text\{([^}]+)\}", r"\1", clean)
    clean = re.sub(r"\\mathbf\{([^}]+)\}", r"\1", clean)
    clean = re.sub(r"\\mathbb\{R\}\^\{([^}]+)\}", r"R^(\1)", clean)
    clean = re.sub(r"\\mathbb\{R\}", "R", clean)
    clean = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"(\1) / (\2)", clean)
    clean = re.sub(r"\\sqrt\{([^}]+)\}", r"sqrt(\1)", clean)
    clean = re.sub(r"\\sqrt\[([^\]]+)\]\{([^}]+)\}", r"root[\1](\2)", clean)
    clean = re.sub(r"\\left\(", "(", clean)
    clean = re.sub(r"\\right\)", ")", clean)
    clean = re.sub(r"\\left\[", "[", clean)
    clean = re.sub(r"\\right\]", "]", clean)
    clean = re.sub(r"\\times", " * ", clean)
    clean = re.sub(r"\\cdot", " * ", clean)
    clean = re.sub(r"\\Delta\s*", "Δ", clean)
    clean = re.sub(r"\\approx", "~", clean)
    clean = re.sub(r"\\ll", "<<", clean)
    clean = re.sub(r"\\gg", ">>", clean)
    clean = re.sub(r"\\in", "in", clean)
    clean = re.sub(r"\\arg\\max", "argmax", clean)
    clean = re.sub(r"\\pm", "±", clean)
    clean = re.sub(r"\\le|\\leq", "<=", clean)
    clean = re.sub(r"\\ge|\\geq", ">=", clean)
    clean = re.sub(r"\\ne|\\neq", "!=", clean)
    clean = re.sub(r"\\sum", "sum", clean)
    clean = re.sub(r"\\prod", "prod", clean)
    clean = re.sub(r"\\int", "int", clean)
    clean = re.sub(r"\\quad", " ", clean)
    clean = re.sub(r"\\qquad", "   ", clean)
    clean = re.sub(r"\\[,;]", " ", clean)
    clean = re.sub(r"[{}]", "", clean)
    clean = re.sub(r"  +", " ", clean)
    return clean.strip()


def format_math_for_devto(markdown: str, use_katex_liquid: bool = False) -> str:
    """Dev.to does not render standard LaTeX math ($...$ or $$...$$).
    Converts:
    - Block math ($$ ... $$) into fenced ```text code blocks or {% katex %} liquid tags.
    - Inline math ($ ... $) into `...` inline code without modifying existing code blocks.
    """
    # 1. Convert block math ($$ ... $$)
    def replace_block(match: re.Match) -> str:
        raw_math = match.group(1).strip()
        if use_katex_liquid:
            return f"\n{{% katex %}}\n{raw_math}\n{{% endkatex %}}\n"
        cleaned = clean_latex_math(raw_math)
        return f"\n```text\n{cleaned}\n```\n"

    result = re.sub(r"\$\$([\s\S]*?)\$\$", replace_block, markdown)

    # 2. Convert inline math ($ ... $) outside of existing fenced code blocks
    parts = re.split(r"(```[\s\S]*?```)", result)
    for idx, part in enumerate(parts):
        # Leave fenced code blocks untouched
        if idx % 2 == 1:
            continue

        def replace_inline(m: re.Match) -> str:
            raw = m.group(1)
            cleaned = clean_latex_math(raw)
            return f"`{cleaned}`"

        # Match inline $...$ not preceded or followed by backslash or newline
        parts[idx] = re.sub(r"(?<!\\)\$([^\$\n]+?)(?<!\\)\$", replace_inline, part)

    return "".join(parts)


def rewrite_toc_and_headings(markdown: str) -> str:
    """Aligns Table of Contents anchor links with Dev.to heading slugs."""
    # Discover all headings and their Dev.to slugs
    heading_matches = re.finditer(r"^(#{2,6})\s+(.+)$", markdown, re.MULTILINE)
    slug_map: dict[str, str] = {}
    seen_slugs: dict[str, int] = {}

    for m in heading_matches:
        raw_title = m.group(2).strip()
        base_slug = slugify_devto_heading(raw_title)
        if not base_slug:
            continue
        count = seen_slugs.get(base_slug, 0)
        seen_slugs[base_slug] = count + 1
        devto_slug = base_slug if count == 0 else f"{base_slug}-{count}"

        slug_map[raw_title.lower()] = devto_slug
        # Also map standard github/sanitize slug
        gh_slug = re.sub(r"[^\w\s-]", "", raw_title.lower()).replace(" ", "-")
        slug_map[gh_slug] = devto_slug

    # Replace anchor links in markdown: [Text](#anchor)
    def replace_anchor(m: re.Match) -> str:
        label = m.group(1)
        anchor = m.group(2).lower().lstrip("#")
        # Match by anchor or label
        matched_slug = (
            slug_map.get(anchor)
            or slug_map.get(label.lower())
            or slug_map.get(slugify_devto_heading(label))
            or slugify_devto_heading(anchor)
        )
        return f"[{label}](#{matched_slug})"

    return re.sub(r"\[([^\]]+)\]\(#([^)]+)\)", replace_anchor, markdown)


# Epic 14. profile-ui strips this exact line (the site shows images at full size), so keep the wording in sync.
FULL_SIZE_LINK_TEXT = "*[Open the full-size diagram]({url})*"

_MERMAID_FENCE = re.compile(r"(^[ \t]*```mermaid[^\n]*\n)(.*?)(^[ \t]*```[ \t]*$)", re.MULTILINE | re.DOTALL)
_BOLD_TAG = re.compile(r"</?b\s*>", re.IGNORECASE)


def strip_mermaid_bold(markdown: str) -> str:
    """Dev.to's Mermaid shows <b>…</b> in labels as literal text, so drop the tags (keep the words) inside
    ```mermaid fences only. The website renders them, so the stored revision keeps them."""
    return _MERMAID_FENCE.sub(lambda m: m.group(1) + _BOLD_TAG.sub("", m.group(2)) + m.group(3), markdown)


async def render_for_devto(
    revision: ArticleRevisionEntity,
    sanity_render: RenderForSanityResult | None = None,
    canonical_url: str | None = None,
    uploader: IAssetUploader | None = None,
    diagram_renderer: IDiagramRenderer | None = None,
    diagram_assets: list[DiagramAssetEntity] | None = None,
    site_base_url: str | None = None,
    include_footer: bool = True,
    use_katex_liquid: bool = False,
    on_asset_uploaded: Callable[[str, str, str], None] | None = None,
) -> RenderForDevtoResult:
    """Pure and deterministic render transform targeting DEV Community (Forem). E8-S2."""
    base_site_url = (site_base_url or config.sanity_site_base_url).rstrip("/")
    markdown = revision.markdown

    # 1. Remove leading H1 because title is passed as a separate API field
    cleaned_md = re.sub(r"^\s*#\s+[^\n]+\n*", "", markdown)

    # 2. Mermaid diagrams are written directly as native Mermaid code blocks
    # Dev.to (Forem) natively renders ```mermaid ... ``` code blocks with Mermaid.js.
    # Preserve them directly in markdown.
    cleaned_md = strip_mermaid_bold(cleaned_md)
    if uploader:
        asset_img_pattern = re.compile(
            r"!\[([^\]]*)\]\((asset://[^\s)]+|/[^\s)]+\.(?:png|jpe?g|svg|webp))(?:\s+[\"']([^\"']*)[\"'])?\)"
        )
        for m in list(asset_img_pattern.finditer(cleaned_md)):
            full_match = m.group(0)
            alt = m.group(1)
            src = m.group(2)
            title = m.group(3) or alt
            try:
                _, cdn_url = await uploader.upload_asset(src, alt=alt, title=title)
                if on_asset_uploaded:
                    on_asset_uploaded(src, _, cdn_url)
                replacement = f'![{alt}]({cdn_url} "{title}")'
                if src.startswith("asset://"):
                    # DEV shows body images at 800px (re-encoded); link the original so wide diagrams stay readable.
                    replacement += f"\n\n{FULL_SIZE_LINK_TEXT.format(url=cdn_url)}"
                cleaned_md = cleaned_md.replace(full_match, replacement)
            except Exception as exc:
                logger.warning(f"Failed to resolve asset image {src}: {exc}")

    # 3. If sanity_render provided rendered_markdown with CDN image URLs, map them
    if sanity_render and sanity_render.rendered_markdown:
        # Transfer Sanity CDN images if revision markdown had local paths
        sanity_images = re.findall(r"!\[([^\]]*)\]\((https://cdn\.sanity\.io/images/[^)\s]+(?:\s+[\"'][^\"']*[\"'])?)\)", sanity_render.rendered_markdown)
        for alt, full_src in sanity_images:
            cleaned_md = re.sub(
                rf"!\[{re.escape(alt)}\]\([^)]+\)",
                f"![{alt}]({full_src})",
                cleaned_md,
            )

    # 4. Math conversion (KaTeX -> code / liquid)
    cleaned_md = format_math_for_devto(cleaned_md, use_katex_liquid=use_katex_liquid)

    # 5. Table of contents and heading anchor matching
    cleaned_md = rewrite_toc_and_headings(cleaned_md)

    # 6. Rewrite internal /posts/<id> links to absolute site URLs
    cleaned_md = re.sub(r"\]\(/posts/([^)\s]+)\)", rf"]({base_site_url}/posts/\1)", cleaned_md)

    # 7. Add optional canonical publication footer
    resolved_canonical = canonical_url or f"{base_site_url}/posts/{revision.slug}"
    if include_footer and resolved_canonical:
        footer = f"\n\n---\n*Originally published at [{resolved_canonical}]({resolved_canonical})*"
        cleaned_md = cleaned_md.rstrip() + footer

    # 8. Main cover image selection (must be raster PNG/JPG/WebP; SVG is rejected by Dev.to)
    main_image: str | None = None
    cover_candidate = revision.metadata.get("cover_image") if revision.metadata else None
    if not cover_candidate and sanity_render and sanity_render.images:
        cover_candidate = sanity_render.images[0].get("asset", {}).get("_ref")

    # Look for raster image in cleaned_md
    raster_matches = re.findall(
        # optional "title" after the URL: rewritten images are always written as ![alt](url "title")
        r"!\[[^\]]*\]\((https?://[^)\s]+\.(?:png|jpe?g|webp)[^)\s]*)(?:\s+[\"'][^\"']*[\"'])?\)",
        cleaned_md,
        re.IGNORECASE,
    )
    if raster_matches:
        main_image = raster_matches[0]
    elif cover_candidate and isinstance(cover_candidate, str) and not cover_candidate.lower().endswith(".svg"):
        if cover_candidate.startswith("http"):
            main_image = cover_candidate

    clean_tags = sanitize_devto_tags(revision.tags)
    content_hash = hashlib.sha256(cleaned_md.encode("utf-8")).hexdigest()

    return RenderForDevtoResult(
        title=revision.title,
        body_markdown=cleaned_md,
        rendered_content_hash=content_hash,
        tags=clean_tags,
        canonical_url=resolved_canonical,
        main_image=main_image,
        description=revision.description[:160] if revision.description else None,
    )
