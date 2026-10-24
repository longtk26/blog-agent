import pytest

from src.modules.articles.domain.content_hash import compute_content_hash
from src.modules.articles.domain.validators import ValidationContext, validate_article
from src.modules.agent.schemas.writing import (
    JudgeReportOut,
    JudgeScoresOut,
    MetadataOut,
    normalize_judge,
    normalize_metadata,
    slugify,
)
from src.modules.shared.domain.entities import ArticleMetadata

META = ArticleMetadata(title="T", slug="good-slug", description="Short.", tags=["llm"])
BASE = "# T\n\nIntro.\n\n## Table of Contents\n\n1. [1. A](#1-a)\n\n## 1. A\n\n{body}\n\n## 2. Summary & What's Next\n\nDone.\n\n## References\n\n1. [S](https://src.org/a)\n"


def rules(markdown: str, **ctx) -> dict[str, str]:
    context = ValidationContext(format=ctx.pop("format", "concept"), metadata=ctx.pop("metadata", META), source_urls={"https://src.org/a"}, **ctx)
    return {issue.rule: issue.severity for issue in validate_article(markdown, context)}


def test_clean_article_has_no_issues():
    assert rules(BASE.format(body="Text with [a source](https://src.org/a).")) == {}


@pytest.mark.parametrize(
    ("body", "rule", "severity"),
    [
        ("```python\nx = (\n```", "PYTHON_SYNTAX", "warning"),
        ("```json\n{bad}\n```", "JSON_SYNTAX", "warning"),
        ("```\nplain\n```", "FENCE_NO_LANG", "warning"),
        ("```yaml\na: 1\n```", "FENCE_LANG", "warning"),
        ("```python\nx = 1", "FENCE_UNCLOSED", "blocker"),
        ("See [part 2](part2.md).", "LINK_RELATIVE", "blocker"),
        ("See [other](https://elsewhere.com/x).", "LINK_NOT_SOURCE", "warning"),
        ("![diagram](./diagram.svg)", "IMAGE_URL", "blocker"),
        ("Text\n![d](https://cdn.x/a.png)", "BLOCK_SPACING", "warning"),
        ("<script>alert(1)</script>", "HTML_UNSAFE", "blocker"),
        ('<b onclick="x()">hi</b>', "HTML_UNSAFE", "blocker"),
        ("<div>box</div>", "HTML_TAG", "warning"),
        ("Jump to [missing](#nowhere).", "ANCHOR_BROKEN", "blocker"),
        ("#### Too deep", "HEADING_SKIP", "warning"),
        ("$$\nx^2", "MATH_UNBALANCED", "warning"),
        ("$$x^2 + y^2$$", "MATH_INLINE_DISPLAY", "warning"),
        ("```mermaid\nnot a diagram\n```", "MERMAID_TYPE", "warning"),
    ],
)
def test_rule_violations(body, rule, severity):
    assert rules(BASE.format(body=body)).get(rule) == severity


def test_notebook_magics_and_valid_mermaid_pass():
    body = "```python\n!pip install peft\nimport peft\n```\n\n```mermaid\nflowchart LR\n    A[\"<b>x</b>\"] --> B\n```\n\n$$\nx^2\n$$"
    assert rules(BASE.format(body=body)) == {}


def test_structure_and_metadata_rules():
    no_refs = BASE.format(body="x").split("## References")[0]
    assert rules(no_refs)["SECTION_REFERENCES"] == "blocker"
    assert rules(BASE.replace("Summary & What's Next", "More").format(body="x"))["SECTION_CLOSING"] == "blocker"
    assert rules(BASE.format(body="x"), format="tutorial")["SECTION_TROUBLESHOOTING"] == "warning"
    assert rules("Intro first\n\n" + BASE.format(body="x"))["H1_FIRST"] == "blocker"
    bad_meta = ArticleMetadata(title="Other", slug="Bad Slug", description="x" * 161, tags=["Not OK", "a", "b", "c", "d"])
    found = rules(BASE.format(body="x"), metadata=bad_meta)
    assert {"META_TITLE", "META_SLUG", "META_DESCRIPTION", "META_TAGS"} <= set(found)
    assert rules(BASE.format(body="x"), must_cover=["memory"], covered_requirements=set())["MUST_COVER"] == "warning"


def test_content_hash_is_stable_and_sensitive():
    args = dict(title="T", slug="s", description="d", tags=["a"], markdown="# T\n")
    assert compute_content_hash(**args) == compute_content_hash(**{**args, "markdown": "# T\r\n"})
    for change in ({"title": "T2"}, {"slug": "s2"}, {"tags": ["b"]}, {"markdown": "# T!\n"}, {"diagram_asset_hashes": ["h"]}):
        assert compute_content_hash(**args) != compute_content_hash(**{**args, **change})


def test_metadata_normalization():
    meta = normalize_metadata(
        MetadataOut(title="ignored", description="word " * 60, tags=["#LLM", "Fine-Tuning", "llm", "x", "rag", "ai", "more"], slug="LoRA: Fine Tuning!!"),
        "LoRA Explained",
    )
    assert meta.title == "LoRA Explained"
    assert len(meta.description) <= 160 and meta.description.endswith("…")
    assert meta.tags == ["llm", "finetuning", "rag", "ai"]
    assert meta.slug == "lora-fine-tuning"
    assert slugify("a" * 100).__len__() <= 80


def test_judge_scores_are_clamped():
    report = normalize_judge(
        JudgeReportOut(scores=JudgeScoresOut(factual_support=9, depth_fit=0, audience_fit=3, requirements_coverage=3, style_adherence=3, clarity=3), summary="ok")
    )
    assert report.scores.factual_support == 5 and report.scores.depth_fit == 1
