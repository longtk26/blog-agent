"""Find the bytes behind an image reference in article Markdown (shared by the Sanity and S3 uploaders).

Accepted references: ``asset://<diagram asset id>``, a path under ``BLOGS_DIR`` / ``DATA_DIR`` (or the
container's ``/app/data/``), and ``data:`` URIs.
"""

import base64
import hashlib
import mimetypes
import uuid
from pathlib import Path

from src.configs import config


async def _diagram_asset(asset_id: str):
    try:
        from src.libs.database import arun_in_session
        from src.modules.diagrams.infrastructure.persistence.diagram_asset_repository import (
            DiagramAssetRepository,
        )

        aid = uuid.UUID(asset_id)
        return await arun_in_session(lambda s: DiagramAssetRepository(s).get(aid))
    except Exception:
        return None


async def resolve_asset(src: str, prefer_raster: bool = False) -> tuple[bytes, str, str]:
    """Return ``(bytes, filename, mime)``.

    ``prefer_raster`` picks a diagram's PNG over its SVG when both exist (Dev.to shows raster images more
    reliably and only accepts raster for ``main_image``). Without it, the historical Sanity behaviour is kept:
    the first file matching the asset id, then the asset's SVG."""
    if src.startswith("asset://"):
        asset_id = src.replace("asset://", "").strip()
        assets_dir = Path(config.data_dir) / "assets"
        matches = sorted(p for p in assets_dir.glob(f"**/*{asset_id}*") if p.is_file()) if assets_dir.exists() else []
        if prefer_raster:
            asset = await _diagram_asset(asset_id)
            if asset and asset.png_path and Path(asset.png_path).is_file():
                p = Path(asset.png_path)
                return p.read_bytes(), p.name, "image/png"
            pngs = [p for p in matches if p.suffix.lower() == ".png"]
            if pngs:
                return pngs[0].read_bytes(), pngs[0].name, "image/png"
        if matches:
            p = matches[0]
            mime, _ = mimetypes.guess_type(p.name)
            return p.read_bytes(), p.name, mime or "image/svg+xml"
        asset = await _diagram_asset(asset_id)
        if asset and asset.svg_path and Path(asset.svg_path).is_file():
            p = Path(asset.svg_path)
            return p.read_bytes(), p.name, "image/svg+xml"

    blogs_dir = Path(config.blogs_dir)
    candidate_paths = [
        Path(src),
        blogs_dir / src.lstrip("/"),
        Path(config.data_dir) / src.lstrip("/"),
    ]
    if src.startswith("/app/data/"):
        candidate_paths.append(Path(config.data_dir) / src[len("/app/data/") :].lstrip("/"))
    for p in candidate_paths:
        if p.is_file():
            mime, _ = mimetypes.guess_type(p.name)
            return p.read_bytes(), p.name, mime or "application/octet-stream"

    if src.startswith("data:"):
        header, _, b64_data = src.partition(",")
        content = base64.b64decode(b64_data)
        mime = header.split(";")[0].replace("data:", "") if ";" in header else "image/png"
        ext = mimetypes.guess_extension(mime) or ".png"
        return content, f"image_{hashlib.sha256(content).hexdigest()[:8]}{ext}", mime

    raise FileNotFoundError(f"Local asset not found: {src}")
