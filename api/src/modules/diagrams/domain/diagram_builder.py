"""One geometry, two outputs: the editable draw.io source and the published SVG."""

from dataclasses import dataclass

from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.geometry import build_geometry, build_sequence_geometry
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from src.modules.diagrams.domain.svg_renderer import render_sequence_svg, render_svg


@dataclass
class BuiltDiagram:
    drawio_xml: str
    svg: str
    width: float
    height: float


def build_diagram(spec: DiagramSpec) -> BuiltDiagram:
    if spec.type == "sequence":
        geometry = build_sequence_geometry(spec)
        xml = generate_drawio_xml(spec, geometry)
        return BuiltDiagram(xml, render_sequence_svg(geometry, xml), geometry.width, geometry.height)
    geometry = build_geometry(spec)
    xml = generate_drawio_xml(spec, geometry)
    return BuiltDiagram(xml, render_svg(geometry, xml), geometry.width, geometry.height)
