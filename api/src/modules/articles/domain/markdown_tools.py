"""Deterministic Markdown helpers matching how profile-ui renders posts (rehype-slug / github-slugger)."""

import re
import unicodedata
from dataclasses import dataclass

from src.modules.shared.domain.entities import DraftSection

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_MARKUP = re.compile(r"(\*\*|__|\*|_|`|~~)")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_LEADING_NUMBER = re.compile(r"^\s*(?:step\s+\d+\s*[:.\-]|\d+(?:\.\d+)*[.)]?)\s*", re.IGNORECASE)


def heading_text(raw: str) -> str:
    """Visible text of a heading line's content (markdown/links/html stripped), like hast-util-to-string."""
    text = _LINK.sub(r"\1", raw)
    text = _HTML_TAG.sub("", text)
    text = _INLINE_MARKUP.sub("", text)
    return text.strip()


class Slugger:
    """Port of github-slugger: lowercase, drop punctuation/symbols, spaces -> '-', de-duplicate with -1, -2."""

    def __init__(self):
        self.seen: dict[str, int] = {}

    @staticmethod
    def base(text: str) -> str:
        kept = []
        for char in text.lower():
            category = unicodedata.category(char)
            if char in (" ", "-", "_") or category[0] in ("L", "N") or category in ("Mn", "Mc"):
                kept.append(char)
        return "".join(kept).replace(" ", "-")

    def slug(self, text: str) -> str:
        slug = self.base(text)
        original = slug
        while slug in self.seen:
            self.seen[original] += 1
            slug = f"{original}-{self.seen[original]}"
        self.seen[slug] = 0
        return slug


def strip_heading_number(heading: str) -> str:
    """LLMs often prefix headings with numbers; numbering is applied deterministically instead."""
    return _LEADING_NUMBER.sub("", heading).strip() or heading.strip()


def _is_block_start(line: str) -> bool:
    stripped = line.lstrip()
    return bool(
        re.match(r"([-*+]\s|\d+[.)]\s|#{1,6}\s|>|\||\$|!\[|<|---\s*$|\*\*\*\s*$)", stripped)
    )


def tidy_markdown(text: str) -> str:
    """Normalise LLM output to the render contract: LF newlines, blank line around fences, headings,
    tables, images and HTML; soft-wrapped paragraph lines joined (the site joins them anyway)."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n")
    out: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE.match(line):
            if not in_fence and out and out[-1].strip():
                out.append("")
            out.append(line.rstrip())
            in_fence = not in_fence
            if not in_fence:
                out.append("")
            continue
        if in_fence:
            out.append(line.rstrip())
            continue
        line = line.rstrip()
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        previous = out[-1] if out else ""
        stripped = line.lstrip()
        in_table, prev_in_table = stripped.startswith("|"), previous.lstrip().startswith("|")
        # a table must start and end on a block boundary, or GFM swallows the neighbouring line
        needs_gap = re.match(r"(#{1,6}\s|!\[|<|---\s*$)", stripped) or (in_table != prev_in_table and previous)
        if previous and needs_gap:
            out.append("")
        elif previous and not _is_block_start(previous) and not _is_block_start(line) and not line.startswith(" "):
            out[-1] = f"{previous} {stripped}"
            continue
        out.append(line)
        if re.match(r"(#{1,6}\s|!\[|---\s*$)", stripped):
            out.append("")
    while out and out[-1] == "":
        out.pop()
    collapsed: list[str] = []
    in_fence = False
    for line in out:
        if _FENCE.match(line):
            in_fence = not in_fence
        elif line == "" and not in_fence and collapsed and collapsed[-1] == "":
            continue  # code blocks keep their own blank lines
        collapsed.append(line)
    return "\n".join(collapsed)


@dataclass
class Heading:
    level: int
    text: str
    slug: str
    line: int


def extract_headings(markdown: str) -> list[Heading]:
    slugger = Slugger()
    headings: list[Heading] = []
    in_fence = False
    for number, line in enumerate(markdown.split("\n"), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if match:
            text = heading_text(match.group(2))
            headings.append(Heading(len(match.group(1)), text, slugger.slug(text), number))
    return headings


def section_heading(section: DraftSection, index: int, step: int) -> str:
    title = strip_heading_number(section.heading or "")
    if section.heading_style == "step":
        return f"Step {step}: {title}"
    if section.heading_style == "plain":
        return title
    return f"{index}. {title}"


def render_toc(headings: list[Heading]) -> str:
    """Owner style: `1. [What is Fine-Tuning?](#1-what-is-fine-tuning)` (number in the anchor, not the link text)."""
    lines = []
    top = 0
    for heading in headings:
        if heading.level == 2 and heading.text != "Table of Contents":
            top += 1
            lines.append(f"{top}. [{strip_heading_number(heading.text)}](#{heading.slug})")
        elif heading.level == 3 and lines:
            lines.append(f"   - [{heading.text}](#{heading.slug})")
    return "\n".join(lines)


def assemble_article(title: str, sections: list[DraftSection], references: list[dict]) -> str:
    """H1 + intro + generated TOC + numbered sections separated by `---` + References."""
    intro = next((s for s in sections if s.key == "intro"), None)
    body_sections = [s for s in sections if s.key != "intro"]

    steps = 0
    rendered: list[str] = []
    for position, section in enumerate(body_sections, start=1):
        if section.heading_style == "step":
            steps += 1
        # Numbered sections use their position, like "## 10. Troubleshooting" after eight "Step N" sections.
        heading = section_heading(section, position, steps)
        rendered.append(f"## {heading}\n\n{tidy_markdown(section.markdown)}".rstrip())

    reference_lines = [
        f"{index}. [{ref['title'] or ref['url']}]({ref['url']}){f' — {ref['publisher']}' if ref.get('publisher') else ''}"
        for index, ref in enumerate(references, start=1)
    ]
    references_block = "## References\n\n" + ("\n".join(reference_lines) if reference_lines else "_No external sources cited._")

    body = "\n\n---\n\n".join(rendered)
    draft_without_toc = f"# {title}\n\n## Table of Contents\n\n{body}\n\n---\n\n{references_block}"
    toc = render_toc([h for h in extract_headings(draft_without_toc) if h.text != "References"])

    parts = [f"# {title}"]
    if intro and intro.markdown.strip():
        parts.append(tidy_markdown(intro.markdown))
    parts.append(f"## Table of Contents\n\n{toc}")
    parts.append("---")
    parts.append(body)
    parts.append("---")
    parts.append(references_block)
    return "\n\n".join(p.strip() for p in parts if p.strip()) + "\n"
