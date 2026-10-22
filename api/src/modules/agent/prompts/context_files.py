import re
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
_VERSION = re.compile(r"<!--\s*version:\s*([\w.-]+)\s*-->")


def _read(name: str) -> tuple[str, str]:
    text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
    match = _VERSION.search(text)
    return (match.group(1) if match else "unversioned"), _VERSION.sub("", text).strip()


@lru_cache
def seed_style_guide() -> tuple[str, str]:
    """(version, content) of the hand-curated style guide shipped with the code."""
    return _read("style_guide.md")


@lru_cache
def render_contract() -> tuple[str, str]:
    return _read("render_contract.md")
