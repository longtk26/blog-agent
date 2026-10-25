import re
from typing import Any

from src.modules.articles.domain.markdown_tools import extract_headings
from src.modules.articles.domain.validators import ValidationContext, has_blockers, validate_article


def _extract_io(args: tuple, kwargs: dict) -> tuple[dict, dict, dict]:
    """Helper to support both LangSmith (run, example) and direct (inputs, outputs, reference)."""
    if len(args) >= 2 and hasattr(args[0], "outputs") and hasattr(args[1], "outputs"):
        run, example = args[0], args[1]
        inputs = getattr(run, "inputs", None) or getattr(example, "inputs", {}) or {}
        outputs = getattr(run, "outputs", {}) or {}
        reference = getattr(example, "outputs", {}) or {}
        return inputs, outputs, reference

    inputs = kwargs.get("inputs") or (args[0] if len(args) > 0 and isinstance(args[0], dict) else {})
    outputs = kwargs.get("outputs") or (args[1] if len(args) > 1 and isinstance(args[1], dict) else {})
    reference = kwargs.get("reference") or kwargs.get("reference_outputs") or (args[2] if len(args) > 2 and isinstance(args[2], dict) else {})
    return inputs, outputs, reference


def _build_validation_context(inputs: dict, outputs: dict, reference: dict) -> ValidationContext:
    fmt = reference.get("format") or inputs.get("format", "concept")
    meta = outputs.get("metadata")
    if meta is None:
        from src.modules.articles.domain.markdown_tools import extract_headings
        from src.modules.shared.domain.entities import ArticleMetadata

        h1 = next((h.text for h in extract_headings(outputs.get("markdown", "")) if h.level == 1), None)
        title = h1 or inputs.get("topic", "Sample Article")
        meta = ArticleMetadata(
            title=title,
            slug="sample-article",
            description="Sample description for testing",
            tags=["sample"],
        )
    elif isinstance(meta, dict):
        from src.modules.shared.domain.entities import ArticleMetadata
        meta = ArticleMetadata(**meta)

    source_urls = set()
    for s in outputs.get("sources", []):
        url = s.get("canonical_url") or s.get("url")
        if url:
            source_urls.add(url)

    must_cover = reference.get("must_cover", [])
    return ValidationContext(
        format=fmt,
        metadata=meta,
        source_urls=source_urls,
        must_cover=must_cover,
    )


def eval_markdown_valid(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: markdown_valid (0 or 1). Checks render contract and structural blocker rules."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    ctx = _build_validation_context(inputs, outputs, reference)
    issues = validate_article(markdown, ctx)
    blockers = [i for i in issues if getattr(i, "severity", None) == "blocker" or getattr(i.severity, "value", None) == "blocker"]
    is_valid = 1 if len(blockers) == 0 else 0
    return {
        "key": "markdown_valid",
        "score": is_valid,
        "comment": f"{len(blockers)} blocker issues found: {[b.rule for b in blockers]}" if blockers else "Markdown contract valid",
    }


def eval_render_contract_violations(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: render_contract_violations (count of rule violations)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    markdown = outputs.get("markdown", "")
    ctx = _build_validation_context(inputs, outputs, reference)
    issues = validate_article(markdown, ctx)
    # Count render contract violations: headings, blank lines, code fences, math, tables, html, anchors
    RENDER_RULES = {
        "H1_COUNT",
        "H1_FIRST",
        "HEADING_SKIP",
        "BLANK_LINE",
        "CODE_FENCE_LANG",
        "MATH_SYNTAX",
        "TABLE_SYNTAX",
        "HTML_TAG_FORBIDDEN",
        "ANCHOR_BROKEN",
    }
    violations = [i for i in issues if i.rule in RENDER_RULES]
    count = len(violations)
    return {
        "key": "render_contract_violations",
        "score": float(count),
        "comment": f"{count} render contract violations found: {[v.rule for v in violations]}",
    }



def eval_citation_coverage(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: citation_coverage (% of claim-map sentences that have a source)."""
    _, outputs, _ = _extract_io(args, kwargs)
    claim_map = outputs.get("claim_map", [])
    markdown = outputs.get("markdown", "")

    if claim_map:
        covered = sum(1 for c in claim_map if c.get("claim_ids") or c.get("source_id"))
        ratio = round(covered / len(claim_map), 4)
    else:
        # Fallback to inspecting markdown links in prose
        link_count = len(re.findall(r"(?<!!)\[[^\]]+\]\(https?://[^\)]+\)", markdown))
        sentences = [s for s in re.split(r"[.!?]\s+", markdown) if len(s.strip()) > 30 and not s.strip().startswith("#")]
        ratio = min(1.0, round(link_count / max(len(sentences), 1), 4))

    return {
        "key": "citation_coverage",
        "score": ratio,
        "comment": f"Citation coverage: {ratio * 100:.1f}%",
    }


def eval_source_quality_mix(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: source_quality_mix (% from official docs, papers or repos)."""
    _, outputs, _ = _extract_io(args, kwargs)
    sources = outputs.get("sources", [])
    if not sources:
        return {"key": "source_quality_mix", "score": 1.0, "comment": "No sources recorded"}

    high_quality_types = {"official_docs", "paper", "github_repo", "owner_note"}
    high_quality_count = 0
    for s in sources:
        stype = s.get("source_type")
        if stype in high_quality_types:
            high_quality_count += 1
        elif (s.get("quality_score") or 0.0) >= 0.7:
            high_quality_count += 1

    ratio = round(high_quality_count / len(sources), 4)
    return {
        "key": "source_quality_mix",
        "score": ratio,
        "comment": f"{high_quality_count}/{len(sources)} sources from authoritative origins ({ratio * 100:.1f}%)",
    }


def eval_min_sources_met(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: min_sources_met (0 or 1)."""
    _, outputs, reference = _extract_io(args, kwargs)
    sources = outputs.get("sources", [])
    min_required = reference.get("min_sources", 1)
    met = 1 if len(sources) >= min_required else 0
    return {
        "key": "min_sources_met",
        "score": met,
        "comment": f"Found {len(sources)} sources, required {min_required}",
    }


def eval_required_sections_present(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: required_sections_present (% of expected sections present in headings)."""
    _, outputs, reference = _extract_io(args, kwargs)
    expected = reference.get("expected_sections", [])
    if not expected:
        return {"key": "required_sections_present", "score": 1.0, "comment": "No expected sections required"}

    markdown = outputs.get("markdown", "")
    headings = [h.text.lower() for h in extract_headings(markdown)]

    matched = 0
    for exp in expected:
        exp_clean = exp.lower().strip()
        # Substring or token overlap match
        words = set(re.findall(r"\w+", exp_clean))
        if any(exp_clean in h or (words and len(words & set(re.findall(r"\w+", h))) >= min(len(words), 2)) for h in headings):
            matched += 1

    ratio = round(matched / len(expected), 4)
    return {
        "key": "required_sections_present",
        "score": ratio,
        "comment": f"Matched {matched}/{len(expected)} expected sections ({ratio * 100:.1f}%)",
    }


def eval_diagram_valid(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: diagram_valid (0 or 1, when expected)."""
    inputs, outputs, reference = _extract_io(args, kwargs)
    expected = reference.get("diagram_expected") or inputs.get("include_diagram") in ("yes", True)
    if not expected:
        return {"key": "diagram_valid", "score": 1.0, "comment": "Diagram not expected"}

    markdown = outputs.get("markdown", "")
    has_mermaid = "```mermaid" in markdown
    diagram_assets = outputs.get("diagram_assets", [])
    has_valid_asset = any(a.get("validation_status") == "valid" for a in diagram_assets)

    valid = 1 if (has_mermaid or has_valid_asset) else 0
    return {
        "key": "diagram_valid",
        "score": valid,
        "comment": "Valid diagram present" if valid else "Diagram was expected but missing or invalid",
    }


def eval_tool_error_rate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: tool_error_rate (failed tool calls / total tool calls)."""
    _, outputs, _ = _extract_io(args, kwargs)
    tool_calls = outputs.get("tool_calls", [])
    if not tool_calls:
        # Check source failures
        sources = outputs.get("sources", [])
        failed = sum(1 for s in sources if s.get("status") == "failed")
        total = len(sources)
        rate = round(failed / max(total, 1), 4) if total else 0.0
        return {"key": "tool_error_rate", "score": rate, "comment": f"Source failure rate: {rate}"}

    failed_calls = sum(1 for c in tool_calls if c.get("error") or c.get("status") == "failed")
    rate = round(failed_calls / len(tool_calls), 4)
    return {
        "key": "tool_error_rate",
        "score": rate,
        "comment": f"{failed_calls}/{len(tool_calls)} tool calls failed",
    }


def eval_cost_usd(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: cost_usd (task estimated cost in USD)."""
    _, outputs, _ = _extract_io(args, kwargs)
    cost = float(outputs.get("cost_usd", outputs.get("total_cost_usd", 0.0)))
    return {
        "key": "cost_usd",
        "score": round(cost, 6),
        "comment": f"Task cost: ${cost:.6f}",
    }


def eval_latency_s(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """E9-S4: latency_s (runtime in seconds)."""
    _, outputs, _ = _extract_io(args, kwargs)
    latency = float(outputs.get("latency_s", outputs.get("total_latency_ms", 0) / 1000.0))
    return {
        "key": "latency_s",
        "score": round(latency, 2),
        "comment": f"Runtime: {latency:.2f}s",
    }


ALL_DETERMINISTIC_EVALUATORS = [
    eval_markdown_valid,
    eval_render_contract_violations,
    eval_citation_coverage,
    eval_source_quality_mix,
    eval_min_sources_met,
    eval_required_sections_present,
    eval_diagram_valid,
    eval_tool_error_rate,
    eval_cost_usd,
    eval_latency_s,
]
