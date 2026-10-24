from dataclasses import dataclass
from datetime import datetime

from src.modules.agent.prompts.context_files import seed_style_guide
from src.modules.shared.domain.entities import StyleGuideEntity, StyleProfileEntity


@dataclass(frozen=True)
class ActiveStyleGuide:
    version: str
    content: str
    source: str            # "learned_profile" | "owner" (latest DB edit) | "seed" (file shipped with the code)
    updated_at: datetime | None


def resolve_active_style(
    latest_guide: StyleGuideEntity | None = None,
    active_profile: StyleProfileEntity | None = None,
) -> ActiveStyleGuide:
    """The active learned StyleProfile wins; else owner's latest edit of style guide; else seed file."""
    if active_profile is not None:
        version_str = f"profile-v{active_profile.version}"
        content = active_profile.markdown_content or ""
        return ActiveStyleGuide(version_str, content, "learned_profile", active_profile.updated_at)
    if latest_guide is not None:
        return ActiveStyleGuide(latest_guide.version, latest_guide.content, "owner", latest_guide.created_at)
    version, content = seed_style_guide()
    return ActiveStyleGuide(version, content, "seed", None)
