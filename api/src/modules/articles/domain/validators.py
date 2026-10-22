"""Deterministic checks of a draft against the render contract and the task's requirements (no LLM)."""

import ast
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from markdown_it import MarkdownIt

from src.modules.articles.domain.markdown_tools import Heading, extract_headings
from src.modules.shared.domain.entities import ArticleMetadata, IssueSeverity, ValidationIssue

B, W, I = IssueSeverity.BLOCKER, IssueSeverity.WARNING, IssueSeverity.INFO

SUPPORTED_LANGUAGES = {"bash", "sh", "shell", "python", "py", "typescript", "ts", "javascript", "js", "json", "java", "markdown", "md", "text", "mermaid"}
MERMAID_STARTS = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram", "mindmap", "timeline", "gantt", "pie", "journey", "quadrantChart")
ALLOWED_HTML = {"b", "br", "sub", "sup", "details", "summary", "strong", "em", "code", "kbd"}
DANGEROUS_HTML = {"script", "iframe", "style", "object", "embed", "form", "input", "link", "meta", "svg", "img"}
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
TAG_PATTERN = re.compile(r"^[a-z0-9]{2,25}$")
CLOSING_HEADINGS = ("summary", "conclusion", "what's next", "whats next", "recommendation", "wrap-up", "takeaways")

_MD = MarkdownIt("commonmark").enable("table")
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")
_TAG = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>")
_EVENT_ATTR = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)


@dataclass
class ValidationContext:
    format: str
    metadata: ArticleMetadata | None
    source_urls: set[str] = field(default_factory=set)
    must_cover: list[str] = field(default_factory=list)
    covered_requirements: set[str] = field(default_factory=set)
    expected_words: int | None = None
    site_url_prefix: str = "https://leon-pham.vercel.app/"


def _issue(rule: str, severity: IssueSeverity, message: str, line: int | None = None, section: str | None = None) -> ValidationIssue:
    return ValidationIssue(rule=rule, severity=severity, message=message, line=line, section=section)


def _section_for_line(headings: list[Heading], line: int | None) -> str | None:
    if line is None:
        return None
    current = None
    for heading in headings:
        if heading.line > line:
            break
        if heading.level == 2:
            current = heading.text
    return current


def _prose_lines(markdown: str) -> list[tuple[int, str]]:
    """(line number, text) for lines outside code fences."""
    result, in_fence = [], False
    for number, line in enumerate(markdown.split("\n"), start=1):
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if not in_fence:
            result.append((number, line))
    return result


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{(parts.hostname or '').lower()}{parts.path.rstrip('/')}"


def check_headings(markdown: str, headings: list[Heading]) -> list[ValidationIssue]:
    issues = []
    h1 = [h for h in headings if h.level == 1]
    first_content = next((n for n, line in enumerate(markdown.split("\n"), start=1) if line.strip()), None)
    if len(h1) != 1:
        issues.append(_issue("H1_COUNT", B, f"Exactly one H1 title is required (found {len(h1)})"))
    if not h1 or h1[0].line != first_content:
        issues.append(_issue("H1_FIRST", B, "The first line must be the '# Title'", line=first_content))
    previous = 1
    for heading in headings:
        if heading.level > previous + 1:
            issues.append(_issue("HEADING_SKIP", W, f"Heading level jumps from H{previous} to H{heading.level}: '{heading.text}'", heading.line))
        previous = heading.level
    return issues


def check_anchors(markdown: str, headings: list[Heading]) -> list[ValidationIssue]:
    slugs = {h.slug for h in headings}
    issues = []
    for number, line in _prose_lines(markdown):
        for target in _LINK.findall(line):
            if target.startswith("#") and target[1:] not in slugs:
                issues.append(_issue("ANCHOR_BROKEN", B, f"In-page link '{target}' does not match any heading", number))
    return issues


def check_fences(markdown: str) -> list[ValidationIssue]:
    issues, open_line, language = [], None, ""
    for number, line in enumerate(markdown.split("\n"), start=1):
        match = re.match(r"^\s*(```|~~~)\s*([^\s`]*)", line)
        if not match:
            continue
        if open_line is None:
            open_line, language = number, match.group(2).lower()
            if not language:
                issues.append(_issue("FENCE_NO_LANG", W, "Code fence has no language (use `text` for plain output)", number))
            elif language not in SUPPORTED_LANGUAGES:
                issues.append(_issue("FENCE_LANG", W, f"'{language}' is not highlighted on the site (falls back to markdown)", number))
        else:
            open_line = None
    if open_line is not None:
        issues.append(_issue("FENCE_UNCLOSED", B, "Code fence is never closed", open_line))
    return issues


def code_blocks(markdown: str) -> list[tuple[int, str, str]]:
    """(start line, language, code) for every fenced block."""
    return [
        ((token.map or [0])[0] + 1, (token.info or "").strip().split(" ")[0].lower(), token.content)
        for token in _MD.parse(markdown)
        if token.type == "fence"
    ]


def check_code(markdown: str) -> list[ValidationIssue]:
    issues = []
    for line, language, code in code_blocks(markdown):
        if language in ("python", "py"):
            # Notebook magics (!pip, %time) are fine in tutorials.
            source = "\n".join("" if re.match(r"^\s*[!%]", row) else row for row in code.split("\n"))
            try:
                ast.parse(source)
            except SyntaxError as exc:
                issues.append(_issue("PYTHON_SYNTAX", W, f"Python block does not parse: {exc.msg} (line {exc.lineno})", line))
        elif language == "json":
            try:
                json.loads(code)
            except json.JSONDecodeError as exc:
                issues.append(_issue("JSON_SYNTAX", W, f"JSON block is invalid: {exc.msg}", line))
        elif language == "mermaid":
            first = next((row.strip() for row in code.split("\n") if row.strip() and not row.strip().startswith("%%")), "")
            if not first.startswith(MERMAID_STARTS):
                issues.append(_issue("MERMAID_TYPE", W, f"Mermaid block starts with '{first[:30]}', not a known diagram type", line))
            if code.count("[") != code.count("]") or code.count("(") != code.count(")"):
                issues.append(_issue("MERMAID_BRACKETS", W, "Mermaid block has unbalanced brackets", line))
    return issues


def check_links(markdown: str, ctx: ValidationContext) -> list[ValidationIssue]:
    issues, sources = [], {_normalize_url(u) for u in ctx.source_urls}
    for number, line in _prose_lines(markdown):
        for target in _LINK.findall(line):
            if target.startswith("#") or target.startswith("mailto:"):
                continue
            if not re.match(r"^https?://", target):
                issues.append(_issue("LINK_RELATIVE", B, f"Link '{target}' is not absolute (posts are routed by id; use https:// URLs)", number))
            elif not target.startswith(ctx.site_url_prefix) and _normalize_url(target) not in sources:
                issues.append(_issue("LINK_NOT_SOURCE", W, f"Link {target} is not one of the research sources", number))
        for target in _IMAGE.findall(line):
            if not re.match(r"^(https://|asset://)", target):
                issues.append(_issue("IMAGE_URL", B, f"Image '{target}' must be an absolute https:// URL", number))
    return issues


def check_blocks(markdown: str) -> list[ValidationIssue]:
    """The site joins adjacent text lines, so images/HTML/labels need blank lines around them."""
    issues = []
    lines = _prose_lines(markdown)
    for (prev_no, prev), (number, line) in zip(lines, lines[1:]):
        if number != prev_no + 1 or not prev.strip() or not line.strip():
            continue
        if re.match(r"\s*(!\[|<(?!br)[a-z])", line) and not re.match(r"\s*([-*+]|\d+\.|#|\||>)", prev):
            issues.append(_issue("BLOCK_SPACING", W, "Image/HTML line directly follows text; add a blank line or it merges into the paragraph", number))
    if markdown.count("$$") % 2:
        issues.append(_issue("MATH_UNBALANCED", W, "Unbalanced $$ display-math delimiters"))
    return issues


def check_html(markdown: str) -> list[ValidationIssue]:
    issues = []
    for number, line in _prose_lines(markdown):
        stripped = re.sub(r"`[^`]*`", "", line)
        for tag, attrs in _TAG.findall(stripped):
            name = tag.lower()
            if name in DANGEROUS_HTML or _EVENT_ATTR.search(" " + attrs):
                issues.append(_issue("HTML_UNSAFE", B, f"Disallowed HTML <{name}>", number))
            elif name not in ALLOWED_HTML:
                issues.append(_issue("HTML_TAG", W, f"HTML <{name}> is outside the render contract", number))
    return issues


def check_structure(headings: list[Heading], ctx: ValidationContext) -> list[ValidationIssue]:
    issues = []
    h2 = [h.text.lower() for h in headings if h.level == 2]
    if "table of contents" not in h2:
        issues.append(_issue("SECTION_TOC", B, "Missing '## Table of Contents'"))
    if "references" not in h2:
        issues.append(_issue("SECTION_REFERENCES", B, "Missing '## References'"))
    if not any(any(word in text for word in CLOSING_HEADINGS) for text in h2):
        issues.append(_issue("SECTION_CLOSING", B, "Missing a closing section (Summary & What's Next / Conclusion)"))
    if ctx.format == "tutorial" and not any("troubleshooting" in text for text in h2):
        issues.append(_issue("SECTION_TROUBLESHOOTING", W, "Tutorials end with a 'Troubleshooting & Pro Tips' table"))
    for requirement in ctx.must_cover:
        if requirement not in ctx.covered_requirements:
            issues.append(_issue("MUST_COVER", W, f"Requirement not mapped to any section: '{requirement}'"))
    return issues


def check_metadata(markdown: str, headings: list[Heading], ctx: ValidationContext) -> list[ValidationIssue]:
    meta = ctx.metadata
    if meta is None:
        return [_issue("META_MISSING", B, "Article metadata (title, description, tags, slug) is missing")]
    issues = []
    h1 = next((h.text for h in headings if h.level == 1), None)
    if h1 != meta.title:
        issues.append(_issue("META_TITLE", B, f"Metadata title '{meta.title}' differs from the H1 '{h1}'"))
    if not meta.description.strip() or len(meta.description) > 160:
        issues.append(_issue("META_DESCRIPTION", B, f"Description must be 1-160 characters (has {len(meta.description)})"))
    if not 1 <= len(meta.tags) <= 4 or not all(TAG_PATTERN.match(t) for t in meta.tags):
        issues.append(_issue("META_TAGS", B, "Tags must be 1-4 lowercase alphanumeric words (DEV Community rules)"))
    if not SLUG_PATTERN.match(meta.slug):
        issues.append(_issue("META_SLUG", B, f"Slug '{meta.slug}' must match [a-z0-9-], 3-80 chars"))
    return issues


def check_length(markdown: str, ctx: ValidationContext) -> list[ValidationIssue]:
    if not ctx.expected_words:
        return []
    words = len(re.findall(r"\w+", "\n".join(line for _, line in _prose_lines(markdown))))
    ratio = words / ctx.expected_words
    if ratio < 0.7 or ratio > 1.3:
        return [_issue("WORD_COUNT", I, f"{words} words vs ~{ctx.expected_words} planned ({ratio:.0%})")]
    return []


def validate_article(markdown: str, ctx: ValidationContext) -> list[ValidationIssue]:
    headings = extract_headings(markdown)
    issues = [
        *check_headings(markdown, headings),
        *check_anchors(markdown, headings),
        *check_fences(markdown),
        *check_code(markdown),
        *check_links(markdown, ctx),
        *check_blocks(markdown),
        *check_html(markdown),
        *check_structure(headings, ctx),
        *check_metadata(markdown, headings, ctx),
        *check_length(markdown, ctx),
    ]
    for issue in issues:
        if issue.section is None:
            issue.section = _section_for_line(headings, issue.line)
    return issues


def has_blockers(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == IssueSeverity.BLOCKER for issue in issues)
