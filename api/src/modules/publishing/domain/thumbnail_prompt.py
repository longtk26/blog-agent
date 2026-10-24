def build_thumbnail_prompt(title: str, description: str, table_of_contents: list[str]) -> str:
    """Builds a targeted prompt for generating a blog post thumbnail image.

    Targeting a modern dark-tech aesthetic matching leon-pham.vercel.app with deep dark background,
    subtle neon emerald/cyan accents, and abstract geometry. Explicitly forbids text/typography.
    """
    cleaned_title = title.strip()
    cleaned_desc = description.strip() if description else "Technical engineering deep-dive."
    toc_highlights = ", ".join(t.strip() for t in table_of_contents[:6] if t.strip())
    if not toc_highlights:
        toc_highlights = "Architecture, core mechanics, and technical implementation"

    return (
        f"A modern, minimalist dark-mode tech illustration representing the topic: '{cleaned_title}'. "
        f"Context and overview: {cleaned_desc}. "
        f"Key topics covered: {toc_highlights}. "
        "Style aesthetic: Deep dark background (#09090b / charcoal / dark zinc) matching modern software engineering portfolios. "
        "Tasteful, subtle neon emerald (#10b981) and cyan accents, clean futuristic architectural geometric elements, "
        "abstract data flows or network nodes, sleek, premium, elegant lighting, 16:9 widescreen composition. "
        "Pure background visual artwork. Absolutely no text, no words, no letters, no typography, no watermarks, no logos, no distorted faces."
    )
