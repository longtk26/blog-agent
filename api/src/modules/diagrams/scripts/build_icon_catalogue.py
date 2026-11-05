"""Build the icon catalogue and the shape-name test fixture from draw.io's shape index (E10-S3/S4).

    python -m src.modules.diagrams.scripts.build_icon_catalogue          # uses the cached index if present
    python -m src.modules.diagrams.scripts.build_icon_catalogue --refresh

The index is downloaded from jsDelivr at the commit pinned in icon_allowlist.json (never @main), cached under
api/.cache/, and treated as untrusted data: it is only JSON-parsed and string-matched. Two files are written:

* src/modules/diagrams/catalogue/icon_catalogue.json: key -> resolved draw.io style fragment + colours
* tests/fixtures/drawio_shape_index.json.gz: every shape/resIcon/prIcon name in the index (+ hashes of image
  styles), so tests can check names offline without the 4.7 MB index.

The build fails if any allowlisted icon has no candidate in the index; nothing is guessed.
"""

import argparse
import gzip
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[4]
CATALOGUE_DIR = API_ROOT / "src" / "modules" / "diagrams" / "catalogue"
ALLOWLIST = CATALOGUE_DIR / "icon_allowlist.json"
CATALOGUE = CATALOGUE_DIR / "icon_catalogue.json"
FIXTURE = API_ROOT / "tests" / "fixtures" / "drawio_shape_index.json.gz"
CACHE_DIR = API_ROOT / ".cache"

_SHAPE = re.compile(r"(?:^|;)shape=([\w.]+)")
_RES = re.compile(r"(?:^|;)resIcon=([\w.]+)")
_PR = re.compile(r"(?:^|;)prIcon=([\w.]+)")
_IMAGE = re.compile(r"(?:^|;)image=([^;]+)")


def style_param(style: str, pattern: re.Pattern) -> str | None:
    match = pattern.search(style)
    return match.group(1) if match else None


def load_index(commit: str, repo: str, path: str, refresh: bool) -> list[dict]:
    CACHE_DIR.mkdir(exist_ok=True)
    cached = CACHE_DIR / f"drawio-search-index-{commit[:12]}.json"
    if refresh or not cached.exists():
        url = f"https://cdn.jsdelivr.net/gh/{repo}@{commit}/{path}"
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=60) as res:  # noqa: S310 - fixed https URL
            cached.write_bytes(res.read())
    data = json.loads(cached.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("unexpected index format: expected a JSON list")
    return [e for e in data if isinstance(e, dict) and isinstance(e.get("style"), str)]


def summarise(index: list[dict], commit: str) -> dict:
    shapes, res_icons, image_hashes = set(), set(), set()
    pr_icons: dict[str, set[str]] = {}
    for entry in index:
        style = entry["style"]
        shape = style_param(style, _SHAPE)
        if shape:
            shapes.add(shape)
        res = style_param(style, _RES)
        if res:
            res_icons.add(res)
        pr = style_param(style, _PR)
        if pr and shape:
            pr_icons.setdefault(shape, set()).add(pr)
        if shape == "image":
            image_hashes.add(hashlib.sha256(style.encode("utf-8")).hexdigest())
    return {
        "commit": commit,
        "shapes": sorted(shapes),
        "res_icons": sorted(res_icons),
        "pr_icons": {k: sorted(v) for k, v in sorted(pr_icons.items())},
        "image_style_sha256": sorted(image_hashes),
    }


def resolve(candidate: str, family: str, index: list[dict], names: dict) -> dict | None:
    kind, _, value = candidate.partition(":")
    if kind == "resIcon":
        if value in names["res_icons"]:
            return {"source": candidate, "shape_style": f"shape=mxgraph.aws4.resourceIcon;resIcon={value};"}
    elif kind == "shape":
        if value in names["shapes"]:
            return {"source": candidate, "shape_style": f"shape={value};"}
    elif kind == "prIcon":
        if value in names["pr_icons"].get("mxgraph.kubernetes.icon2", []):
            return {"source": candidate, "shape_style": f"shape=mxgraph.kubernetes.icon2;prIcon={value};"}
    elif kind == "image":
        tag = {"gcp": "gcp"}.get(family, family)
        for entry in index:
            style = entry["style"]
            if style_param(style, _SHAPE) != "image" or entry.get("title", "").lower() != value.lower():
                continue
            if tag not in str(entry.get("tags", "")).lower():
                continue
            image = style_param(style, _IMAGE) or ""
            if not image.startswith("data:image/"):
                continue  # remote images would be stripped by the SVG sanitiser and need network at render time
            return {
                "source": candidate,
                "shape_style": f"shape=image;aspect=fixed;imageAspect=0;image={image};",
                "index_style": style,
            }
    else:
        raise SystemExit(f"unknown candidate kind in {candidate!r}")
    return None


def build(refresh: bool) -> int:
    allow = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    pin = allow["index"]
    index = load_index(pin["commit"], pin["repo"], pin["path"], refresh)
    names = summarise(index, pin["commit"])
    names_sets = {**names, "shapes": set(names["shapes"]), "res_icons": set(names["res_icons"])}

    families = allow["families"]
    icons, missing = {}, []
    for item in allow["icons"]:
        key = item["key"]
        family = key.split(":", 1)[0] if ":" in key else "generic"
        if family not in families:
            raise SystemExit(f"{key}: unknown family {family!r}")
        resolved = None
        for candidate in item["candidates"]:
            resolved = resolve(candidate, family, index, names_sets)
            if resolved:
                break
        if not resolved:
            missing.append(f"{key}: none of {item['candidates']} is in the index")
            continue
        fam = families[family]
        is_tile = resolved["shape_style"].startswith("shape=mxgraph.aws4.resourceIcon") or "kubernetes.icon2" in resolved["shape_style"]
        icons[key] = {
            "family": family,
            "fill": item.get("fill") or fam.get("fill") or "#475569",
            "stroke": item.get("stroke") or fam.get("stroke") or ("#FFFFFF" if is_tile else "none"),
            "tile": is_tile,
            "aliases": item.get("aliases", []),
            **resolved,
        }
    if missing:
        print("\n".join(missing), file=sys.stderr)
        return 1

    CATALOGUE.write_text(
        json.dumps({"index_commit": pin["commit"], "icons": icons}, indent=1, sort_keys=False) + "\n", encoding="utf-8"
    )
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(names, separators=(",", ":")).encode("utf-8")
    with open(FIXTURE, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as fh:
        fh.write(payload)  # mtime=0: byte-identical output on every rebuild
    by_source = {}
    for icon in icons.values():
        kind = icon["source"].split(":", 1)[0]
        by_source[kind] = by_source.get(kind, 0) + 1
    print(f"wrote {len(icons)} icons to {CATALOGUE.relative_to(API_ROOT)} ({by_source})")
    print(f"wrote shape-name fixture to {FIXTURE.relative_to(API_ROOT)} ({FIXTURE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="download the pinned index again")
    sys.exit(build(parser.parse_args().refresh))
