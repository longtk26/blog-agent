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
                res = await client.post(
                    f"{self.base_url}/render/drawio",
                    json={"xml": xml_content, "embed_diagram": embed_diagram, "format": "both"},
                )
                if res.status_code == 200:
                    data = res.json()
                    svg = sanitize_svg_content(data.get("svg", ""))
                    png_b64 = data.get("png_base64")
                    png_bytes = base64.b64decode(png_b64) if png_b64 else None
                    sha = data.get("sha256") or hashlib.sha256(svg.encode("utf-8")).hexdigest()
                    return RenderResult(svg=svg, png_bytes=png_bytes, sha256=sha)
                else:
                    raise DiagramRendererException(f"draw.io render failed: {res.text}")
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.warning(f"Diagram renderer service is unavailable at {self.base_url}: {exc}")
            # Fallback: create standalone embedded SVG so workflow continues gracefully
            return self._fallback_drawio_embed(xml_content)
        except DiagramRendererException:
            raise
        except Exception as exc:
            logger.warning(f"Diagram render error: {exc}")
            return self._fallback_drawio_embed(xml_content)

    async def render_png(self, svg: str, scale: float = 2) -> bytes | None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/render/png", json={"svg": svg, "scale": scale})
            if res.status_code == 200:
                data = res.json().get("png_base64")
                return base64.b64decode(data) if data else None
            logger.warning(f"PNG render failed: {res.text[:300]}")
        except Exception as exc:
            # The SVG is the published asset; a missing PNG only affects Dev.to and can be regenerated.
            logger.warning(f"PNG render unavailable: {exc}")
        return None

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

    @staticmethod
    def _fallback_drawio_embed(xml_content: str) -> RenderResult:
        """Create an SVG container embedding draw.io XML so it opens in diagrams.net."""
        escaped_xml = xml_content.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'version="1.1" width="100%" height="100%" viewBox="0 0 1200 800" content="{escaped_xml}">\n'
            f'  <rect width="100%" height="100%" fill="#0F172A" rx="8" />\n'
            f'  <text x="50%" y="50%" fill="#94A3B8" font-family="sans-serif" font-size="16" '
            f'text-anchor="middle" dominant-baseline="middle">draw.io diagram source embedded (open in diagrams.net)</text>\n'
            f'</svg>'
        )
        sha = hashlib.sha256(svg.encode("utf-8")).hexdigest()
        return RenderResult(svg=svg, png_bytes=None, sha256=sha)


DiagramRendererDep = Annotated[IDiagramRenderer, Depends(DiagramRendererAdapter)]
