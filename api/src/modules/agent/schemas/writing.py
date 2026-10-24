"""Structured outputs for outlining, drafting and judging. Limits are enforced in `normalize_*`, not in the schema."""

import re
from typing import Literal

from pydantic import BaseModel, Field

SectionNeed = Literal["code", "table", "diagram", "math", "analogy", "troubleshooting_table", "summary_table"]


class OutlineSectionOut(BaseModel):
    heading: str = Field(description="Section heading text WITHOUT numbering (numbering is added automatically)")
    heading_style: Literal["numbered", "step", "plain"] = Field(
        default="numbered", description="numbered = '## 2. Heading'; step = '## Step 3: Heading' (tutorial steps); plain = no number"
    )
    goal: str = Field(description="What the reader understands or can do after this section")
    key_points: list[str] = Field(description="3-6 points the section must make")
    claim_refs: list[str] = Field(default_factory=list, description="Evidence refs like C4 this section relies on")
    needs: list[SectionNeed] = Field(default_factory=list, description="Elements this section should include")
    est_words: int = Field(description="Target length in words")


class RequirementMapOut(BaseModel):
    requirement: str
    section_index: int = Field(description="0-based index into `sections`")


class OutlineOut(BaseModel):
    title_options: list[str] = Field(description="3 candidate titles in the owner's style")
    angle: str = Field(description="One sentence: the article's angle and promise to the reader")
    intro_goal: str = Field(description="What the 1-2 framing intro paragraphs must establish")
    sections: list[OutlineSectionOut]
    requirement_map: list[RequirementMapOut] = Field(default_factory=list, description="Where each must-cover requirement is handled")
    next_steps: str = Field(default="", description="What the closing section points readers to next")


class ClaimMapEntryOut(BaseModel):
    sentence: str = Field(description="The factual sentence (or its first ~15 words) as written in the section")
    claim_refs: list[str] = Field(default_factory=list, description="Evidence refs like C4 that support it")
    support: Literal["supported", "partial", "unsupported"]


class SectionDraftOut(BaseModel):
    markdown: str = Field(description="The section body in Markdown, WITHOUT the '## ' section heading line")
    claim_map: list[ClaimMapEntryOut] = Field(default_factory=list, description="Every factual statement and its evidence")


class MetadataOut(BaseModel):
    title: str
    description: str = Field(description="Plain-text summary for previews and SEO, at most 160 characters")
    tags: list[str] = Field(description="1-4 lowercase alphanumeric tags (no spaces or dashes), most specific first")
    slug: str = Field(description="URL slug: lowercase words joined by dashes, at most 80 characters")


class FeedbackRouteOut(BaseModel):
    target: Literal["research", "outline", "draft", "diagram", "metadata"]
    sections: list[str] = Field(default_factory=list, description="Affected section names exactly as listed; empty = whole article")
    reason: str = Field(default="", description="One sentence: why this stage")


class JudgeScoresOut(BaseModel):
    factual_support: int = Field(description="1-5: claims are backed by the evidence")
    depth_fit: int = Field(description="1-5: matches the requested depth")
    audience_fit: int = Field(description="1-5: right level for the stated audience")
    requirements_coverage: int = Field(description="1-5: covers every owner requirement")
    style_adherence: int = Field(description="1-5: follows the owner's style guide")
    clarity: int = Field(description="1-5: clear structure and explanations")


class JudgeIssueOut(BaseModel):
    section: str | None = Field(default=None, description="Heading text of the affected section, exactly as in the article")
    severity: Literal["blocker", "warning", "info"]
    problem: str
    suggested_fix: str


class JudgeReportOut(BaseModel):
    scores: JudgeScoresOut
    issues: list[JudgeIssueOut] = Field(default_factory=list)
    unsupported_statements: list[str] = Field(default_factory=list, description="Statements not backed by the evidence")
    summary: str = Field(description="Two sentences: overall assessment")


def normalize_outline(outline: OutlineOut, max_sections: int) -> OutlineOut:
    sections = [s for s in outline.sections if s.heading.strip()][:max_sections]
    for section in sections:
        section.est_words = max(80, min(int(section.est_words or 300), 1500))
        section.key_points = [p for p in section.key_points if p.strip()][:8]
    outline.sections = sections
    outline.requirement_map = [m for m in outline.requirement_map if 0 <= m.section_index < len(sections)]
    outline.title_options = [t.strip() for t in outline.title_options if t.strip()][:3] or [sections[0].heading if sections else "Untitled"]
    return outline


def slugify(text: str, max_length: int = 80) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]
    return slug or "article"


def normalize_metadata(meta: MetadataOut, h1: str) -> MetadataOut:
    description = " ".join(meta.description.replace("\n", " ").split())
    if len(description) > 160:
        description = description[:157].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    tags: list[str] = []
    for tag in meta.tags:
        clean = re.sub(r"[^a-z0-9]", "", tag.lower())
        if 2 <= len(clean) <= 25 and clean not in tags:
            tags.append(clean)
    return MetadataOut(
        title=h1,
        description=description,
        tags=tags[:4] or ["programming"],
        slug=slugify(meta.slug or h1),
    )


def normalize_judge(report: JudgeReportOut) -> JudgeReportOut:
    for name in JudgeScoresOut.model_fields:
        setattr(report.scores, name, max(1, min(5, int(getattr(report.scores, name) or 1))))
    report.issues = report.issues[:20]
    report.unsupported_statements = report.unsupported_statements[:20]
    return report
