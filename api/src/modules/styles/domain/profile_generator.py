from dataclasses import asdict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.modules.agent.nodes.llm import invoke_structured
from src.modules.shared.domain.entities import StyleProfileData, WritingSampleEntity


class StyleProfileSchema(BaseModel):
    tone: str = Field(description="The author's tone (e.g. conversational, rigorous, pragmatic, no-nonsense).")
    voice: str = Field(description="Author voice (e.g. first-person builder, experienced practitioner, mentor).")
    structure_patterns: dict[str, str] = Field(
        default_factory=dict,
        description="Patterns by format: tutorial, deep_dive, overview, series_part.",
    )
    heading_conventions: str = Field(
        description="Conventions for H1/H2/H3 (e.g. numbered sections '1. Concept', imperative titles, case style)."
    )
    intro_pattern: str = Field(
        description="How intros are constructed (e.g. problem statement hook, practical motivation, roadmap)."
    )
    explanation_devices: list[str] = Field(
        default_factory=list,
        description="Recurring pedagogical devices: analogies, intuitive mental models, tables, trade-off comparisons.",
    )
    code_example_style: str = Field(
        description="How code snippets are presented (commenting density, self-contained vs snippets, language choices)."
    )
    diagram_usage: str = Field(
        description="When and what type of diagrams are used (flowcharts, sequence diagrams, architecture trees)."
    )
    typical_length: dict[str, str] = Field(
        default_factory=dict,
        description="Typical word count estimates per format.",
    )
    do: list[str] = Field(
        default_factory=list,
        description="Definitive style rules to follow based on the author's writing.",
    )
    dont: list[str] = Field(
        default_factory=list,
        description="Anti-patterns and generic AI tropes the author avoids.",
    )
    signature_phrases: list[str] = Field(
        default_factory=list,
        description="Short recurring catchphrases, idioms, or transitions (max 3-7 words each).",
    )


async def generate_style_profile_from_samples(
    samples: list[WritingSampleEntity],
    model: BaseChatModel,
) -> StyleProfileData:
    """Analyze approved writing samples to produce an explicit, structured StyleProfileData."""
    # Build a condensed representation of the corpus
    corpus_excerpts: list[str] = []
    for s in samples[:8]:
        # Excerpt intro, middle, code, and outro up to ~2500 chars per sample
        title = s.title
        content = s.content
        lines = content.split("\n")
        intro = "\n".join(lines[:25])
        middle = "\n".join(lines[len(lines) // 2 : len(lines) // 2 + 25]) if len(lines) > 50 else ""
        corpus_excerpts.append(
            f"--- Article Sample: {title} ---\nIntro Excerpt:\n{intro}\n\nMiddle Excerpt:\n{middle}\n"
        )

    corpus_text = "\n\n".join(corpus_excerpts)

    system_prompt = (
        "You are an expert technical editor and stylometry analyst. "
        "Your task is to analyze the author's approved technical blog posts and extract an exact, structured style profile. "
        "Capture their authentic voice, structural patterns, code snippet conventions, and do's/don'ts. "
        "Avoid generic advice; extract what makes THIS author's writing distinct from generic AI text."
    )

    user_prompt = f"Analyze the following writing samples from the author's technical blog corpus:\n\n{corpus_text}"

    messages = [
        SystemMessage(system_prompt),
        HumanMessage(user_prompt),
    ]

    result = await invoke_structured(model, StyleProfileSchema, messages)
    return StyleProfileData(
        tone=result.tone,
        voice=result.voice,
        structure_patterns=result.structure_patterns,
        heading_conventions=result.heading_conventions,
        intro_pattern=result.intro_pattern,
        explanation_devices=result.explanation_devices,
        code_example_style=result.code_example_style,
        diagram_usage=result.diagram_usage,
        typical_length=result.typical_length,
        do=result.do,
        dont=result.dont,
        signature_phrases=result.signature_phrases,
    )
