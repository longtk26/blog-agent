import pytest

from src.modules.articles.domain.markdown_tools import (
    Slugger,
    assemble_article,
    changed_sections,
    draft_sections_from_markdown,
    extract_headings,
    split_article,
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


# --- reading articles back (Epic 4) -----------------------------------------------------------

ARTICLE = """# LoRA Explained

Intro paragraph.

## Table of Contents

1. [How It Works](#1-how-it-works)

---

## 1. How It Works

Body one.

```python
## not a heading
x = 1
```

---

## Step 2: Install

Body two.

---

## References

1. [Paper](https://arxiv.org/abs/2106.09685)
"""


def test_split_article_inverts_assembly():
    parts = split_article(ARTICLE)
    assert parts.title == "LoRA Explained"
    assert parts.intro == "Intro paragraph."
    assert [h for h, _ in parts.sections] == ["1. How It Works", "Step 2: Install"]
    assert parts.sections[0][1].endswith("x = 1\n```")  # fenced '##' is not a heading, separator trimmed
    assert parts.references == "1. [Paper](https://arxiv.org/abs/2106.09685)"


def test_changed_sections_reports_only_edited_parts():
    edited = ARTICLE.replace("Body two.", "Body two, edited.").replace("# LoRA Explained", "# LoRA, Explained")
    assert changed_sections(ARTICLE, edited) == ["Title", "Install"]
    assert changed_sections(ARTICLE, ARTICLE) == []
    soft_wrapped = ARTICLE.replace("Intro paragraph.", "Intro\nparagraph.")
    assert changed_sections(ARTICLE, soft_wrapped) == []  # the site joins soft-wrapped lines anyway
    removed = ARTICLE.replace("## Step 2: Install\n\nBody two.\n\n---\n\n", "")
    assert changed_sections(ARTICLE, removed) == ["Install"]


def test_draft_sections_keep_keys_and_claims_of_unchanged_sections():
    existing = [
        DraftSection(key="intro", heading=None, heading_style="plain", markdown="Intro paragraph.", claim_map=[{"x": 1}]),
        DraftSection(key="s1", heading="How It Works", goal="mechanism", markdown="old body", claim_map=[{"y": 1}]),
        DraftSection(key="s2", heading="Install", heading_style="step", markdown="Body two.", claim_map=[{"z": 1}]),
    ]
    added = ARTICLE.replace("## References", "## 3. Owner Notes\n\nNew section.\n\n---\n\n## References")
    sections = draft_sections_from_markdown(added, existing)
    assert [(s.key, s.heading, s.heading_style) for s in sections] == [
        ("intro", None, "plain"), ("s1", "How It Works", "numbered"), ("s2", "Install", "step"), ("s3", "Owner Notes", "numbered"),
    ]
    assert sections[0].claim_map == [{"x": 1}]   # unchanged text keeps its claim map
    assert sections[1].claim_map == [] and sections[1].goal == "mechanism"  # edited text drops stale claims
    assert sections[2].claim_map == [{"z": 1}]
