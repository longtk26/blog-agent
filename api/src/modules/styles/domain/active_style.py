from dataclasses import dataclass
from datetime import datetime

from src.modules.agent.prompts.context_files import seed_style_guide
from src.modules.shared.domain.entities import StyleGuideEntity


@dataclass(frozen=True)
class ActiveStyleGuide:
    version: str
    content: str
    source: str            # "owner" (latest DB edit) | "seed" (file shipped with the code)
    updated_at: datetime | None


def resolve_active_style(latest: StyleGuideEntity | None) -> ActiveStyleGuide:
    """The owner's latest edit wins; otherwise the seed file."""
    if latest is not None:
        return ActiveStyleGuide(latest.version, latest.content, "owner", latest.created_at)
    version, content = seed_style_guide()
    return ActiveStyleGuide(version, content, "seed", None)
