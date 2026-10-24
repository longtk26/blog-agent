"""SVG rendering of a computed diagram geometry in the owner_dark theme (E7-S4).

The SVG embeds the draw.io source in its `content` attribute (diagrams.net convention), so the published image
can still be opened and edited in draw.io.
"""

from xml.sax.saxutils import escape

from src.modules.diagrams.domain.geometry import (
    EDGE_FONT,
    EDGE_LINE_HEIGHT,
    LINE_HEIGHT,
    NODE_FONT,
    TITLE_FONT,
    DiagramGeometry,
    EdgeGeom,
    GroupGeom,
    NodeGeom,
    SequenceGeometry,
)
from src.modules.diagrams.domain.group_styles import group_style

FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
BACKGROUND = "#0B1120"
TEXT = "#E2E8F0"
MUTED = "#94A3B8"
EDGE = "#94A3B8"
LABEL_BG = "#0B1120"
LABEL_BORDER = "#334155"

BOX_STYLES = {
    "process": ("#1E293B", "#38BDF8"),
    "service": ("#1E293B", "#818CF8"),
    "datastore": ("#1E293B", "#4ADE80"),
    "decision": ("#1E293B", "#FBBF24"),
    "external": ("#1E293B", "#94A3B8"),
    "actor": ("#1E293B", "#FB7185"),
    "note": ("#FEF08A", "#CA8A04"),
}


def _t(value: str) -> str:
    return escape(str(value))


def _num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _text_lines(lines: list[str], cx: float, top: float, size: float, line_height: float, fill: str, weight: int = 500) -> str:
    spans = "".join(
        f'<tspan x="{_num(cx)}" y="{_num(top + line_height * i + size)}">{_t(line)}</tspan>' for i, line in enumerate(lines)
    )
    return f'<text text-anchor="middle" font-size="{size}" font-weight="{weight}" fill="{fill}">{spans}</text>'


def _rounded_path(points: list[tuple[float, float]], radius: float = 6) -> str:
    if len(points) < 3:
        return "M " + " L ".join(f"{_num(x)} {_num(y)}" for x, y in points)
    parts = [f"M {_num(points[0][0])} {_num(points[0][1])}"]
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = points[i - 1], points[i], points[i + 1]
        d1 = abs(x1 - x0) + abs(y1 - y0)
        d2 = abs(x2 - x1) + abs(y2 - y1)
        r = min(radius, d1 / 2, d2 / 2)
        ax = x1 - (x1 - x0) / d1 * r if d1 else x1
        ay = y1 - (y1 - y0) / d1 * r if d1 else y1
        bx = x1 + (x2 - x1) / d2 * r if d2 else x1
        by = y1 + (y2 - y1) / d2 * r if d2 else y1
        parts.append(f"L {_num(ax)} {_num(ay)} Q {_num(x1)} {_num(y1)} {_num(bx)} {_num(by)}")
    parts.append(f"L {_num(points[-1][0])} {_num(points[-1][1])}")
    return " ".join(parts)


def _group(g: GroupGeom) -> str:
    style = group_style(g.title)
    r = g.rect
    dash = ' stroke-dasharray="6 4"' if style.dashed else ""
    out = [
        f'<rect x="{_num(r.x)}" y="{_num(r.y)}" width="{_num(r.w)}" height="{_num(r.h)}" rx="6" '
        f'fill="{style.color}" fill-opacity="0.05" stroke="{style.color}" stroke-width="1.4"{dash}/>'
    ]
    text_x = r.x + 12
    if style.badge:
        out.append(f'<rect x="{_num(r.x)}" y="{_num(r.y)}" width="24" height="24" rx="4" fill="{style.color}"/>')
        out.append(
            f'<g transform="translate({_num(r.x + 4)},{_num(r.y + 4)}) scale(0.667)" fill="none" stroke="#FFFFFF" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{style.badge}</g>'
        )
        text_x = r.x + 32
    out.append(
        f'<text x="{_num(text_x)}" y="{_num(r.y + 17)}" font-size="12" font-weight="700" fill="{style.text}">{_t(g.title)}</text>'
    )
    return "\n".join(out)


def _box_shape(node: NodeGeom) -> str:
    r = node.body
    fill, stroke = BOX_STYLES.get(node.kind, BOX_STYLES["process"])
    if node.kind == "decision":
        pts = f"{_num(r.cx)},{_num(r.y)} {_num(r.x2)},{_num(r.cy)} {_num(r.cx)},{_num(r.y2)} {_num(r.x)},{_num(r.cy)}"
        return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" stroke-linejoin="round"/>'
    if node.kind == "datastore":
        ry = 7
        body = (
            f"M {_num(r.x)} {_num(r.y + ry)} A {_num(r.w / 2)} {ry} 0 0 1 {_num(r.x2)} {_num(r.y + ry)} "
            f"V {_num(r.y2 - ry)} A {_num(r.w / 2)} {ry} 0 0 1 {_num(r.x)} {_num(r.y2 - ry)} Z"
        )
        rim = f"M {_num(r.x)} {_num(r.y + ry)} A {_num(r.w / 2)} {ry} 0 0 0 {_num(r.x2)} {_num(r.y + ry)}"
        return (
            f'<path d="{body}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
            f'<path d="{rim}" fill="none" stroke="{stroke}" stroke-width="1.6"/>'
        )
    dash = ' stroke-dasharray="5 4"' if node.kind == "external" else ""
    return (
        f'<rect x="{_num(r.x)}" y="{_num(r.y)}" width="{_num(r.w)}" height="{_num(r.h)}" rx="8" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/>'
    )


def _node(node: NodeGeom) -> str:
    r = node.body
    if node.icon is not None:
        out = [
            f'<rect x="{_num(r.x)}" y="{_num(r.y)}" width="{_num(r.w)}" height="{_num(r.h)}" rx="6" fill="{node.icon.color}"/>',
            f'<g transform="translate({_num(r.x + 10)},{_num(r.y + 10)}) scale(1.167)" fill="none" stroke="#FFFFFF" '
            f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{node.icon.glyph}</g>',
        ]
        label = node.label
        if node.label_side == "bottom":
            out.append(_text_lines(node.lines, label.cx, label.y, NODE_FONT, LINE_HEIGHT, TEXT))
        else:
            spans = "".join(
                f'<tspan x="{_num(label.x)}" y="{_num(label.y + LINE_HEIGHT * i + NODE_FONT)}">{_t(line)}</tspan>'
                for i, line in enumerate(node.lines)
            )
            out.append(f'<text font-size="{NODE_FONT}" font-weight="500" fill="{TEXT}">{spans}</text>')
        return "\n".join(out)
    text_fill = "#713F12" if node.kind == "note" else TEXT
    top = r.cy - len(node.lines) * LINE_HEIGHT / 2 - 2
    weight = 600 if node.kind in ("process", "service", "decision") else 500
    return _box_shape(node) + "\n" + _text_lines(node.lines, r.cx, top, NODE_FONT, LINE_HEIGHT, text_fill, weight)


def _edge(edge: EdgeGeom) -> str:
    dash = ' stroke-dasharray="6 4"' if edge.dashed else ""
    start = ' marker-start="url(#arrow)"' if edge.arrow == "both" else ""
    end = ' marker-end="url(#arrow)"' if edge.arrow in ("one", "both") else ""
    out = [f'<path d="{_rounded_path(edge.points)}" fill="none" stroke="{EDGE}" stroke-width="1.6"{dash}{start}{end}/>']
    if edge.label and edge.lines:
        lb = edge.label
        out.append(
            f'<rect x="{_num(lb.x)}" y="{_num(lb.y)}" width="{_num(lb.w)}" height="{_num(lb.h)}" rx="4" '
            f'fill="{LABEL_BG}" stroke="{LABEL_BORDER}" stroke-width="0.8"/>'
        )
        out.append(_text_lines(edge.lines, lb.cx, lb.y + 2, EDGE_FONT, EDGE_LINE_HEIGHT, "#CBD5E1"))
    return "\n".join(out)


def _document(width: float, height: float, body: list[str], drawio_xml: str | None) -> str:
    content = f' content="{escape(drawio_xml, {chr(34): "&quot;"})}"' if drawio_xml else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{_num(width)}" height="{_num(height)}" '
        f'viewBox="0 0 {_num(width)} {_num(height)}" font-family="{FONT}"{content}>\n'
        "<defs>\n"
        '  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M 0 1 L 10 5 L 0 9 z" fill="{EDGE}"/></marker>\n'
        "</defs>\n"
        f'<rect width="100%" height="100%" rx="12" fill="{BACKGROUND}"/>\n' + "\n".join(body) + "\n</svg>\n"
    )


def render_svg(geometry: DiagramGeometry, drawio_xml: str | None = None) -> str:
    body: list[str] = []
    if geometry.title:
        t = geometry.title
        body.append(
            f'<text x="{_num(t.rect.x)}" y="{_num(t.rect.y + TITLE_FONT)}" font-size="{TITLE_FONT}" font-weight="700" '
            f'fill="#F1F5F9">{_t(t.text)}</text>'
        )
    body += [_group(g) for g in geometry.groups]
    # Edges under nodes, labels above edges (each edge draws its own label last).
    body += [_edge(e) for e in geometry.edges if not e.lines]
    body += [_edge(e) for e in geometry.edges if e.lines]
    body += [_node(n) for n in geometry.nodes.values()]
    return _document(geometry.width, geometry.height, body, drawio_xml)


def render_sequence_svg(geometry: SequenceGeometry, drawio_xml: str | None = None) -> str:
    body: list[str] = []
    if geometry.title:
        t = geometry.title
        body.append(
            f'<text x="{_num(t.rect.x)}" y="{_num(t.rect.y + TITLE_FONT)}" font-size="{TITLE_FONT}" font-weight="700" '
            f'fill="#F1F5F9">{_t(t.text)}</text>'
        )
    for p in geometry.participants:
        body.append(
            f'<line x1="{_num(p.lifeline_x)}" y1="{_num(geometry.lifeline_top)}" x2="{_num(p.lifeline_x)}" '
            f'y2="{_num(geometry.lifeline_bottom)}" stroke="#475569" stroke-width="1.2" stroke-dasharray="4 4"/>'
        )
    for p in geometry.participants:
        h = p.head
        stroke = "#FB7185" if p.actor else "#38BDF8"
        body.append(
            f'<rect x="{_num(h.x)}" y="{_num(h.y)}" width="{_num(h.w)}" height="{_num(h.h)}" rx="8" '
            f'fill="#1E293B" stroke="{stroke}" stroke-width="1.6"/>'
        )
        top = h.cy - len(p.lines) * LINE_HEIGHT / 2 - 2
        body.append(_text_lines(p.lines, p.lifeline_x, top, NODE_FONT, LINE_HEIGHT, TEXT, 600))
    for m in geometry.messages:
        dash = ' stroke-dasharray="6 4"' if m.dashed else ""
        body.append(
            f'<path d="{_rounded_path(m.points, 4)}" fill="none" stroke="{EDGE if m.dashed else "#38BDF8"}" '
            f'stroke-width="1.6"{dash} marker-end="url(#arrow)"/>'
        )
        if m.lines:
            body.append(_text_lines(m.lines, m.label.cx, m.label.y - 2, EDGE_FONT, EDGE_LINE_HEIGHT, "#CBD5E1"))
    for n in geometry.notes:
        r = n.rect
        body.append(
            f'<rect x="{_num(r.x)}" y="{_num(r.y)}" width="{_num(r.w)}" height="{_num(r.h)}" rx="4" '
            f'fill="#FEF08A" stroke="#CA8A04" stroke-width="1"/>'
        )
        body.append(_text_lines(n.lines, r.cx, r.y + 4, NODE_FONT, LINE_HEIGHT, "#713F12"))
    return _document(geometry.width, geometry.height, body, drawio_xml)
