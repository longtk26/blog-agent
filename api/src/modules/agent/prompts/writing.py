"""Prompts for outlining, drafting, metadata and judging. Bump PROMPT_VERSION on any wording change."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.modules.agent.prompts.research import describe_task
from src.modules.shared.domain.entities import WritingTaskEntity

PROMPT_VERSION = "writing-v3"

FORMAT_TEMPLATES = {
    "concept": (
        "Concept explainer: 4-7 numbered sections that build understanding step by step (what it is → how it works → "
        "trade-offs/comparison → when to use it). Use a comparison table where options are contrasted. The LAST section "
        "is 'Summary & What's Next' with a summary table (| Core Concept | Summary Takeaway |) and a pointer to what to read next."
    ),
    "tutorial": (
        "Hands-on tutorial: first a numbered 'Prerequisites' or 'The Tool Stack' section, then the hands-on steps with "
        "heading_style='step' (rendered '## Step N: …') each with complete runnable code, then a numbered "
        "'Troubleshooting & Pro Tips' section (table: | Problem | Cause | Solution |), and LAST a plain 'Conclusion & Resources'."
    ),
    "comparison": (
        "Comparison: numbered sections for 'Evaluation Criteria', one section per option, a 'Side-by-Side Comparison' "
        "section built around a table, a 'Recommendation' section (which to choose when), and LAST 'Summary & What's Next'."
    ),
    "series_part": (
        "Part of a series: the intro briefly recaps the previous part; then 4-7 numbered sections; LAST 'Summary & What's Next' "
        "with a summary table and a teaser of the next part."
    ),
}

DEPTH_GUIDANCE = {
    "intro": "Assume little background; favour intuition, analogies and small examples over maths.",
    "intermediate": "Assume working engineering knowledge; explain mechanisms and trade-offs with concrete examples.",
    "deep_dive": "Go deep: mechanisms, maths where it helps, implementation details, edge cases and numbers.",
}


def _context(style_guide: str, render_contract: str) -> str:
    return f"<style_guide>\n{style_guide}\n</style_guide>\n\n<render_contract>\n{render_contract}\n</render_contract>"


def outline_messages(
    task: WritingTaskEntity,
    brief_summary: str,
    evidence: str,
    must_cover: list[str],
    style_guide: str,
    max_sections: int,
    feedback: str | None = None,
    owner_feedback: str | None = None,
    current_outline: str | None = None,
    sample_outlines: str | None = None,
) -> list[BaseMessage]:
    diagram_rule = {
        "yes": "Include at least one diagram (needs: diagram).",
        "no": "Do not plan diagrams.",
        "auto": "Plan a diagram for each concept that is easier to see than to read.",
    }[str(task.include_diagram)]
    system = (
        "You are the outlining editor for a technical blog. Design the structure of ONE article from the research "
        "evidence, in the owner's style.\n"
        f"- Format: {FORMAT_TEMPLATES[str(task.format)]}\n"
        f"- Depth: {DEPTH_GUIDANCE[str(task.depth)]}\n"
        f"- At most {max_sections} sections (the intro, table of contents and references are added automatically; do not plan them).\n"
        "- Each section lists the evidence refs (C#) it relies on; do not plan claims there is no evidence for.\n"
        f"- {diagram_rule} Mark code/table/math/analogy needs where they help.\n"
        "- Map every must-cover requirement to the section that handles it.\n"
        "- Headings are short and specific; do not number them."
    )
    requirements = "\n".join(f"- {item}" for item in must_cover) or "- (none)"
    human = (
        f"{describe_task(task)}\n\nMust-cover requirements:\n{requirements}\n\n"
        f"Research summary:\n{brief_summary}\n\nEvidence:\n{evidence}\n\n<style_guide>\n{style_guide}\n</style_guide>"
    )
    if sample_outlines:
        human += (
            f"\n\n<style_reference_do_not_copy>\n"
            f"The following are approved past outlines from the author's blog for this format ({task.format}). "
            "Use them ONLY as structural inspiration — do NOT copy headings or wording verbatim:\n"
            f"{sample_outlines}\n"
            "</style_reference_do_not_copy>"
        )
    if owner_feedback:
        human += (
            "\n\nThe owner reviewed the article built from the current outline and asked for a structural change. "
            "Restructure accordingly; keep what the feedback does not touch.\n"
            f"Current outline:\n{current_outline or '(unknown)'}\n\nOwner feedback:\n<feedback>\n{owner_feedback}\n</feedback>"
        )
    if feedback:
        human += f"\n\nYour previous outline had problems; fix them:\n{feedback}"
    return [SystemMessage(system), HumanMessage(human)]


def section_messages(
    task: WritingTaskEntity,
    title: str,
    angle: str,
    outline_overview: str,
    section_heading: str | None,
    section_brief: str,
    evidence: str,
    previous_tail: str,
    style_guide: str,
    render_contract: str,
    current_markdown: str | None = None,
    feedback: str | None = None,
    owner_feedback: str | None = None,
    sample_sections: str | None = None,
    internal_links: str | None = None,
) -> list[BaseMessage]:
    part = "the INTRODUCTION (1-2 framing paragraphs, no heading)" if section_heading is None else f"the section '{section_heading}'"
    system = (
        f"You are writing {part} of a technical blog article, in the owner's voice and style.\n"
        "- Follow the style guide and the render contract exactly.\n"
        "- Write ONLY this part. Do not write the '## ' heading of this section, a title, a table of contents or references. "
        "Use '### ' for sub-headings inside the section.\n"
        "- Ground every factual statement in the evidence. Cite inline by linking the source URL with descriptive text, "
        "e.g. [the LoRA paper](https://arxiv.org/abs/2106.09685). Never invent URLs, numbers, versions or quotes.\n"
        "- If the evidence does not support something the outline asks for, say so briefly or leave it out.\n"
        "- Code must be complete and runnable as shown (imports included).\n"
        "- Also return a claim map: every factual sentence with the evidence refs (C#) that support it and whether the "
        "support is full, partial or missing."
    )
    human = (
        f"{describe_task(task)}\n\nArticle title: {title}\nAngle: {angle}\n\nArticle outline (for context):\n{outline_overview}\n\n"
        f"Write: {part}\n{section_brief}\n\nEvidence for this part:\n{evidence or '- (no direct evidence; keep factual claims minimal)'}\n\n"
        f"End of the previous part (for flow):\n{previous_tail or '(start of article)'}\n\n{_context(style_guide, render_contract)}"
    )
    if sample_sections:
        human += (
            f"\n\n<style_reference_do_not_copy>\n"
            "The following are approved past sections from the author's blog on similar topics. "
            "Use them ONLY for tone, explanation depth, and structure — DO NOT copy sentences, paragraphs, or wording verbatim:\n"
            f"{sample_sections}\n"
            "</style_reference_do_not_copy>"
        )
    if internal_links:
        human += (
            f"\n\n<internal_links>\n"
            "The author has previously published the following related articles. "
            "If directly relevant to this section, you may link to them using their exact absolute URL (e.g. [our LoRA guide](https://leon-pham.vercel.app/posts/...)):\n"
            f"{internal_links}\n"
            "</internal_links>"
        )
    if current_markdown is not None and owner_feedback:
        human += (
            "\n\nOWNER REVISION: the owner reviewed this part and asked for the change below. Apply it faithfully, "
            "keep everything the feedback does not mention, and keep the evidence rules (no invented facts).\n"
            f"Owner feedback:\n<feedback>\n{owner_feedback}\n</feedback>\n\nCurrent text:\n<current>\n{current_markdown}\n</current>"
        )
        if feedback:
            human += f"\n\nAlso fix these problems found by automated checks:\n{feedback}"
    elif current_markdown is not None:
        human += (
            f"\n\nREVISION: rewrite this part to fix the problems below. Keep everything that is already good.\n"
            f"Problems:\n{feedback}\n\nCurrent text:\n<current>\n{current_markdown}\n</current>"
        )
    return [SystemMessage(system), HumanMessage(human)]


def metadata_messages(task: WritingTaskEntity, title_options: list[str], angle: str, intro: str) -> list[BaseMessage]:
    system = (
        "Write publishing metadata for a technical blog post. Title: choose or refine one of the options (keep the owner's "
        "style: plain subject, often with a colon or 'vs.'). Description: one plain-text sentence of at most 160 characters. "
        "Tags: 1-4 lowercase alphanumeric words (no spaces, dashes or '#'), most specific first, e.g. 'llm', 'finetuning', "
        "'rag'. Slug: lowercase words joined by dashes."
    )
    options = "\n".join(f"- {t}" for t in title_options)
    human = f"{describe_task(task)}\n\nAngle: {angle}\n\nTitle options:\n{options}\n\nIntroduction:\n{intro[:1500]}"
    return [SystemMessage(system), HumanMessage(human)]


def judge_messages(
    task: WritingTaskEntity, article: str, evidence: str, must_cover: list[str], style_guide: str
) -> list[BaseMessage]:
    system = (
        "You are a strict technical editor reviewing a draft before the owner sees it. Score it 1-5 on each criterion and "
        "list concrete issues. Be honest about uncertainty: you can only check claims against the evidence given, so flag "
        "statements the evidence does not support instead of assuming they are true or false.\n"
        "- severity 'blocker': factual error vs. the evidence, unsupported important claim, missing required content, or "
        "broken structure; 'warning': weaker writing, style drift, missing helpful element; 'info': minor polish.\n"
        "- For each issue give the affected section's heading text exactly as written (without the number), the problem, "
        "and a specific fix."
    )
    requirements = "\n".join(f"- {item}" for item in must_cover) or "- (none)"
    human = (
        f"{describe_task(task)}\n\nMust-cover requirements:\n{requirements}\n\nEvidence:\n{evidence}\n\n"
        f"<style_guide>\n{style_guide}\n</style_guide>\n\n<draft>\n{article}\n</draft>"
    )
    return [SystemMessage(system), HumanMessage(human)]


def metadata_revision_messages(task: WritingTaskEntity, current: dict, feedback: str, intro: str) -> list[BaseMessage]:
    system = (
        "Revise the publishing metadata of a technical blog post according to the owner's feedback. Change only what "
        "the feedback asks for. Description: one plain-text sentence of at most 160 characters. Tags: 1-4 lowercase "
        "alphanumeric words. Slug: lowercase words joined by dashes; keep the current slug unless the feedback asks to change it."
    )
    human = (
        f"{describe_task(task)}\n\nCurrent metadata:\n- title: {current.get('title')}\n- slug: {current.get('slug')}\n"
        f"- description: {current.get('description')}\n- tags: {', '.join(current.get('tags', []))}\n\n"
        f"Owner feedback:\n<feedback>\n{feedback}\n</feedback>\n\nIntroduction:\n{intro[:1500]}"
    )
    return [SystemMessage(system), HumanMessage(human)]


def feedback_route_messages(
    task: WritingTaskEntity, feedback: str, section_names: list[str], scoped: list[str]
) -> list[BaseMessage]:
    system = (
        "Classify the owner's review feedback on a draft article into the ONE stage that must redo work:\n"
        "- research: needs facts, sources or evidence the article does not have yet\n"
        "- outline: change the structure (add/remove/merge/reorder sections, different angle)\n"
        "- draft: rewrite the wording or content of specific sections (the default when unsure)\n"
        "- diagram: only a diagram should change\n"
        "- metadata: only the title, description, slug or tags should change\n"
        "Also list the affected sections, using the section names exactly as given (use 'Introduction' for the intro). "
        "Leave sections empty if the feedback applies to the whole article."
    )
    names = "\n".join(f"- {name}" for name in section_names)
    human = f"{describe_task(task)}\n\nSections:\n{names}\n\n"
    if scoped:
        human += f"The owner pointed at these sections: {', '.join(scoped)}\n\n"
    human += f"Owner feedback:\n<feedback>\n{feedback}\n</feedback>"
    return [SystemMessage(system), HumanMessage(human)]
