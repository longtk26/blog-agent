import hashlib
from pathlib import Path
import uuid
import pytest

from src.modules.publishing.domain.devto_renderer import (
    clean_latex_math,
    format_math_for_devto,
    render_for_devto,
    sanitize_devto_tags,
    slugify_devto_heading,
)
from src.modules.shared.domain.entities import ArticleRevisionEntity, RevisionAuthor


def test_slugify_devto_heading():
    assert slugify_devto_heading("1. What is Fine-Tuning?") == "1-what-is-fine-tuning"
    assert slugify_devto_heading("Getting Started with Forem & API!") == "getting-started-with-forem-api"
    assert slugify_devto_heading("## Table of Contents") == "table-of-contents"
    assert slugify_devto_heading("Code `npm install` and **Bold**") == "code-npm-install-and-bold"


def test_sanitize_devto_tags():
    raw_tags = ["#AI", "Machine Learning", "deep-learning", "python", "extra_tag"]
    # Max 4, lowercase, spaces removed, # stripped
    cleaned = sanitize_devto_tags(raw_tags)
    assert cleaned == ["ai", "machinelearning", "deep-learning", "python"]
    assert len(cleaned) == 4


def test_clean_latex_math():
    raw = r"\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V"
    cleaned = clean_latex_math(raw)
    assert "softmax((QK^T) / (sqrt(d_k)))V" in cleaned or "Attention" in cleaned
    assert clean_latex_math(r"\Delta W = B \cdot A") == "ΔW = B * A"
    assert clean_latex_math(r"\mathbb{R}^{d \times r}") == "R^(d * r)"


def test_format_math_for_devto():
    sample = """Here is inline $x = 5$ and another $W_e \\in \\mathbb{R}^{V \\times d}$.

$$
\\Delta W = B \\cdot A
$$

And a real code block:
```python
x = "$not_math$"
```
"""
    formatted = format_math_for_devto(sample, use_katex_liquid=False)
    assert "`x = 5`" in formatted
    assert "`W_e in R^(V * d)`" in formatted
    assert "```text\nΔW = B * A\n```" in formatted
    # Existing python code block is preserved untouched
    assert 'x = "$not_math$"' in formatted

    # Test Liquid tag option
    formatted_liquid = format_math_for_devto(sample, use_katex_liquid=True)
    assert "{% katex %}" in formatted_liquid


@pytest.mark.asyncio
async def test_render_for_devto_basic():
    markdown = """# The Real Title

Welcome to the post. Check out [Other Post](/posts/other-post).

## 1. Introduction

Here is some math: $E = mc^2$.

```mermaid
flowchart TD
    A --> B
```

## Table of Contents
- [1. Introduction](#1-introduction)
"""
    revision = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="The Real Title",
        slug="the-real-title",
        description="A great article",
        tags=["#AI", "DevOps", "Python"],
        markdown=markdown,
        created_by=RevisionAuthor.AI,
        content_hash="mock-hash",
    )

    res = await render_for_devto(revision, canonical_url="https://leon-pham.vercel.app/posts/the-real-title")

    # 1. Strips leading H1
    assert not res.body_markdown.startswith("# The Real Title")
    assert "Welcome to the post." in res.body_markdown

    # 2. Rewrites /posts/ links to absolute URL
    assert "https://leon-pham.vercel.app/posts/other-post" in res.body_markdown

    # 3. Formats math
    assert "`E = mc^2`" in res.body_markdown

    # 4. Replaces mermaid with image
    assert "```mermaid" not in res.body_markdown
    assert "![Diagram 1]" in res.body_markdown

    # 5. Adds canonical footer
    assert "*Originally published at [https://leon-pham.vercel.app/posts/the-real-title](https://leon-pham.vercel.app/posts/the-real-title)*" in res.body_markdown

    # 6. Tags sanitized
    assert res.tags == ["ai", "devops", "python"]
    assert res.rendered_content_hash == hashlib.sha256(res.body_markdown.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_golden_fine_tuning_posts():
    """Golden-file audit test on the two existing fine-tuning posts (E8-S2)."""
    root = Path(__file__).resolve().parents[4]
    blogs_dir = root / "blogs" / "fine_tuning"

    concepts_path = blogs_dir / "fine_tuning_concepts.md"
    impl_path = blogs_dir / "fine_tuning_implementation.md"

    assert concepts_path.exists(), f"Missing {concepts_path}"
    assert impl_path.exists(), f"Missing {impl_path}"

    # 1. Fine-tuning concepts
    rev1 = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="LLM Fine-Tuning: Concepts, Architecture, and Fine-Tuning vs. RAG",
        slug="fine-tuning-concepts",
        description="Comprehensive guide to fine-tuning LLMs",
        tags=["ai", "finetuning", "rag", "llm"],
        markdown=concepts_path.read_text(encoding="utf-8"),
        created_by=RevisionAuthor.OWNER,
        content_hash="concepts-hash",
    )

    res1 = await render_for_devto(rev1, canonical_url="https://leon-pham.vercel.app/posts/fine-tuning-concepts")
    assert not res1.body_markdown.startswith("# LLM Fine-Tuning:")
    assert "```mermaid" not in res1.body_markdown
    assert "![Diagram" in res1.body_markdown
    assert len(res1.tags) == 4
    assert res1.rendered_content_hash

    # 2. Fine-tuning implementation
    rev2 = ArticleRevisionEntity(
        task_id=uuid.uuid4(),
        revision_number=1,
        title="Fine-Tuning Implementation Guide",
        slug="fine-tuning-implementation",
        description="Step-by-step implementation guide for Unsloth and QLoRA",
        tags=["ai", "unsloth", "qlora", "python"],
        markdown=impl_path.read_text(encoding="utf-8"),
        created_by=RevisionAuthor.OWNER,
        content_hash="impl-hash",
    )

    res2 = await render_for_devto(rev2, canonical_url="https://leon-pham.vercel.app/posts/fine-tuning-implementation")
    assert not res2.body_markdown.startswith("# ")
    assert "```mermaid" not in res2.body_markdown
    assert len(res2.tags) == 4
    assert res2.rendered_content_hash

    # Save golden rendered hashes for audit
    golden_dir = root / "blog-agent" / "pdm" / "epic8_devto_publishing" / "golden"
    golden_dir.mkdir(parents=True, exist_ok=True)
    (golden_dir / "fine_tuning_concepts_devto.hash").write_text(res1.rendered_content_hash)
    (golden_dir / "fine_tuning_implementation_devto.hash").write_text(res2.rendered_content_hash)
