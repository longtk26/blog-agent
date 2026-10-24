"""Output port for rendering diagrams to SVG and PNG (E7-S4)."""

from abc import ABC, abstractmethod
from pydantic import BaseModel


class RenderResult(BaseModel):
    svg: str
    png_bytes: bytes | None = None
    sha256: str = ""


class IDiagramRenderer(ABC):
    @abstractmethod
    async def render_drawio(self, xml_content: str, embed_diagram: bool = True) -> RenderResult:
        """Render draw.io XML to SVG with diagram embedded, and PNG at 2x."""
        ...

    @abstractmethod
    async def render_png(self, svg: str, scale: float = 2) -> bytes | None:
        """Rasterise an SVG (generated diagrams are drawn in Python); None when the renderer is unavailable."""
        ...

    @abstractmethod
    async def render_mermaid(self, mermaid_code: str) -> RenderResult:
        """Render Mermaid code to SVG and PNG."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if renderer service is healthy and responsive."""
        ...
