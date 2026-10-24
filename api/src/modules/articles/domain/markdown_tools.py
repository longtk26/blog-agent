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


# --- reading an assembled article back (owner edits, revision comparison) ---------------------

INTRO = "Introduction"
_STEP_HEADING = re.compile(r"^step\s+\d+\s*[:.\-]", re.IGNORECASE)
_NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*[.)]?\s")


@dataclass
class ArticleParts:
    title: str
    intro: str
    sections: list[tuple[str, str]]   # (H2 heading text as written, body)
    references: str | None


def split_article(markdown: str) -> ArticleParts:
    """Inverse of `assemble_article`: H1 title, intro, H2 sections (TOC dropped, `---` separators trimmed)."""
    title, intro_lines = "", []
    sections: list[tuple[str, list[str]]] = []
    references: list[str] | None = None
    current: list[str] | None = intro_lines
    in_fence = False
    for line in markdown.replace("\r\n", "\n").split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            h1 = re.match(r"^#\s+(.*?)\s*#*\s*$", line)
            h2 = re.match(r"^##\s+(.*?)\s*#*\s*$", line)
            if h1 and not title and not sections:
                title = heading_text(h1.group(1))
                continue
            if h2:
                text = h2.group(1).strip()
                plain = heading_text(text)
                if plain == "Table of Contents":
                    current = None
                elif plain == "References":
                    references = []
                    current = references
                else:
                    sections.append((text, []))
                    current = sections[-1][1]
                continue
        if current is not None:
            current.append(line)

    def body(lines: list[str]) -> str:
        text = "\n".join(lines).strip()
        text = re.sub(r"^(?:---\s*\n+)+", "", text)
        return re.sub(r"(?:\n+---\s*)+$", "", text).strip()

    return ArticleParts(
        title=title,
        intro=body(intro_lines),
        sections=[(heading, body(lines)) for heading, lines in sections],
        references=body(references) if references is not None else None,
    )


def heading_style_of(heading: str) -> str:
    if _STEP_HEADING.match(heading):
        return "step"
    return "numbered" if _NUMBERED_HEADING.match(heading) else "plain"


def section_name(heading: str) -> str:
    return strip_heading_number(heading_text(heading))


def _named_bodies(markdown: str) -> dict[str, str]:
    parts = split_article(markdown)
    # Compared after tidy_markdown: soft-wrapped vs joined lines render identically on the site.
    bodies = {"Title": parts.title, INTRO: tidy_markdown(parts.intro)}
    for heading, text in parts.sections:
        bodies[section_name(heading)] = tidy_markdown(text)
    bodies["References"] = tidy_markdown(parts.references or "")
    return bodies


def changed_sections(before: str, after: str) -> list[str]:
    """Names of the sections (plus Title/Introduction/References) whose rendered text differs, in article order."""
    old, new = _named_bodies(before), _named_bodies(after)
    names = list(new) + [name for name in old if name not in new]
    return [name for name in names if old.get(name) != new.get(name)]


def draft_sections_from_markdown(markdown: str, existing: list[DraftSection]) -> list[DraftSection]:
    """Owner-edited markdown -> working-draft sections, keeping keys/goals/claim maps of sections that still exist."""
    parts = split_article(markdown)
    by_name = {section_name(s.heading): s for s in existing if s.heading}
    intro = next((s for s in existing if s.key == "intro"), None)
    used_numbers = [int(s.key[1:]) for s in existing if re.fullmatch(r"s\d+", s.key)]
    next_number = max(used_numbers, default=0) + 1

    sections = [
        DraftSection(
            key="intro",
            heading=None,
            heading_style="plain",
            goal=intro.goal if intro else "",
            markdown=parts.intro,
            claim_map=intro.claim_map if intro and intro.markdown == parts.intro else [],
            revisions=intro.revisions if intro else 0,
        )
    ]
    seen: set[str] = set()
    for heading, text in parts.sections:
        name = section_name(heading)
        match = by_name.get(name) if name not in seen else None
        seen.add(name)
        if match is None:
            key, goal, claim_map, revisions = f"s{next_number}", "", [], 0
            next_number += 1
        else:
            key, goal, revisions = match.key, match.goal, match.revisions
            claim_map = match.claim_map if match.markdown == text else []
        sections.append(
            DraftSection(
                key=key, heading=name, heading_style=heading_style_of(heading), goal=goal,
                markdown=text, claim_map=claim_map, revisions=revisions,
            )
        )
    return sections
