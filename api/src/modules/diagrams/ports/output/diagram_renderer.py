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
        """Export draw.io XML with draw.io itself (E10-S1): SVG + 2x PNG, the diagram XML embedded in both.

        Raises RendererUnavailableException when the renderer cannot be reached, DiagramRendererException when the
        export fails. Never returns a placeholder: a published diagram is always the real render.
        """
        ...

    @abstractmethod
    async def render_mermaid(self, mermaid_code: str) -> RenderResult:
        """Render Mermaid code to SVG and PNG."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if renderer service is healthy and responsive."""
        ...
