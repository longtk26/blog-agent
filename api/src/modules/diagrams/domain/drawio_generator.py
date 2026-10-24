"""Deterministic draw.io XML generator with owner_dark palette (E7-S3)."""

from xml.sax.saxutils import escape

from src.modules.diagrams.domain.layout import compute_layout, LayoutResult
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec, DiagramNode, DiagramEdge

# owner_dark style preset styles
NODE_STYLES_OWNER_DARK = {
    "process": (
        "rounded=1;whiteSpace=wrap;html=1;fillColor=#1E293B;strokeColor=#38BDF8;"
        "strokeWidth=2;fontColor=#F8FAFC;fontStyle=1;align=center;"
    ),
    "decision": (
        "rhombus;whiteSpace=wrap;html=1;fillColor=#1E293B;strokeColor=#FBBF24;"
        "strokeWidth=2;fontColor=#F8FAFC;fontStyle=1;align=center;"
    ),
    "datastore": (
        "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;"
        "fillColor=#1E293B;strokeColor=#4ADE80;strokeWidth=2;fontColor=#F8FAFC;fontStyle=1;align=center;"
    ),
    "service": (
        "rounded=1;whiteSpace=wrap;html=1;fillColor=#0F172A;strokeColor=#818CF8;"
        "strokeWidth=2;fontColor=#F8FAFC;fontStyle=1;align=center;"
    ),
    "actor": (
        "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
        "fillColor=#1E293B;strokeColor=#FB7185;strokeWidth=2;fontColor=#F8FAFC;"
    ),
    "external": (
        "rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#1E293B;strokeColor=#94A3B8;"
        "strokeWidth=2;fontColor=#CBD5E1;align=center;"
    ),
    "note": (
        "shape=note;whiteSpace=wrap;html=1;size=14;fillColor=#FEF08A;strokeColor=#CA8A04;"
        "fontColor=#713F12;align=left;spacingLeft=5;"
    ),
}

GROUP_STYLE_OWNER_DARK = (
    "swimlane;whiteSpace=wrap;html=1;fillColor=#0F172A;strokeColor=#334155;strokeWidth=1.5;"
    "fontColor=#94A3B8;fontStyle=1;rounded=1;arcSize=4;collapsible=0;"
)

EDGE_BASE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;"
    "strokeColor=#94A3B8;strokeWidth=2;fontColor=#F8FAFC;"
)


def _attr(val: str | None) -> str:
    if val is None:
        return ""
    return escape(str(val), {'"': "&quot;", "\n": "&#xa;"})


def generate_drawio_xml(spec: DiagramSpec, layout: LayoutResult | None = None) -> str:
    """Generate valid draw.io XML (.drawio) deterministically from DiagramSpec."""
    if layout is None:
        layout = compute_layout(spec)

    if spec.type == "sequence":
        return _generate_sequence_xml(spec, layout)

    return _generate_flowchart_xml(spec, layout)


def _generate_flowchart_xml(spec: DiagramSpec, layout: LayoutResult) -> str:
    diagram_id = "diagram_1"
    diagram_name = _attr(spec.title)

    lines = [
        '<mxfile host="app.diagrams.net" agent="blog-agent" version="24.0.0" type="device">',
        f'  <diagram id="{diagram_id}" name="{diagram_name}">',
        f'    <mxGraphModel dx="{layout.total_width}" dy="{layout.total_height}" grid="1" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{layout.total_width}" pageHeight="{layout.total_height}" math="0" shadow="0">',
        '      <root>',
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]

    # 1. Groups / Swimlanes
    # Map group to parent group (or root 1)
    group_parents: dict[str, str] = {g.id: (g.parent if g.parent else "1") for g in spec.groups}

    for group in spec.groups:
        grect = layout.groups.get(group.id)
        if not grect:
            continue
        pid = group_parents.get(group.id, "1")
        lines.append(
            f'        <mxCell id="{_attr(group.id)}" value="{_attr(group.label)}" '
            f'style="{GROUP_STYLE_OWNER_DARK}" vertex="1" parent="{_attr(pid)}" container="1">\n'
            f'          <mxGeometry x="{grect.x}" y="{grect.y}" width="{grect.width}" height="{grect.height}" as="geometry" />\n'
            '        </mxCell>'
        )

    # 2. Nodes
    for node in spec.nodes:
        nrect = layout.nodes.get(node.id)
        if not nrect:
            continue
        pid = node.group if node.group and node.group in layout.groups else "1"
        style = NODE_STYLES_OWNER_DARK.get(node.kind, NODE_STYLES_OWNER_DARK["process"])
        
        # Relative coordinates if child of group
        if pid != "1" and pid in layout.groups:
            parent_rect = layout.groups[pid]
            rel_x = max(10, nrect.x - parent_rect.x)
            rel_y = max(30, nrect.y - parent_rect.y)
        else:
            rel_x = nrect.x
            rel_y = nrect.y

        lines.append(
            f'        <mxCell id="{_attr(node.id)}" value="{_attr(node.label)}" '
            f'style="{style}" vertex="1" parent="{_attr(pid)}">\n'
            f'          <mxGeometry x="{rel_x}" y="{rel_y}" width="{nrect.width}" height="{nrect.height}" as="geometry" />\n'
            '        </mxCell>'
        )

    # 3. Edges
    for idx, edge in enumerate(spec.edges):
        edge_id = f"e{idx}_{edge.from_node}_{edge.to_node}"
        style_parts = [EDGE_BASE_STYLE]
        if edge.style == "dashed":
            style_parts.append("dashed=1;strokeDasharray=4;")
        
        if edge.arrow == "both":
            style_parts.append("startArrow=block;endArrow=block;")
        elif edge.arrow == "none":
            style_parts.append("startArrow=none;endArrow=none;")
        else:
            style_parts.append("endArrow=block;")

        edge_style = "".join(style_parts)
        edge_label = _attr(edge.label) if edge.label else ""

        lines.append(
            f'        <mxCell id="{_attr(edge_id)}" value="{edge_label}" '
            f'style="{edge_style}" edge="1" parent="1" '
            f'source="{_attr(edge.from_node)}" target="{_attr(edge.to_node)}">\n'
            '          <mxGeometry relative="1" as="geometry" />\n'
            '        </mxCell>'
        )

    lines.extend([
        '      </root>',
        '    </mxGraphModel>',
        '  </diagram>',
        '</mxfile>',
    ])
    return "\n".join(lines)


def _generate_sequence_xml(spec: DiagramSpec, layout: LayoutResult) -> str:
    diagram_id = "diagram_seq"
    diagram_name = _attr(spec.title)

    lines = [
        '<mxfile host="app.diagrams.net" agent="blog-agent" version="24.0.0" type="device">',
        f'  <diagram id="{diagram_id}" name="{diagram_name}">',
        f'    <mxGraphModel dx="{layout.total_width}" dy="{layout.total_height}" grid="1" gridSize="10" '
        'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{layout.total_width}" pageHeight="{layout.total_height}" math="0" shadow="0">',
        '      <root>',
        '        <mxCell id="0" />',
        '        <mxCell id="1" parent="0" />',
    ]

    # Lifelines
    for idx, p in enumerate(spec.participants):
        nrect = layout.nodes[p.id]
        if p.actor:
            p_style = (
                "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;"
                "container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;"
                "portConstraint=eastwest;size=40;participant=umlActor;verticalAlign=bottom;"
                "fillColor=#1E293B;strokeColor=#FB7185;fontColor=#F8FAFC;"
            )
        else:
            p_style = (
                "shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;html=1;"
                "container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;"
                "portConstraint=eastwest;size=40;fillColor=#1E293B;strokeColor=#38BDF8;fontColor=#F8FAFC;"
            )

        lines.append(
            f'        <mxCell id="{_attr(p.id)}" value="{_attr(p.label)}" '
            f'style="{p_style}" vertex="1" parent="1">\n'
            f'          <mxGeometry x="{nrect.x}" y="{nrect.y}" width="{nrect.width}" height="{nrect.height}" as="geometry" />\n'
            '        </mxCell>'
        )

    # Messages
    for idx, msg in enumerate(spec.messages):
        msg_id = f"m_{idx}"
        y_pos = 120 + idx * 50
        from_rect = layout.nodes.get(msg.from_node)
        to_rect = layout.nodes.get(msg.to_node)
        x_from = from_rect.x + from_rect.width // 2 if from_rect else 100
        x_to = to_rect.x + to_rect.width // 2 if to_rect else 300

        if msg.return_msg:
            m_style = "html=1;verticalAlign=bottom;endArrow=open;dashed=1;strokeColor=#94A3B8;strokeWidth=2;fontColor=#F8FAFC;"
        elif msg.async_msg:
            m_style = "html=1;verticalAlign=bottom;endArrow=open;strokeColor=#38BDF8;strokeWidth=2;fontColor=#F8FAFC;"
        else:
            m_style = "html=1;verticalAlign=bottom;endArrow=block;strokeColor=#38BDF8;strokeWidth=2;fontColor=#F8FAFC;"

        lines.append(
            f'        <mxCell id="{_attr(msg_id)}" value="{_attr(msg.label)}" '
            f'style="{m_style}" edge="1" parent="1">\n'
            f'          <mxGeometry relative="1" as="geometry">\n'
            f'            <mxPoint x="{x_from}" y="{y_pos}" as="sourcePoint" />\n'
            f'            <mxPoint x="{x_to}" y="{y_pos}" as="targetPoint" />\n'
            '          </mxGeometry>\n'
            '        </mxCell>'
        )

    lines.extend([
        '      </root>',
        '    </mxGraphModel>',
        '  </diagram>',
        '</mxfile>',
    ])
    return "\n".join(lines)
