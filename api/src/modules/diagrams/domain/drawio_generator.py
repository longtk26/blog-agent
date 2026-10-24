"""Deterministic draw.io XML from the computed geometry (E7-S3).

Edges carry explicit exit/entry points and waypoints, so draw.io shows exactly the routes the SVG shows; moving a
shape in draw.io re-routes only the edges attached to it.
"""

from xml.sax.saxutils import escape

from src.modules.diagrams.domain.geometry import (
    DiagramGeometry,
    NodeGeom,
    SequenceGeometry,
    build_geometry,
    build_sequence_geometry,
)
from src.modules.diagrams.domain.group_styles import group_style
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from src.modules.diagrams.domain.svg_renderer import BACKGROUND, BOX_STYLES, EDGE, LABEL_BG, TEXT

FONT_FAMILY = "Helvetica"


def _attr(value: object) -> str:
    return escape(str(value), {'"': "&quot;", "\n": "&#xa;"})


def _num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _html_lines(lines: list[str]) -> str:
    return "<br>".join(escape(line) for line in lines)


def _header(name: str, width: float, height: float) -> list[str]:
    return [
        '<mxfile host="app.diagrams.net" agent="blog-agent" version="24.0.0" type="device">',
        f'  <diagram id="diagram_1" name="{_attr(name)}">',
        f'    <mxGraphModel dx="{_num(width)}" dy="{_num(height)}" grid="1" gridSize="10" guides="1" tooltips="1" '
        f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{_num(width)}" pageHeight="{_num(height)}" '
        f'background="{BACKGROUND}" math="0" shadow="0">',
        "      <root>",
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]


_FOOTER = ["      </root>", "    </mxGraphModel>", "  </diagram>", "</mxfile>"]


def _vertex(cell_id: str, value: str, style: str, parent: str, x: float, y: float, w: float, h: float, extra: str = "") -> str:
    return (
        f'        <mxCell id="{_attr(cell_id)}" value="{_attr(value)}" style="{_attr(style)}" vertex="1" '
        f'parent="{_attr(parent)}"{extra}>\n'
        f'          <mxGeometry x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{_num(h)}" as="geometry" />\n'
        "        </mxCell>"
    )


def _node_style(node: NodeGeom) -> str:
    if node.icon is not None:
        label = (
            "verticalLabelPosition=bottom;verticalAlign=top;align=center;"
            if node.label_side == "bottom"
            else "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=6;"
        )
        return (
            f"sketch=0;outlineConnect=0;gradientColor=none;fillColor={node.icon.color};strokeColor=#ffffff;dashed=0;"
            f"html=1;fontSize=12;fontStyle=0;fontColor={TEXT};fontFamily={FONT_FAMILY};aspect=fixed;{label}"
            f"{node.icon.drawio_shape}"
        )
    fill, stroke = BOX_STYLES.get(node.kind, BOX_STYLES["process"])
    shape = {
        "decision": "rhombus;",
        "datastore": "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=7;",
        "note": "shape=note;size=12;",
    }.get(node.kind, "rounded=1;arcSize=14;")
    font = "#713F12" if node.kind == "note" else TEXT
    dashed = "dashed=1;" if node.kind == "external" else ""
    bold = "fontStyle=1;" if node.kind in ("process", "service", "decision") else ""
    return (
        f"{shape}whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1.6;fontColor={font};"
        f"fontSize=12;fontFamily={FONT_FAMILY};{bold}{dashed}"
    )


def generate_drawio_xml(spec: DiagramSpec, geometry: DiagramGeometry | SequenceGeometry | None = None) -> str:
    """Generate valid draw.io XML (.drawio) deterministically from a DiagramSpec."""
    if spec.type == "sequence":
        return _sequence_xml(spec, geometry if isinstance(geometry, SequenceGeometry) else build_sequence_geometry(spec))
    if not isinstance(geometry, DiagramGeometry):
        geometry = build_geometry(spec)
    return _flow_xml(spec, geometry)


def _flow_xml(spec: DiagramSpec, g: DiagramGeometry) -> str:
    lines = _header(spec.title, g.width, g.height)
    if g.title:
        lines.append(
            _vertex(
                "diagram_title", g.title.text,
                f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;fontSize=16;fontStyle=1;"
                f"fontColor=#F1F5F9;fontFamily={FONT_FAMILY};",
                "1", g.title.rect.x, g.title.rect.y - 2, g.title.rect.w + 20, g.title.rect.h + 6,
            )
        )

    rects = {grp.id: grp.rect for grp in g.groups}
    for grp in g.groups:
        parent = grp.parent if grp.parent in rects else "1"
        ox, oy = (rects[parent].x, rects[parent].y) if parent != "1" else (0, 0)
        r = grp.rect
        lines.append(
            _vertex(grp.id, grp.title, group_style(grp.title).drawio, parent, r.x - ox, r.y - oy, r.w, r.h, ' container="1"')
        )

    for node in g.nodes.values():
        parent = node.group if node.group in rects else "1"
        ox, oy = (rects[parent].x, rects[parent].y) if parent != "1" else (0, 0)
        b = node.body
        value = _html_lines(node.lines)
        lines.append(_vertex(node.id, value, _node_style(node), parent, b.x - ox, b.y - oy, b.w, b.h))

    for edge in g.edges:
        src, tgt = g.nodes[edge.source].body, g.nodes[edge.target].body
        (sx, sy), (tx, ty) = edge.points[0], edge.points[-1]
        exit_x, exit_y = (sx - src.x) / src.w, (sy - src.y) / src.h
        entry_x, entry_y = (tx - tgt.x) / tgt.w, (ty - tgt.y) / tgt.h
        arrows = {"both": "startArrow=block;startFill=1;endArrow=block;endFill=1;", "none": "startArrow=none;endArrow=none;"}
        style = (
            f"edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeColor={EDGE};"
            f"strokeWidth=1.6;fontColor=#CBD5E1;fontSize=11;fontFamily={FONT_FAMILY};labelBackgroundColor={LABEL_BG};"
            f"labelBorderColor=#334155;{arrows.get(edge.arrow, 'endArrow=block;endFill=1;')}"
            f"{'dashed=1;' if edge.dashed else ''}"
            f"exitX={exit_x:.4f};exitY={exit_y:.4f};exitDx=0;exitDy=0;exitPerimeter=0;"
            f"entryX={entry_x:.4f};entryY={entry_y:.4f};entryDx=0;entryDy=0;entryPerimeter=0;"
        )
        waypoints = "".join(f'<mxPoint x="{_num(x)}" y="{_num(y)}" />' for x, y in edge.points[1:-1])
        label_x = f' x="{edge.label_at * 2 - 1:.4f}"' if edge.lines else ""
        lines.append(
            f'        <mxCell id="{_attr(edge.id)}" value="{_attr(_html_lines(edge.lines))}" style="{_attr(style)}" '
            f'edge="1" parent="1" source="{_attr(edge.source)}" target="{_attr(edge.target)}">\n'
            f'          <mxGeometry{label_x} relative="1" as="geometry">'
            + (f'<Array as="points">{waypoints}</Array>' if waypoints else "")
            + "</mxGeometry>\n        </mxCell>"
        )
    lines.extend(_FOOTER)
    return "\n".join(lines)


def _sequence_xml(spec: DiagramSpec, g: SequenceGeometry) -> str:
    lines = _header(spec.title, g.width, g.height)
    if g.title:
        lines.append(
            _vertex(
                "diagram_title", g.title.text,
                f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;fontSize=16;fontStyle=1;"
                f"fontColor=#F1F5F9;fontFamily={FONT_FAMILY};",
                "1", g.title.rect.x, g.title.rect.y - 2, g.title.rect.w + 20, g.title.rect.h + 6,
            )
        )
    for p in g.participants:
        stroke = "#FB7185" if p.actor else "#38BDF8"
        style = (
            "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;container=1;dropTarget=0;"
            "collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={};"
            f"size={_num(p.head.h)};fillColor=#1E293B;strokeColor={stroke};fontColor={TEXT};fontStyle=1;"
            f"fontFamily={FONT_FAMILY};"
        )
        lines.append(
            _vertex(p.id, _html_lines(p.lines), style, "1", p.head.x, p.head.y, p.head.w, g.lifeline_bottom - p.head.y)
        )
    for m in g.messages:
        dashed = "dashed=1;endArrow=open;" if m.dashed else ("endArrow=open;" if m.async_msg else "endArrow=block;endFill=1;")
        stroke = EDGE if m.dashed else "#38BDF8"
        style = (
            f"html=1;verticalAlign=bottom;strokeColor={stroke};strokeWidth=1.6;fontColor=#CBD5E1;fontSize=11;"
            f"fontFamily={FONT_FAMILY};{dashed}"
        )
        (x1, y1), (x2, y2) = m.points[0], m.points[-1]
        waypoints = "".join(f'<mxPoint x="{_num(x)}" y="{_num(y)}" />' for x, y in m.points[1:-1])
        lines.append(
            f'        <mxCell id="{_attr(m.id)}" value="{_attr(_html_lines(m.lines))}" style="{_attr(style)}" '
            'edge="1" parent="1">\n'
            '          <mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{_num(x1)}" y="{_num(y1)}" as="sourcePoint" />'
            f'<mxPoint x="{_num(x2)}" y="{_num(y2)}" as="targetPoint" />'
            + (f'<Array as="points">{waypoints}</Array>' if waypoints else "")
            + "</mxGeometry>\n        </mxCell>"
        )
    for n in g.notes:
        lines.append(
            _vertex(
                n.id, _html_lines(n.lines),
                f"shape=note;size=10;whiteSpace=wrap;html=1;fillColor=#FEF08A;strokeColor=#CA8A04;fontColor=#713F12;"
                f"fontFamily={FONT_FAMILY};",
                "1", n.rect.x, n.rect.y, n.rect.w, n.rect.h,
            )
        )
    lines.extend(_FOOTER)
    return "\n".join(lines)
