import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.configs import config
from src.configs.logger import get_logger
from src.modules.agent.prompts.context_files import render_contract, seed_style_guide
from src.modules.agent.prompts.diagram import PROMPT_VERSION as DIAGRAM_PROMPT_VERSION
from src.modules.agent.prompts.research import PROMPT_VERSION as RESEARCH_PROMPT_VERSION
from src.modules.agent.prompts.writing import PROMPT_VERSION as WRITING_PROMPT_VERSION

logger = get_logger(__name__)
PROMPTS_DIR = Path(__file__).parent


def _compute_file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:12]


class PromptRegistry:
    """Manages prompt versions and content hashes.

    Supports local prompt files (default) and optional LangSmith Prompt Hub (PROMPT_SOURCE=langsmith).
    """

    def __init__(self, source: str = "files"):
        self.source = source

    def all_versions(self) -> dict[str, str]:
        style_ver, _ = seed_style_guide()
        contract_ver, _ = render_contract()
        return {
            "research": RESEARCH_PROMPT_VERSION,
            "writing": WRITING_PROMPT_VERSION,
            "diagram": DIAGRAM_PROMPT_VERSION,
            "style_guide": style_ver,
            "render_contract": contract_ver,
        }

    def all_hashes(self) -> dict[str, str]:
        return {
            "research": _compute_file_hash(PROMPTS_DIR / "research.py"),
            "writing": _compute_file_hash(PROMPTS_DIR / "writing.py"),
            "diagram": _compute_file_hash(PROMPTS_DIR / "diagram.py"),
            "style_guide": _compute_file_hash(PROMPTS_DIR / "style_guide.md"),
            "render_contract": _compute_file_hash(PROMPTS_DIR / "render_contract.md"),
        }

    def get_prompt(self, name: str) -> tuple[str, str]:
        """Returns (version, prompt_content) for the given prompt name."""
        if self.source == "langsmith":
            try:
                from langchain import hub  # type: ignore

                pulled = hub.pull(f"blog-agent-{name}")
                if pulled:
                    return "langsmith-hub", str(pulled)
            except Exception as exc:
                logger.warning(
                    f"Failed to fetch prompt '{name}' from LangSmith Hub, falling back to local files: {exc}"
                )

        versions = self.all_versions()
        version = versions.get(name, "unknown")

        if name == "style_guide":
            return seed_style_guide()
        elif name == "render_contract":
            return render_contract()
        elif name in ("research", "writing", "diagram"):
            filepath = PROMPTS_DIR / f"{name}.py"
            text = filepath.read_text(encoding="utf-8") if filepath.exists() else ""
            return version, text

        return version, ""


@lru_cache
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry(source=config.prompt_source)
