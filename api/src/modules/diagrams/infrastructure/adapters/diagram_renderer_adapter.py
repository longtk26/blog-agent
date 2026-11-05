"""HTTP client adapter implementing IDiagramRenderer talking to the renderer service (E7-S4)."""

import base64
import hashlib
from typing import Annotated
from fastapi import Depends
import httpx

from src.configs.config import config
from src.configs.logger import get_logger
from src.modules.diagrams.domain.svg_sanitizer import sanitize_svg_content
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer, RenderResult

logger = get_logger(__name__)


class DiagramRendererException(Exception):
    """Raised when rendering fails or syntax error occurs."""
    pass


class RendererUnavailableException(DiagramRendererException):
    """Raised when the renderer service is unreachable."""
    pass


class DiagramRendererAdapter(IDiagramRenderer):
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or config.diagram_renderer_url).rstrip("/")
        self.timeout = timeout or config.diagram_render_timeout

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def render_drawio(self, xml_content: str, embed_diagram: bool = True) -> RenderResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/render/drawio", json={"xml": xml_content})
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.warning(f"Diagram renderer service is unavailable at {self.base_url}: {exc}")
            raise RendererUnavailableException("Renderer service is unavailable") from exc
        except httpx.TimeoutException as exc:
            raise DiagramRendererException(f"draw.io render timed out after {self.timeout}s") from exc
        if res.status_code != 200:
            raise DiagramRendererException(f"draw.io render failed ({res.status_code}): {res.text[:500]}")
        data = res.json()
        svg = sanitize_svg_content(data.get("svg", ""))
        if "<svg" not in svg:
            raise DiagramRendererException("draw.io render returned no SVG")
        png_b64 = data.get("png_base64")
        png_bytes = base64.b64decode(png_b64) if png_b64 else None
        # Hash what we store (the API-side sanitised SVG), so the revision hash matches the published file.
        sha = hashlib.sha256(svg.encode("utf-8")).hexdigest()
        return RenderResult(svg=svg, png_bytes=png_bytes, sha256=sha)

    async def render_mermaid(self, mermaid_code: str) -> RenderResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.base_url}/render/mermaid",
                    json={"code": mermaid_code, "format": "both"},
                )
                if res.status_code == 200:
                    data = res.json()
                    svg = sanitize_svg_content(data.get("svg", ""))
                    png_b64 = data.get("png_base64")
                    png_bytes = base64.b64decode(png_b64) if png_b64 else None
                    sha = data.get("sha256") or hashlib.sha256(svg.encode("utf-8")).hexdigest()
                    return RenderResult(svg=svg, png_bytes=png_bytes, sha256=sha)
                elif res.status_code == 400:
                    err_data = res.json() if res.headers.get("content-type") == "application/json" else {}
                    msg = err_data.get("message") or res.text
                    raise DiagramRendererException(f"Mermaid syntax error: {msg}")
                else:
                    raise DiagramRendererException(f"Mermaid render failed: {res.text}")
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.warning(f"Diagram renderer service is unavailable at {self.base_url}: {exc}")
            raise RendererUnavailableException("Renderer service is unavailable")


DiagramRendererDep = Annotated[IDiagramRenderer, Depends(DiagramRendererAdapter)]
