"""Icon catalogue for the draw.io generator.

Styles come from catalogue/icon_catalogue.json, generated from draw.io's pinned shape index by
`make diagrams-icons` (E10-S4), so every shape name is one draw.io knows (checked by test_icons_exist.py).
Keys are namespaced by family: aws:*, gcp:*, k8s:*, gh:*, plus a few generic keys (user, client, ...).
Specs only ever carry keys; styles are resolved here.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

CATALOGUE_PATH = Path(__file__).resolve().parents[1] / "catalogue" / "icon_catalogue.json"

@dataclass(frozen=True)
class IconSpec:
    key: str
    family: str             # aws | gcp | k8s | gh | generic
    color: str              # fillColor
    stroke: str             # strokeColor ("none" for standalone glyph stencils)
    drawio_shape: str       # style fragment selecting the draw.io stencil (from the shape index)
    tile: bool = False      # square service tile (aws resourceIcon, k8s icon2) vs. standalone glyph
    aliases: tuple[str, ...] = ()
    source: str = ""        # which allowlist candidate resolved (resIcon:/shape:/prIcon:/image:)


def _load() -> dict[str, IconSpec]:
    data = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    return {
        key: IconSpec(
            key=key,
            family=item["family"],
            color=item["fill"],
            stroke=item["stroke"],
            drawio_shape=item["shape_style"],
            tile=bool(item.get("tile")),
            aliases=tuple(item.get("aliases", ())),
            source=item.get("source", ""),
        )
        for key, item in data["icons"].items()
    }


ICONS: dict[str, IconSpec] = _load()
FAMILIES = ("aws", "gcp", "k8s", "gh", "generic")


_AWS_TAG = re.compile(r"^\s*\[(?:aws\s+)?([^\]]+)\]\s*", re.IGNORECASE)
_PREFIXES = ("aws:", "gcp:", "k8s:", "gh:")


def family_of(key: str | None) -> str | None:
    icon = lookup(key)
    return icon.family if icon else None


def lookup(key: str | None) -> IconSpec | None:
    """Exact key, or a bare AWS name ("ec2" -> "aws:ec2"); None for unknown keys."""
    if not key:
        return None
    key = key.strip().lower()
    return ICONS.get(key) or ICONS.get(f"aws:{key}")


def dominant_family(icon_keys: list[str | None]) -> str:
    """The cloud family most icon keys belong to (k8s/gh/generic don't count); "aws" when there is no signal."""
    counts: dict[str, int] = {}
    for key in icon_keys:
        family = family_of(key)
        if family in ("aws", "gcp"):
            counts[family] = counts.get(family, 0) + 1
    if not counts:
        return "aws"
    return max(sorted(counts), key=lambda f: counts[f])


def _match_alias(text: str, keys: list[str]) -> IconSpec | None:
    for key in keys:
        icon = ICONS[key]
        for alias in icon.aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                return icon
    return None


def _inference_order(prefer: str | None) -> list[str]:
    """Keys searched when inferring an icon from a label: the preferred cloud first, the other cloud never."""
    prefer = prefer or "aws"
    other = "gcp" if prefer == "aws" else "aws"
    first = [k for k in ICONS if k.startswith(f"{prefer}:")]
    rest = [k for k in ICONS if not k.startswith((f"{prefer}:", f"{other}:"))]
    return first + rest


def resolve_icon(
    icon: str | None, label: str, kind: str, diagram_type: str, prefer_family: str | None = None
) -> tuple[IconSpec | None, str]:
    """(icon, display label). Explicit keys win; "[AWS EC2] Web Server" tags are understood and stripped.

    Keyword inference only runs for architecture diagrams, so flowchart steps keep their box shapes; it searches the
    diagram's dominant cloud (prefer_family) and never the other one, so "Load Balancer" in a GCP diagram stays GCP.
    """
    found = lookup(icon)
    if found:
        return found, _AWS_TAG.sub("", label).strip() or label
    tag = _AWS_TAG.match(label)
    if tag:
        found = _match_alias(tag.group(1).lower(), [k for k in ICONS if k.startswith("aws:")])
        rest = label[tag.end():].strip()
        if found:
            return found, rest or tag.group(1).strip()
    if kind == "actor":
        return ICONS["user"], label
    if diagram_type == "architecture" and kind in ("service", "datastore", "external"):
        found = _match_alias(label.lower(), _inference_order(prefer_family))
        if found:
            return found, label
    return None, label
