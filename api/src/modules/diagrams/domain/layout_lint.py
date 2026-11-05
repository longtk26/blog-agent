"""Deterministic layout lint (E10-S5/S6): the review checklist's geometric checks, run on the computed geometry.

Pure Python, no rendering. It complements the vision review (E10-S7): findings are precise ("edge e3 runs along the
border of group vpc") and cheap, so they are asserted in tests and also fed back to the model with the vision issues.

Checks (numbers follow the review checklist):
  1 text_overlap         an edge label or icon label overlaps another label, a node, or an edge it doesn't belong to
  2 edge_through_node    an edge passes through a node it doesn't connect to
  3 edge_on_border       an edge segment runs along a group border (parallel, within BORDER_CLEARANCE)
  3 shared_segment       two edges share a line (parallel, closer than 3 px, overlapping)
  5 label_exit_side      an edge leaves/enters an icon on the side its label sits on
"""

from dataclasses import dataclass, field

from src.modules.diagrams.domain.geometry import DiagramGeometry, EdgeGeom, Point, Rect

BORDER_CLEARANCE = 8.0   # px: closest a parallel edge segment may run to a group border
SHARED_LINE = 3.0        # px: parallel segments of two edges closer than this look like one line
MIN_OVERLAP = 6.0        # px: ignore touching segment ends


@dataclass
class LintFinding:
    check: str
    message: str
    elements: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"[{self.check}] {self.message}"


def _segments(points: list[Point]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:]))


def _seg_rect(a: Point, b: Point, pad: float = 0.0) -> Rect:
    return Rect(min(a[0], b[0]) - pad, min(a[1], b[1]) - pad, abs(b[0] - a[0]) + 2 * pad, abs(b[1] - a[1]) + 2 * pad)


def _overlap(lo1: float, hi1: float, lo2: float, hi2: float) -> float:
    return min(hi1, hi2) - max(lo1, lo2)


def _inner(rect: Rect, by: float = 1.0) -> Rect:
    return rect.inflate(-by)


def lint_geometry(g: DiagramGeometry) -> list[LintFinding]:
    findings: list[LintFinding] = []
    nodes = g.nodes

    # 2. edges through unrelated nodes (body or label)
    for e in g.edges:
        for key, n in nodes.items():
            if key in (e.source, e.target):
                continue
            for a, b in _segments(e.points):
                seg = _seg_rect(a, b)
                if seg.intersects(_inner(n.body)) or (n.label and seg.intersects(_inner(n.label))):
                    findings.append(LintFinding("edge_through_node", f"edge {e.id} passes through node {key}", [e.id, key]))
                    break

    # 1. text overlaps
    labels: list[tuple[str, Rect, EdgeGeom | None]] = [(f"label of {e.id}", e.label, e) for e in g.edges if e.label]
    labels += [(f"label of node {k}", n.label, None) for k, n in nodes.items() if n.label]
    for i, (name_a, ra, ea) in enumerate(labels):
        for name_b, rb, _eb in labels[i + 1:]:
            if _inner(ra).intersects(_inner(rb)):
                findings.append(LintFinding("text_overlap", f"{name_a} overlaps {name_b}", [name_a, name_b]))
        if ea is not None:
            for key, n in nodes.items():
                if _inner(ra).intersects(n.body):
                    findings.append(LintFinding("text_overlap", f"{name_a} overlaps node {key}", [ea.id, key]))
            for other in g.edges:
                if other is ea:
                    continue
                if any(_seg_rect(a, b).intersects(_inner(ra, 2)) for a, b in _segments(other.points)):
                    findings.append(LintFinding("text_overlap", f"{name_a} sits on edge {other.id}", [ea.id, other.id]))
    for gr in g.groups:
        band = gr.title_band
        for e in g.edges:
            if e.label and _inner(e.label).intersects(band):
                findings.append(LintFinding("text_overlap", f"label of {e.id} covers the title of group {gr.id}", [e.id, gr.id]))

    # 3a. edges running along group borders
    for e in g.edges:
        for a, b in _segments(e.points):
            horizontal = abs(a[1] - b[1]) < 0.01
            length = abs(b[0] - a[0]) + abs(b[1] - a[1])
            if length < MIN_OVERLAP:
                continue
            for gr in g.groups:
                r = gr.rect
                if horizontal:
                    lines = [(r.y, r.x, r.x2), (r.y2, r.x, r.x2)]
                    pos, lo, hi = a[1], min(a[0], b[0]), max(a[0], b[0])
                else:
                    lines = [(r.x, r.y, r.y2), (r.x2, r.y, r.y2)]
                    pos, lo, hi = a[0], min(a[1], b[1]), max(a[1], b[1])
                for line, llo, lhi in lines:
                    if abs(pos - line) < BORDER_CLEARANCE and _overlap(lo, hi, llo, lhi) >= MIN_OVERLAP:
                        findings.append(
                            LintFinding("edge_on_border", f"edge {e.id} runs along the border of group {gr.id}", [e.id, gr.id])
                        )
                        break
                else:
                    continue
                break

    # 3b. two edges sharing a line
    for i, e1 in enumerate(g.edges):
        for e2 in g.edges[i + 1:]:
            hit = False
            for a1, b1 in _segments(e1.points):
                h1 = abs(a1[1] - b1[1]) < 0.01
                for a2, b2 in _segments(e2.points):
                    h2 = abs(a2[1] - b2[1]) < 0.01
                    if h1 != h2:
                        continue
                    if h1:
                        close = abs(a1[1] - a2[1]) < SHARED_LINE
                        ov = _overlap(min(a1[0], b1[0]), max(a1[0], b1[0]), min(a2[0], b2[0]), max(a2[0], b2[0]))
                    else:
                        close = abs(a1[0] - a2[0]) < SHARED_LINE
                        ov = _overlap(min(a1[1], b1[1]), max(a1[1], b1[1]), min(a2[1], b2[1]), max(a2[1], b2[1]))
                    if close and ov >= MIN_OVERLAP:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                findings.append(LintFinding("shared_segment", f"edges {e1.id} and {e2.id} share a line", [e1.id, e2.id]))

    # 5. edges leaving an icon on its label side
    for e in g.edges:
        for key, point in ((e.source, e.points[0]), (e.target, e.points[-1])):
            n = nodes[key]
            if n.icon is None or not n.label:
                continue
            b = n.body
            side = (
                "bottom" if abs(point[1] - b.y2) < 0.6 else
                "top" if abs(point[1] - b.y) < 0.6 else
                "right" if abs(point[0] - b.x2) < 0.6 else None
            )
            if side and side == n.label_side:
                findings.append(
                    LintFinding("label_exit_side", f"edge {e.id} attaches to {key} on the {side}, where its label is", [e.id, key])
                )
    return findings
