from src.modules.shared.domain.entities import WritingTaskEntity


def render_brief_markdown(task: WritingTaskEntity, data: dict) -> str:
    """Deterministic Markdown view of a research brief; every finding links to its sources."""
    sources = {s["ref"]: s for s in data.get("sources", [])}

    def links(refs: list[str]) -> str:
        parts = [f"[{ref}]({sources[ref]['url']})" for ref in refs if ref in sources]
        return f" ({', '.join(parts)})" if parts else ""

    lines = [f"# Research brief: {task.topic}", "", data.get("summary", "").strip(), ""]

    lines += ["## Key findings", ""]
    for finding in data.get("key_findings", []):
        marker = "" if finding.get("supported") else " _(no linked evidence)_"
        lines.append(f"- {finding['finding']}{links(finding.get('source_refs', []))}{marker}")
    lines.append("")

    if data.get("conflicts"):
        lines += ["## Conflicting information", ""]
        lines += [f"- {c['description']}{links(c.get('source_refs', []))}" for c in data["conflicts"]]
        lines.append("")

    if data.get("open_questions"):
        lines += ["## Open questions", ""]
        lines += [f"- {q}" for q in data["open_questions"]]
        lines.append("")

    if data.get("angles"):
        lines += ["## Suggested angles", ""]
        lines += [f"- **{a['title']}** — for {a['audience']}. {a['rationale']}" for a in data["angles"]]
        lines.append("")

    lines += ["## Recommended sources", ""]
    for index, source in enumerate(data.get("recommended_sources", []), start=1):
        meta = ", ".join(
            str(part)
            for part in (source.get("publisher"), source.get("source_type"), f"quality {source['quality_score']:.2f}" if source.get("quality_score") is not None else None)
            if part
        )
        lines.append(f"{index}. [{source.get('title') or source['url']}]({source['url']}){f' — {meta}' if meta else ''}")
    return "\n".join(lines).strip() + "\n"
