import pytest

from src.modules.articles.domain.markdown_tools import (
    Slugger,
    assemble_article,
    extract_headings,
    strip_heading_number,
    tidy_markdown,
)
from src.modules.articles.domain.validators import ValidationContext, validate_article
from src.modules.shared.domain.entities import ArticleMetadata, DraftSection


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("1. What is Fine-Tuning?", "1-what-is-fine-tuning"),
        ("3. Fine-Tuning vs. RAG", "3-fine-tuning-vs-rag"),
        ("Parameter-Efficient Fine-Tuning (PEFT) & LoRA", "parameter-efficient-fine-tuning-peft--lora"),
        ("The Hybrid Approach: RAG + Fine-Tuning", "the-hybrid-approach-rag--fine-tuning"),
        ("1. Temperature ($T$)", "1-temperature-t"),
        ("8. Summary & What's Next", "8-summary--whats-next"),
        ("Stop Tokens (`<|im_end|>`)", "stop-tokens-im_end"),
    ],
)
def test_slugger_matches_github_slugger(heading, slug):
    assert Slugger().slug(heading) == slug


def test_slugger_deduplicates():
    slugger = Slugger()
    assert [slugger.slug("Setup"), slugger.slug("Setup"), slugger.slug("Setup")] == ["setup", "setup-1", "setup-2"]


@pytest.mark.parametrize(
    ("raw", "clean"),
    [("1. Intro", "Intro"), ("Step 3: Train", "Train"), ("2.1 Rank", "Rank"), ("Why LoRA?", "Why LoRA?"), ("3", "3")],
)
def test_strip_heading_number(raw, clean):
    assert strip_heading_number(raw) == clean


def test_tidy_joins_soft_wraps_and_separates_blocks():
    raw = "A sentence that\nwraps here.\n![d](https://x.org/a.png)\nNext para.\n| a | b |\n|---|---|\n| 1 | 2 |\nAfter table.\n```python\nx = 1\n\n\ny = 2\n```\n### Sub\nText"
    tidy = tidy_markdown(raw)
    assert "A sentence that wraps here." in tidy
    assert "\n\n![d](https://x.org/a.png)\n\n" in tidy
    assert "| 1 | 2 |\n\nAfter table." in tidy
    assert "x = 1\n\n\ny = 2" in tidy  # code is untouched
    assert "\n\n### Sub\n\nText" in tidy


def test_tidy_keeps_lists_and_indented_continuations():
    raw = "Intro:\n\n- item one\n  continues\n- item two\n1. first\n2. second"
    assert tidy_markdown(raw) == raw


def test_assembled_article_passes_structure_and_anchor_checks():
    sections = [
        DraftSection(key="intro", heading=None, heading_style="plain", markdown="Why this matters.\n\nIn this guide, we cover LoRA."),
        DraftSection(key="s1", heading="How LoRA Works", markdown="LoRA trains [adapters](https://arxiv.org/abs/2106.09685).\n\n### Rank r\n\nSmall r."),
        DraftSection(key="s2", heading="Train the Adapter", heading_style="step", markdown="```python\nprint('hi')\n```"),
        DraftSection(key="s3", heading="Summary & What's Next", markdown="| Concept | Takeaway |\n| :--- | :--- |\n| LoRA | small |"),
    ]
    markdown = assemble_article("LoRA Explained", sections, [{"title": "LoRA paper", "url": "https://arxiv.org/abs/2106.09685", "publisher": "arXiv"}])
    headings = [h.text for h in extract_headings(markdown)]
    assert headings == ["LoRA Explained", "Table of Contents", "1. How LoRA Works", "Rank r", "Step 1: Train the Adapter", "3. Summary & What's Next", "References"]
    assert "1. [How LoRA Works](#1-how-lora-works)" in markdown
    assert "3. [Summary & What's Next](#3-summary--whats-next)" in markdown
    assert "   - [Rank r](#rank-r)" in markdown
    assert "1. [LoRA paper](https://arxiv.org/abs/2106.09685) — arXiv" in markdown
    issues = validate_article(
        markdown,
        ValidationContext(
            format="concept",
            metadata=ArticleMetadata(title="LoRA Explained", slug="lora-explained", description="LoRA in short.", tags=["llm", "lora"]),
            source_urls={"https://arxiv.org/abs/2106.09685"},
        ),
    )
    assert [i for i in issues if i.severity == "blocker"] == []
