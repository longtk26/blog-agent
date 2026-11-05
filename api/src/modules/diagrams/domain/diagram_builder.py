"""Spec -> geometry -> editable draw.io XML. draw.io itself renders the published SVG/PNG (E10-S2)."""

from dataclasses import dataclass

from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.geometry import (
    DiagramGeometry,
    SequenceGeometry,
    build_geometry,
    build_sequence_geometry,
)
from src.modules.diagrams.domain.layout_lint import LintFinding, lint_geometry
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec


@dataclass
class BuiltDiagram:
    drawio_xml: str
    geometry: DiagramGeometry | SequenceGeometry
    width: float
    height: float

    @property
    def lint(self) -> list[LintFinding]:
        return lint_geometry(self.geometry) if isinstance(self.geometry, DiagramGeometry) else []


def build_diagram(spec: DiagramSpec) -> BuiltDiagram:
    geometry = build_sequence_geometry(spec) if spec.type == "sequence" else build_geometry(spec)
    xml = generate_drawio_xml(spec, geometry)
    return BuiltDiagram(xml, geometry, geometry.width, geometry.height)

