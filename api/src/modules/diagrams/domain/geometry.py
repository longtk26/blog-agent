"""Diagram geometry: nested layered layout, orthogonal edge routing and label placement (E7-S2).

One geometry feeds both outputs — the editable draw.io file and the published SVG — so they always match.
Pure Python and deterministic: the same spec always produces the same coordinates.

Guarantees the renderers rely on:
- Nodes, group frames and their titles never overlap (groups are laid out bottom-up as solid blocks).
- Edges are orthogonal, never cross a node or a node label, and start/end on the icon or box itself.
- Every edge label sits on its own edge in free space (when the layout has room, which rank gaps reserve).
"""

import heapq
import math
from dataclasses import dataclass, field

from src.configs.logger import get_logger
from src.modules.diagrams.domain.icons import IconSpec, dominant_family, lookup, resolve_icon
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramEdge, DiagramSpec

logger = get_logger(__name__)

ICON_SIZE = 48
NODE_FONT = 12
EDGE_FONT = 11
TITLE_FONT = 16
LINE_HEIGHT = 15
EDGE_LINE_HEIGHT = 14
LABEL_GAP = 6            # icon to its label
GROUP_PAD = 24           # inside group frames
GROUP_TITLE = 34         # title band at the top of a group
NODE_GAP = 40            # between neighbours in a rank
RANK_GAP_LR = 72         # between ranks (grown to fit edge labels)
RANK_GAP_TB = 64
NODE_CLEARANCE = 18      # how close an edge may run to a node
STUB = 20                # straight segment out of a port
MARGIN = 24
BEND_COST = 28
OVERLAP_COST = 6.0       # per pixel of running on another edge's line
CROSS_COST = 14
GROUP_CROSS_COST = 36
SEPARATION = 10          # minimum distance between parallel lines of different edges
ROW_GROUP_WORDS = ("region", "project")   # frames whose own services go in a bottom row (E10-S6)
ROW_GAP = 76             # between a frame's content and its services row (room for stubs + a label)
BORDER_CLEARANCE = 8     # closest an edge may run parallel to a group border (E10-S6)
BORDER_COST = 12.0       # per pixel of running parallel to a group border within BORDER_CLEARANCE


# --- text -------------------------------------------------------------------------------------

_NARROW = set("iljtf.,:;'|!()[] ")
_WIDE = set("mwMW@%")


def text_width(text: str, size: float = NODE_FONT) -> float:
    """Approximate rendered width for a sans-serif font (good enough to reserve space)."""
    width = 0.0
    for char in text:
        if char in _NARROW:
            width += 0.30
        elif char in _WIDE:
            width += 0.85
        elif char.isupper() or char.isdigit():
            width += 0.64
        else:
            width += 0.54
    return width * size


def wrap(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").replace("\\n", "\n").split("\n"):
        words, line = paragraph.split(), ""
        for word in words:
            if line and len(line) + 1 + len(word) > max_chars:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            lines.append(line)
    return lines or [""]


# --- primitives -------------------------------------------------------------------------------

@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def inflate(self, margin: float) -> "Rect":
        return Rect(self.x - margin, self.y - margin, self.w + 2 * margin, self.h + 2 * margin)

    def moved(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def intersects(self, other: "Rect") -> bool:
        return self.x < other.x2 and other.x < self.x2 and self.y < other.y2 and other.y < self.y2

    def contains(self, x: float, y: float) -> bool:
        return self.x < x < self.x2 and self.y < y < self.y2

    def union(self, other: "Rect") -> "Rect":
        x, y = min(self.x, other.x), min(self.y, other.y)
        return Rect(x, y, max(self.x2, other.x2) - x, max(self.y2, other.y2) - y)


Point = tuple[float, float]


@dataclass
class NodeGeom:
    id: str
    kind: str
    lines: list[str]
    icon: IconSpec | None
    body: Rect                      # icon tile, or the box holding the text
    label: Rect | None = None       # text below/right of an icon
    label_side: str | None = None   # "bottom" | "right" | "top"
    group: str | None = None
    row: bool = False               # sits in a regional services row at the bottom of its group (E10-S6)

    @property
    def footprint(self) -> Rect:
        return self.body.union(self.label) if self.label else self.body

    def move(self, dx: float, dy: float) -> None:
        self.body = self.body.moved(dx, dy)
        if self.label:
            self.label = self.label.moved(dx, dy)


@dataclass
class GroupGeom:
    id: str
    title: str
    parent: str | None
    rect: Rect
    depth: int = 0

    @property
    def title_band(self) -> Rect:
        return Rect(self.rect.x, self.rect.y, self.rect.w, GROUP_TITLE)


@dataclass
class EdgeGeom:
    id: str
    source: str
    target: str
    points: list[Point]                 # port .. waypoints .. port, orthogonal
    lines: list[str] = field(default_factory=list)
    label: Rect | None = None
    label_at: float = 0.5               # label centre as a fraction of the path length
    dashed: bool = False
    arrow: str = "one"


@dataclass
class TitleGeom:
    text: str
    rect: Rect


@dataclass
class LegendItem:
    dashed: bool
    text: str
    line: tuple[Point, Point]
    text_rect: Rect


@dataclass
class LegendGeom:
    rect: Rect
    items: list[LegendItem]


LEGEND_TEXT = {False: "data path", True: "control / automation"}


@dataclass
class DiagramGeometry:
    direction: str
    width: float
    height: float
    title: TitleGeom | None
    nodes: dict[str, NodeGeom]
    groups: list[GroupGeom]            # parents before children
    edges: list[EdgeGeom]
    family: str = "aws"                # dominant cloud of the icons: picks AWS or GCP container styles
    legend: LegendGeom | None = None   # solid vs dashed key, when a diagram uses both (E10-S6)


# --- node sizes -------------------------------------------------------------------------------

def _make_node(node, diagram_type: str, lr: bool, family: str | None = None, side_label: bool = False) -> NodeGeom:
    if node.icon and lookup(node.icon) is None:
        logger.warning(f"Unknown icon key {node.icon!r} on node {node.id!r}; drawing it as a {node.kind} shape")
    icon, text = resolve_icon(node.icon, node.label, node.kind, diagram_type, family)
    if icon is not None:
        lines = wrap(text, 18)
        lw = max(text_width(line) for line in lines) + 4
        lh = len(lines) * LINE_HEIGHT
        body = Rect(0, 0, ICON_SIZE, ICON_SIZE)
        if lr and not side_label:
            # Label below; centred under the tile.
            width = max(ICON_SIZE, lw)
            body = Rect((width - ICON_SIZE) / 2, 0, ICON_SIZE, ICON_SIZE)
            label = Rect((width - lw) / 2, ICON_SIZE + LABEL_GAP, lw, lh)
            side = "bottom"
        elif lr:
            # Left-to-right flow uses the left/right sides and a services row uses the bottom: label goes on top.
            width = max(ICON_SIZE, lw)
            label = Rect((width - lw) / 2, 0, lw, lh)
            body = Rect((width - ICON_SIZE) / 2, lh + LABEL_GAP, ICON_SIZE, ICON_SIZE)
            side = "top"
        else:
            # Edges attach above/below the tile (top-to-bottom flow, or links to a services row): label on the right,
            # because a label under the icon always collides with an edge leaving from the bottom (note §2.5).
            height = max(ICON_SIZE, lh)
            body = Rect(0, (height - ICON_SIZE) / 2, ICON_SIZE, ICON_SIZE)
            label = Rect(ICON_SIZE + LABEL_GAP + 2, (height - lh) / 2, lw, lh)
            side = "right"
        return NodeGeom(node.id, node.kind, lines, icon, body, label, side, node.group)

    lines = wrap(text, {"note": 30, "decision": 18}.get(node.kind, 24))
    tw = max(text_width(line) for line in lines)
    th = len(lines) * LINE_HEIGHT
    if node.kind == "decision":
        w, h = max(140, tw * 1.75 + 40), max(76, th * 2 + 30)
    elif node.kind == "datastore":
        w, h = max(110, tw + 36), max(64, th + 40)
    else:
        w, h = max(120, tw + 32), max(48, th + 24)
    return NodeGeom(node.id, node.kind, lines, None, Rect(0, 0, round(w), round(h)), None, None, node.group)


# --- nested layered layout --------------------------------------------------------------------

@dataclass
class _Item:
    key: str            # node id or "g:<group id>"
    w: float
    h: float
    anchor: float       # port line, measured from the item's top/left on the cross axis


def _isotonic(targets: list[float]) -> list[float]:
    """Pool-adjacent-violators: closest non-decreasing sequence (least squares)."""
    blocks: list[list[float]] = []      # [mean, weight]
    for t in targets:
        blocks.append([t, 1.0])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            m2, w2 = blocks.pop()
            m1, w1 = blocks.pop()
            blocks.append([(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2])
    out: list[float] = []
    for mean, weight in blocks:
        out.extend([mean] * int(weight))
    return out


class _Layout:
    def __init__(self, spec: DiagramSpec):
        self.spec = spec
        self.lr = spec.direction != "TB"
        self.family = dominant_family([n.icon for n in spec.nodes])
        self.group_ids = [g.id for g in spec.groups]
        self.group_parent = {g.id: (g.parent if g.parent in self.group_ids and g.parent != g.id else None) for g in spec.groups}
        self.node_group = {n.id: (n.group if n.group in self.group_ids else None) for n in spec.nodes}
        self.group_rects: dict[str, Rect] = {}
        self._measured: dict[str | None, tuple[dict[str, tuple[float, float]], float, float]] = {}

        # Regional services row (E10-S6): in a region/project frame that also holds nested frames (a VPC), the nodes
        # sitting directly in it (S3, ECR, Route 53, Cloud Storage, ...) go in a row along its bottom edge instead of a
        # side column, so their edges stay short and vertical.
        labels = {g.id: g.label.lower() for g in spec.groups}
        self.row_groups = {
            gid for gid in self.group_ids
            if any(word in labels[gid] for word in ROW_GROUP_WORDS)
            and any(self.group_parent[c] == gid for c in self.group_ids)
            and any(self.node_group[n.id] == gid for n in spec.nodes)
        }
        # Only services *used by* the nested frames qualify (every neighbour sits inside one of the frame's child
        # groups): S3/ECR/Parameter Store next to a VPC do; a load balancer or Cloud Run API on the main flow don't.
        self.row_nodes = set()
        for n in spec.nodes:
            gid = self.node_group[n.id]
            if gid not in self.row_groups:
                continue
            neighbours = [e.to_node if e.from_node == n.id else e.from_node
                          for e in spec.edges if n.id in (e.from_node, e.to_node)]
            if neighbours and all(self._inside_child_group(other, gid) for other in neighbours):
                self.row_nodes.add(n.id)
        self.row_groups = {gid for gid in self.row_groups if any(self.node_group[n] == gid for n in self.row_nodes)}
        linked = set()
        for e in spec.edges:
            if (e.from_node in self.row_nodes) != (e.to_node in self.row_nodes):
                linked.add(e.to_node if e.from_node in self.row_nodes else e.from_node)
        self.nodes = {
            n.id: _make_node(n, spec.type, self.lr, self.family, side_label=n.id in linked) for n in spec.nodes
        }
        for node_id in self.row_nodes:
            self.nodes[node_id].row = True

    def _inside_child_group(self, node_id: str, gid: str) -> bool:
        """True when node_id sits (at any depth) inside a group whose parent is gid."""
        cur = self.node_group.get(node_id)
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            if self.group_parent.get(cur) == gid:
                return True
            cur = self.group_parent.get(cur)
        return False

    # axis helpers: u = rank (main) axis, v = cross axis
    def _uv(self, w: float, h: float) -> tuple[float, float]:
        return (w, h) if self.lr else (h, w)

    def _chain(self, node_id: str) -> list[str | None]:
        """Groups containing a node, innermost first, ending with None (the root)."""
        chain: list[str | None] = []
        gid = self.node_group.get(node_id)
        seen = set()
        while gid is not None and gid not in seen:
            seen.add(gid)
            chain.append(gid)
            gid = self.group_parent.get(gid)
        chain.append(None)
        return chain

    def _child_of(self, container: str | None, node_id: str) -> str | None:
        chain = self._chain(node_id)
        if container not in chain:
            return None
        index = chain.index(container)
        return node_id if index == 0 else f"g:{chain[index - 1]}"

    def run(self) -> dict[str, tuple[float, float]]:
        """Absolute top-left of every node; group rectangles are filled into self.group_rects."""
        positions: dict[str, tuple[float, float]] = {}
        self._place(None, 0.0, 0.0, positions)
        return positions

    def _children(self, container: str | None) -> list[str]:
        keys = [f"g:{g}" for g in self.group_ids if self.group_parent[g] == container]
        keys += [n.id for n in self.spec.nodes if self.node_group[n.id] == container]
        return keys

    def _measure(self, container: str | None) -> tuple[dict[str, tuple[float, float]], float, float]:
        """Relative top-left of each child in a container, plus the content size (memoised: pure per container)."""
        if container not in self._measured:
            self._measured[container] = self._measure_uncached(container)
        return self._measured[container]

    def _offset_in(self, container: str | None, node_id: str) -> tuple[float, float] | None:
        """Centre of a node relative to a container's content origin (None when the node is not inside it)."""
        key = self._child_of(container, node_id)
        if key is None:
            return None
        rel, _, _ = self._measure(container)
        if key not in rel:
            return None
        x, y = rel[key]
        if key == node_id:
            fp = self.nodes[node_id].footprint
            body = self.nodes[node_id].body
            return x + (body.cx - fp.x), y + (body.cy - fp.y)
        inner = self._offset_in(key[2:], node_id)
        return None if inner is None else (x + GROUP_PAD + inner[0], y + GROUP_TITLE + inner[1])

    def _measure_uncached(self, container: str | None) -> tuple[dict[str, tuple[float, float]], float, float]:
        keys = self._children(container)
        if container in self.row_groups:
            return self._measure_with_row(container, keys)
        return self._measure_keys(container, keys)

    def _measure_with_row(self, container: str, keys: list[str]):
        row = [k for k in keys if k in self.row_nodes]
        main_keys = [k for k in keys if k not in self.row_nodes]
        rel, main_w, main_h = self._measure_keys(container, main_keys)
        # Order the row under the things it connects to (barycentre of neighbour x), spec order on ties.
        desired: dict[str, float] = {}
        for k in row:
            xs = []
            for e in self.spec.edges:
                other = e.to_node if e.from_node == k else e.from_node if e.to_node == k else None
                if other is None or other in row:
                    continue
                key = self._child_of(container, other)
                if key in rel:
                    if key == other:
                        fp = self.nodes[other].footprint
                        xs.append(rel[key][0] + (self.nodes[other].body.cx - fp.x))
                    else:
                        inner = self._offset_in(key[2:], other)
                        if inner is not None:
                            xs.append(rel[key][0] + GROUP_PAD + inner[0])
            desired[k] = sum(xs) / len(xs) if xs else main_w / 2
        row.sort(key=lambda k: (desired[k], keys.index(k)))
        widths = [self.nodes[k].footprint.w for k in row]
        offsets, cursor = [], 0.0
        for k, w in zip(row, widths):
            body = self.nodes[k].body
            fp = self.nodes[k].footprint
            offsets.append(cursor + (body.cx - fp.x))
            cursor += w + NODE_GAP
        fitted = _isotonic([desired[k] - offsets[i] for i, k in enumerate(row)])
        shift = min(0.0, min(fitted)) if fitted else 0.0
        row_y = main_h + ROW_GAP
        row_h = 0.0
        out = {k: (x - shift, y) for k, (x, y) in rel.items()} if shift < 0 else dict(rel)
        width = main_w - shift
        for i, k in enumerate(row):
            fp = self.nodes[k].footprint
            x = fitted[i] + offsets[i] - (self.nodes[k].body.cx - fp.x) - shift
            out[k] = (x, row_y)
            width = max(width, x + fp.w)
            row_h = max(row_h, fp.h)
        return out, width, row_y + row_h

    def _measure_keys(self, container: str | None, keys: list[str]):
        """Relative top-left of each child in a container, plus the content size."""
        items: dict[str, _Item] = {}
        for key in keys:
            if key.startswith("g:"):
                _, cw, ch = self._measure(key[2:])
                w, h = cw + 2 * GROUP_PAD, ch + GROUP_PAD + GROUP_TITLE
                items[key] = _Item(key, w, h, (h if self.lr else w) / 2)
            else:
                node = self.nodes[key]
                fp = node.footprint
                anchor = (node.body.cy - fp.y) if self.lr else (node.body.cx - fp.x)
                items[key] = _Item(key, fp.w, fp.h, anchor)

        edges: list[tuple[str, str, DiagramEdge]] = []
        for edge in self.spec.edges:
            a, b = self._child_of(container, edge.from_node), self._child_of(container, edge.to_node)
            if a and b and a != b and a in items and b in items:
                edges.append((a, b, edge))
        if not items:
            return {}, 0.0, 0.0
        return self._layered(keys, items, edges, container)

    def _external_side(self, key: str, edges) -> tuple[str, str] | None:
        """For a top-level external system linked to one frame only: ("before"|"after", frame key) by where its
        neighbours sit inside that frame, so DB/ACME end up next to the NAT gateway they talk to (note §2.5)."""
        node = next((n for n in self.spec.nodes if n.id == key), None)
        if node is None or node.kind != "external" or self.node_group.get(key) is not None:
            return None
        frames = {b if a == key else a for a, b, _ in edges if key in (a, b)}
        if len(frames) != 1:
            return None
        frame = next(iter(frames))
        if not frame.startswith("g:"):
            return None
        gid = frame[2:]
        positions = []
        for e in self.spec.edges:
            other = e.to_node if e.from_node == key else e.from_node if e.to_node == key else None
            if other is None:
                continue
            pos = self._offset_in(gid, other)
            if pos is not None:
                positions.append(pos[0] if self.lr else pos[1])
        if not positions:
            return None
        _, w, h = self._measure(gid)
        size = w if self.lr else h
        return ("before" if sum(positions) / len(positions) < size / 2 else "after"), frame

    def _layered(self, keys, items, edges, container=None):
        # 1. ranks: longest path over a DAG (back edges found by DFS in spec order are ignored)
        succ: dict[str, list[str]] = {k: [] for k in keys}
        pred: dict[str, list[str]] = {k: [] for k in keys}
        state: dict[str, int] = {}
        out_edges: dict[str, list[str]] = {k: [] for k in keys}
        for a, b, _ in edges:
            if b not in out_edges[a]:
                out_edges[a].append(b)

        def dfs(k: str) -> None:
            state[k] = 1
            for nxt in out_edges[k]:
                if state.get(nxt) == 1:
                    continue  # back edge
                if nxt not in succ[k]:
                    succ[k].append(nxt)
                    pred[nxt].append(k)
                if nxt not in state:
                    dfs(nxt)
            state[k] = 2

        # Walk from where the flow starts: items without incoming edges, then by first appearance as a source.
        first_source = {}
        for index, (a, _b, _e) in enumerate(edges):
            first_source.setdefault(a, index)
        has_incoming = {b for _a, b, _e in edges}
        for k in sorted(keys, key=lambda k: (k in has_incoming, first_source.get(k, len(edges)), keys.index(k))):
            if k not in state:
                dfs(k)

        rank: dict[str, int] = {}

        def longest(k: str) -> int:
            if k not in rank:
                rank[k] = 0
                rank[k] = max((longest(p) + 1 for p in pred[k]), default=0)
            return rank[k]

        for k in keys:
            longest(k)
        # Pull sources next to their first consumer instead of leaving them in column 0.
        for k in keys:
            if not pred[k] and succ[k]:
                rank[k] = max(rank[k], min(rank[s] for s in succ[k]) - 1)
        if container is None:
            for k in keys:
                side = self._external_side(k, edges)
                if side:
                    where, frame = side
                    rank[k] = rank[frame] - 1 if where == "before" else rank[frame] + 1
            low = min(rank.values())
            if low < 0:
                rank = {k: r - low for k, r in rank.items()}
        ranks: dict[int, list[str]] = {}
        for k in keys:
            ranks.setdefault(rank[k], []).append(k)
        order = [ranks[r] for r in sorted(ranks)]
        rank_of = {k: i for i, layer in enumerate(order) for k in layer}

        # 2. order within ranks: barycentre sweeps
        def position(layer):
            return {k: i for i, k in enumerate(layer)}

        for sweep in range(8):
            forward = sweep % 2 == 0
            indices = range(1, len(order)) if forward else range(len(order) - 2, -1, -1)
            for r in indices:
                ref = position(order[r - 1] if forward else order[r + 1])
                neighbours = pred if forward else succ
                current = position(order[r])

                def bary(k: str) -> float:
                    vals = [ref[n] for n in neighbours[k] if n in ref]
                    return sum(vals) / len(vals) if vals else current[k]

                order[r] = sorted(order[r], key=lambda k: (bary(k), current[k]))

        # 3. main-axis coordinates; gaps grow to fit the labels of edges leaving a rank
        gap_base = RANK_GAP_LR if self.lr else RANK_GAP_TB
        sizes_u = [max(self._uv(items[k].w, items[k].h)[0] for k in layer) for layer in order]
        gaps = [gap_base] * max(0, len(order) - 1)
        # Labels of edges leaving one item through the same gap are placed side by side, so reserve their sum.
        label_room: dict[tuple[int, str], float] = {}
        for a, b, edge in edges:
            if not edge.label:
                continue
            lines = wrap(edge.label, 22)
            lw = max(text_width(line, EDGE_FONT) for line in lines) + 12
            lh = len(lines) * EDGE_LINE_HEIGHT + 6
            lo, hi = sorted((rank_of[a], rank_of[b]))
            if hi > lo:
                key = (lo, a if rank_of[a] == lo else b)
                label_room[key] = label_room.get(key, 0.0) + (lw if self.lr else lh) + 10
        for (lo, _item), room in label_room.items():
            gaps[lo] = max(gaps[lo], room + 2 * (STUB + 12))
        u_start, cursor = [], 0.0
        for r, size in enumerate(sizes_u):
            u_start.append(cursor)
            cursor += size + (gaps[r] if r < len(gaps) else 0)
        total_u = cursor

        # 4. cross-axis coordinates: align each item's port line with its neighbours (isotonic regression)
        anchor_v: dict[str, float] = {}
        for layer in order:
            cursor = 0.0
            for k in layer:
                v_size = self._uv(items[k].w, items[k].h)[1]
                anchor_v[k] = cursor + items[k].anchor
                cursor += v_size + NODE_GAP

        def place(layer: list[str], desired: dict[str, float]) -> None:
            offsets, cursor = [], 0.0
            for k in layer:
                v_size = self._uv(items[k].w, items[k].h)[1]
                offsets.append(cursor + items[k].anchor)
                cursor += v_size + NODE_GAP
            targets = [desired[k] - offsets[i] for i, k in enumerate(layer)]
            fitted = _isotonic(targets)
            for i, k in enumerate(layer):
                anchor_v[k] = fitted[i] + offsets[i]

        def median(values: list[float]) -> float:
            values = sorted(values)
            mid = len(values) // 2
            return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2

        for _ in range(6):
            for direction in (1, -1):
                layers = range(len(order)) if direction == 1 else range(len(order) - 1, -1, -1)
                for r in layers:
                    neighbours = pred if direction == 1 else succ
                    desired = {}
                    for k in order[r]:
                        vals = [anchor_v[n] for n in neighbours[k] if n in anchor_v and rank_of[n] != r]
                        desired[k] = median(vals) if vals else anchor_v[k]
                    place(order[r], desired)

        top = min(anchor_v[k] - items[k].anchor for k in keys)
        positions: dict[str, tuple[float, float]] = {}
        total_v = 0.0
        for layer_index, layer in enumerate(order):
            for k in layer:
                iu, iv = self._uv(items[k].w, items[k].h)
                u = u_start[layer_index] + (sizes_u[layer_index] - iu) / 2
                v = anchor_v[k] - items[k].anchor - top
                total_v = max(total_v, v + iv)
                positions[k] = (u, v) if self.lr else (v, u)
        width, height = (total_u, total_v) if self.lr else (total_v, total_u)
        return positions, width, height

    def _place(self, container: str | None, ox: float, oy: float, out: dict[str, tuple[float, float]]) -> tuple[float, float]:
        rel, width, height = self._measure(container)
        for key, (x, y) in rel.items():
            ax, ay = ox + x, oy + y
            if key.startswith("g:"):
                gid = key[2:]
                cw, ch = self._place(gid, ax + GROUP_PAD, ay + GROUP_TITLE, out)
                self.group_rects[gid] = Rect(ax, ay, cw + 2 * GROUP_PAD, ch + GROUP_PAD + GROUP_TITLE)
            else:
                out[key] = (ax, ay)
        return width, height


# --- orthogonal routing -----------------------------------------------------------------------

_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


class _Router:
    def __init__(self, nodes: dict[str, NodeGeom], groups: list[GroupGeom], bounds: Rect):
        self.nodes = nodes
        self.groups = groups
        self.hard = [n.body.inflate(NODE_CLEARANCE) for n in nodes.values()]
        self.hard += [n.label.inflate(4) for n in nodes.values() if n.label]
        self.soft = [g.title_band for g in groups]
        self.bounds = bounds
        self.used_h: dict[tuple[float, float, float], int] = {}   # (y, x1, x2) segments in use
        self.used_v: dict[tuple[float, float, float], int] = {}
        self.used_points: set[Point] = set()
        self.extra_x: set[float] = set()
        self.extra_y: set[float] = set()
        self.penalty: list[tuple[bool, float, float, float]] = []   # (horizontal, line, lo, hi) to keep well away from

    def add_coordinates(self, points: list[Point]) -> None:
        for x, y in points:
            self.extra_x.add(round(x, 1))
            self.extra_y.add(round(y, 1))

    def build(self) -> None:
        xs = {self.bounds.x, self.bounds.x2, *self.extra_x}
        ys = {self.bounds.y, self.bounds.y2, *self.extra_y}
        for r in self.hard:
            xs.update((r.x, r.x2))
            ys.update((r.y, r.y2))
        for g in self.groups:
            xs.update((g.rect.x - 10, g.rect.x + 10, g.rect.x2 - 10, g.rect.x2 + 10))
            ys.update((g.rect.y - 10, g.rect.y + GROUP_TITLE + 8, g.rect.y2 - 10, g.rect.y2 + 10))
        # Group borders: vertical lines at x (spanning y1..y2) and horizontal lines at y (spanning x1..x2).
        self.border_v = [(x, g.rect.y, g.rect.y2) for g in self.groups for x in (g.rect.x, g.rect.x2)]
        self.border_h = [(y, g.rect.x, g.rect.x2) for g in self.groups for y in (g.rect.y, g.rect.y2)]
        keep_x = {round(v, 1) for v in (self.bounds.x, self.bounds.x2, *self.extra_x)}
        keep_y = {round(v, 1) for v in (self.bounds.y, self.bounds.y2, *self.extra_y)}
        self.xs = self._off_borders(self._with_channels(sorted(round(x, 1) for x in xs)), [b[0] for b in self.border_v], keep_x)
        self.ys = self._off_borders(self._with_channels(sorted(round(y, 1) for y in ys)), [b[0] for b in self.border_h], keep_y)
        self.ix = {x: i for i, x in enumerate(self.xs)}
        self.iy = {y: i for i, y in enumerate(self.ys)}
        # rows/columns closer than SEPARATION count as "the same line" for overlap costs
        self.near_y = [[k for k, other in enumerate(self.ys) if abs(other - y) < SEPARATION] for y in self.ys]
        self.near_x = [[k for k, other in enumerate(self.xs) if abs(other - x) < SEPARATION] for x in self.xs]
        # blocked intervals per row/column
        self.row_block = [[(r.x, r.x2) for r in self.hard if r.y < y < r.y2] for y in self.ys]
        self.col_block = [[(r.y, r.y2) for r in self.hard if r.x < x < r.x2] for x in self.xs]

    @staticmethod
    def _off_borders(values: list[float], borders: list[float], keep: set[float]) -> list[float]:
        """Drop routing lines that would run on (or hug) a group border; port stubs and bounds are kept."""
        return [v for v in values if v in keep or all(abs(v - b) >= BORDER_CLEARANCE for b in borders)]

    @staticmethod
    def _with_channels(values: list[float]) -> list[float]:
        out = set(values)
        for a, b in zip(values, values[1:]):
            gap = b - a
            if gap > 16:
                out.add(round((a + b) / 2, 1))
            if gap > 90:
                out.add(round(a + gap / 4, 1))
                out.add(round(b - gap / 4, 1))
        return sorted(out)

    def _free(self, i: int, j: int) -> bool:
        x, y = self.xs[i], self.ys[j]
        return not any(a < x < b for a, b in self.row_block[j])

    def _segment_free(self, i: int, j: int, di: int, dj: int) -> bool:
        if di:
            mid = (self.xs[i] + self.xs[i + di]) / 2
            return not any(a < mid < b for a, b in self.row_block[j])
        mid = (self.ys[j] + self.ys[j + dj]) / 2
        return not any(a < mid < b for a, b in self.col_block[i])

    def _step_cost(self, i: int, j: int, di: int, dj: int) -> float:
        x1, y1 = self.xs[i], self.ys[j]
        x2, y2 = self.xs[i + di], self.ys[j + dj]
        length = abs(x2 - x1) + abs(y2 - y1)
        cost = length
        if di:
            lo, hi = min(x1, x2), max(x1, x2)
            used = sum(self.used_h.get((self.ys[k], lo, hi), 0) for k in self.near_y[j])
        else:
            lo, hi = min(y1, y2), max(y1, y2)
            used = sum(self.used_v.get((self.xs[k], lo, hi), 0) for k in self.near_x[i])
        cost += used * OVERLAP_COST * length
        if (x2, y2) in self.used_points:
            cost += CROSS_COST
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        for band in self.soft:
            if band.contains(mx, my):
                cost += 4 * length
        for g in self.groups:
            if g.rect.contains(x1, y1) != g.rect.contains(x2, y2):
                cost += GROUP_CROSS_COST
        for horizontal, line, lo, hi in self.penalty:
            if horizontal == bool(di):
                pos, a, b = (y1, min(x1, x2), max(x1, x2)) if di else (x1, min(y1, y2), max(y1, y2))
                if abs(pos - line) < SEPARATION and min(hi, b) - max(lo, a) > 0:
                    cost += 60 * length
        # Running parallel to a group border reads as part of the frame (note §2.4): push such segments away.
        if di:
            for line, lo, hi in self.border_h:
                if abs(y1 - line) < BORDER_CLEARANCE and min(hi, max(x1, x2)) - max(lo, min(x1, x2)) > 0:
                    cost += BORDER_COST * length
        else:
            for line, lo, hi in self.border_v:
                if abs(x1 - line) < BORDER_CLEARANCE and min(hi, max(y1, y2)) - max(lo, min(y1, y2)) > 0:
                    cost += BORDER_COST * length
        return cost

    def route(self, start: Point, start_dir: int, goal: Point, goal_dir: int) -> list[Point] | None:
        """A* over the grid from `start` (leaving in start_dir) to `goal` (arriving in goal_dir)."""
        si, sj = self.ix[round(start[0], 1)], self.iy[round(start[1], 1)]
        gi, gj = self.ix[round(goal[0], 1)], self.iy[round(goal[1], 1)]
        gx, gy = self.xs[gi], self.ys[gj]

        def h(i: int, j: int) -> float:
            return abs(self.xs[i] - gx) + abs(self.ys[j] - gy)

        start_state = (si, sj, start_dir)
        best = {start_state: 0.0}
        came: dict[tuple[int, int, int], tuple[int, int, int]] = {}
        heap = [(h(si, sj), 0.0, start_state)]
        while heap:
            _, cost, state = heapq.heappop(heap)
            i, j, d = state
            if cost > best.get(state, math.inf):
                continue
            if (i, j) == (gi, gj):
                if d != goal_dir:
                    continue  # must arrive head-on into the target port
                path = [state]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return [(self.xs[s[0]], self.ys[s[1]]) for s in reversed(path)]
            for nd, (di, dj) in enumerate(_DIRS):
                if d >= 0 and (di, dj) == (-_DIRS[d][0], -_DIRS[d][1]):
                    continue  # no U-turns in place
                ni, nj = i + di, j + dj
                if not (0 <= ni < len(self.xs) and 0 <= nj < len(self.ys)):
                    continue
                if not self._free(ni, nj) and (ni, nj) != (gi, gj):
                    continue
                if not self._segment_free(i, j, di, dj):
                    continue
                step = self._step_cost(i, j, di, dj) + (BEND_COST if d >= 0 and nd != d else 0)
                new_state = (ni, nj, nd)
                new_cost = cost + step
                if new_cost < best.get(new_state, math.inf):
                    best[new_state] = new_cost
                    came[new_state] = state
                    heapq.heappush(heap, (new_cost + h(ni, nj), new_cost, new_state))
        return None

    def commit(self, points: list[Point]) -> None:
        """Register a routed path so later edges avoid running on top of it."""
        grid_x, grid_y = self.xs, self.ys
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if y1 == y2:
                lo, hi = sorted((x1, x2))
                xs = [x for x in grid_x if lo <= x <= hi]
                for a, b in zip(xs, xs[1:]):
                    self.used_h[(y1, a, b)] = self.used_h.get((y1, a, b), 0) + 1
                    self.used_points.add((b, y1))
            else:
                lo, hi = sorted((y1, y2))
                ys = [y for y in grid_y if lo <= y <= hi]
                for a, b in zip(ys, ys[1:]):
                    self.used_v[(x1, a, b)] = self.used_v.get((x1, a, b), 0) + 1
                    self.used_points.add((x1, b))


def _simplify(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for p in points:
        if out and abs(p[0] - out[-1][0]) < 0.01 and abs(p[1] - out[-1][1]) < 0.01:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (abs(ax - bx) < 0.01 and abs(bx - p[0]) < 0.01) or (abs(ay - by) < 0.01 and abs(by - p[1]) < 0.01):
                out[-1] = p
                continue
        out.append(p)
    return out


# --- ports ------------------------------------------------------------------------------------

_SIDE_DIR = {"right": 0, "left": 1, "bottom": 2, "top": 3}
_SIDE_OUT = {"right": (1, 0), "left": (-1, 0), "bottom": (0, 1), "top": (0, -1)}


def _sides(src: NodeGeom, tgt: NodeGeom, lr: bool) -> tuple[str, str]:
    a, b = src.body, tgt.body
    # Services rows are reached vertically: down into the row, up out of it.
    if tgt.row and not src.row and b.y >= a.y2 + 1 and src.label_side != "bottom":
        return "bottom", "top"
    if src.row and not tgt.row and b.y2 <= a.y - 1 and tgt.label_side != "bottom":
        return "top", "bottom"
    if lr:
        if b.x >= a.x2 + 1:
            return "right", "left"
        if b.x2 <= a.x - 1:
            return "left", "right"
        # same column: never attach on the side an icon's label sits on
        down = b.cy > a.cy
        exit_side, entry_side = ("bottom", "top") if down else ("top", "bottom")
        if src.label_side == exit_side or tgt.label_side == entry_side:
            return ("right", "right")
        return exit_side, entry_side
    if b.y >= a.y2 + 1:
        return "bottom", "top"
    if b.y2 <= a.y - 1:
        return "top", "bottom"
    if src.label_side == "right" or tgt.label_side == "right":
        return ("left", "left")
    return ("right", "left") if b.cx > a.cx else ("left", "right")


def _port_points(node: NodeGeom, side: str, offset: float) -> tuple[Point, Point]:
    r = node.body
    if side in ("left", "right"):
        x = r.x2 if side == "right" else r.x
        y = r.cy + offset
    else:
        y = r.y2 if side == "bottom" else r.y
        x = r.cx + offset
    dx, dy = _SIDE_OUT[side]
    port = (round(x, 1), round(y, 1))
    return port, (round(x + dx * STUB, 1), round(y + dy * STUB, 1))


def _spread(count: int, length: float, is_icon: bool) -> list[float]:
    span = 24 if is_icon else length * 0.7
    if count == 1:
        return [0.0]
    step = min(14.0 if is_icon else 28.0, span / (count - 1))
    return [(i - (count - 1) / 2) * step for i in range(count)]


# --- labels -----------------------------------------------------------------------------------

def _path_length(points: list[Point]) -> float:
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in zip(points, points[1:]))


def _place_label(
    edge: EdgeGeom, size: tuple[float, float], blockers: list[Rect], others: list[EdgeGeom], lr: bool, near_source: bool
) -> None:
    w, h = size
    pts = edge.points
    total = _path_length(pts)
    best: tuple[float, Rect, float] | None = None
    walked = 0.0
    for index, (a, b) in enumerate(zip(pts, pts[1:])):
        seg = abs(b[0] - a[0]) + abs(b[1] - a[1])
        horizontal = abs(a[1] - b[1]) < 0.01
        need = (w if horizontal else h) + 12
        last = index == len(pts) - 2
        usable = seg - (14 if last else 0)  # keep clear of the arrowhead
        if usable >= need:
            for frac in (0.5, 0.35, 0.65, 0.2, 0.8):
                center = need / 2 + (usable - need) * frac
                cx = a[0] + (b[0] - a[0]) * center / seg
                cy = a[1] + (b[1] - a[1]) * center / seg
                rect = Rect(cx - w / 2, cy - h / 2, w, h)
                if any(rect.intersects(r) for r in blockers):
                    continue
                # Branch labels ("Yes"/"No") belong next to the decision; others mid-way along the edge.
                score = abs((walked + center) / total - (0.12 if near_source else 0.5)) * 40 if total else 0
                score += 0 if horizontal == lr else 25
                score += 400 * sum(_crosses(rect, o.points) for o in others if o is not edge)
                if best is None or score < best[0]:
                    best = (score, rect, (walked + center) / total if total else 0.5)
        walked += seg
    if best is not None and best[0] >= 400:
        # Every spot on the line sits on another edge: a spot beside the line that is clear of all edges is better.
        side = _label_beside(edge, (w, h), blockers + _edge_rects(others, edge), total)
        if side[0] < 1.0 or not any(_crosses(side[1], o.points) for o in others if o is not edge):
            best = side
    if best is None:
        best = _label_beside(edge, (w, h), blockers + _edge_rects(others, edge), total)
    edge.label = best[1]
    edge.label_at = best[2]


def _label_beside(edge: EdgeGeom, size: tuple[float, float], blockers: list[Rect], total: float) -> tuple[float, Rect, float]:
    """No room on the line itself: put the label next to a segment, else at the nearest free spot."""
    w, h = size
    pts = edge.points
    walked, options = 0.0, []
    for a, b in zip(pts, pts[1:]):
        seg = abs(b[0] - a[0]) + abs(b[1] - a[1])
        horizontal = abs(a[1] - b[1]) < 0.01
        steps = max(1, int(seg // 12))
        for k in range(steps + 1):
            t = k / steps
            px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            sides = ((0, -(h / 2 + 3)), (0, h / 2 + 3)) if horizontal else ((w / 2 + 3, 0), (-(w / 2 + 3), 0))
            for dx, dy in sides:
                rect = Rect(px + dx - w / 2, py + dy - h / 2, w, h)
                if not any(rect.intersects(r) for r in blockers):
                    frac = (walked + seg * t) / total if total else 0.5
                    options.append((abs(frac - 0.5), rect, frac))
        walked += seg
    if options:
        return min(options, key=lambda o: o[0])
    # Spiral out from the middle of the path until a free spot is found.
    mid = len(pts) // 2
    cx, cy = (pts[mid - 1][0] + pts[mid][0]) / 2, (pts[mid - 1][1] + pts[mid][1]) / 2
    for radius in range(12, 600, 12):
        for k in range(16):
            angle = 2 * math.pi * k / 16
            rect = Rect(cx + radius * math.cos(angle) - w / 2, cy + radius * math.sin(angle) - h / 2, w, h)
            if not any(rect.intersects(r) for r in blockers):
                return (0.0, rect, 0.5)
    return (0.0, Rect(cx - w / 2, cy - h / 2, w, h), 0.5)


def _edge_rects(edges: list[EdgeGeom], skip: EdgeGeom) -> list[Rect]:
    """Thin rectangles along other edges, used as blockers when a label must leave its own line."""
    out = []
    for e in edges:
        if e is skip:
            continue
        for (x1, y1), (x2, y2) in zip(e.points, e.points[1:]):
            out.append(Rect(min(x1, x2) - 1.5, min(y1, y2) - 1.5, abs(x2 - x1) + 3, abs(y2 - y1) + 3))
    return out


def _crosses(rect: Rect, points: list[Point]) -> int:
    count = 0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        seg = Rect(min(x1, x2) - 0.5, min(y1, y2) - 0.5, abs(x2 - x1) + 1, abs(y2 - y1) + 1)
        if seg.intersects(rect):
            count += 1
    return count


def _nudge_overlaps(edges: list[EdgeGeom], hard: list[Rect]) -> None:
    """Spread apart parallel inner segments of different edges that overlap or run closer than SEPARATION.

    Only inner segments move (ports and their stubs stay fixed); a move is skipped if it would hit a node.
    """
    for horizontal in (True, False):
        segs: list[list] = []   # [line, lo, hi, edge, index]
        for edge in edges:
            pts = edge.points
            for i in range(1, len(pts) - 2):
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                if horizontal and abs(y1 - y2) < 0.01:
                    segs.append([y1, min(x1, x2), max(x1, x2), edge, i])
                elif not horizontal and abs(x1 - x2) < 0.01:
                    segs.append([x1, min(y1, y2), max(y1, y2), edge, i])
        segs.sort(key=lambda s: (s[0], s[1], s[3].id))
        # cluster segments that are close and overlap in extent
        clusters: list[list[list]] = []
        for seg in segs:
            for cluster in clusters:
                if any(abs(seg[0] - o[0]) < SEPARATION and seg[1] < o[2] - 0.5 and o[1] < seg[2] - 0.5 and o[3] is not seg[3]
                       for o in cluster):
                    cluster.append(seg)
                    break
            else:
                clusters.append([seg])
        for cluster in clusters:
            if len({id(s[3]) for s in cluster}) < 2:
                continue
            cluster.sort(key=lambda s: (s[0], s[3].id))
            center = sum(s[0] for s in cluster) / len(cluster)
            for n, (line, lo, hi, edge, i) in enumerate(cluster):
                new = round(center + (n - (len(cluster) - 1) / 2) * SEPARATION, 1)
                if abs(new - line) < 0.01:
                    continue
                probe = Rect(lo, new - 0.5, hi - lo, 1) if horizontal else Rect(new - 0.5, lo, 1, hi - lo)
                if any(probe.intersects(r) for r in hard):
                    continue
                (x1, y1), (x2, y2) = edge.points[i], edge.points[i + 1]
                if horizontal:
                    edge.points[i], edge.points[i + 1] = (x1, new), (x2, new)
                else:
                    edge.points[i], edge.points[i + 1] = (new, y1), (new, y2)


def _shared_pairs(edges: list[EdgeGeom]) -> list[tuple[EdgeGeom, EdgeGeom]]:
    """Pairs of edges with parallel segments closer than 3 px that overlap by 6 px or more (they read as one line)."""
    pairs = []
    for i, e1 in enumerate(edges):
        for e2 in edges[i + 1:]:
            if any(_parallel_close(a1, b1, a2, b2, 3.0) >= 6.0
                   for a1, b1 in zip(e1.points, e1.points[1:]) for a2, b2 in zip(e2.points, e2.points[1:])):
                pairs.append((e1, e2))
    return pairs


def _parallel_close(a1: Point, b1: Point, a2: Point, b2: Point, distance: float) -> float:
    h1, h2 = abs(a1[1] - b1[1]) < 0.01, abs(a2[1] - b2[1]) < 0.01
    if h1 != h2:
        return 0.0
    k = 1 if h1 else 0      # coordinate that is constant along the segment
    j = 0 if h1 else 1
    if abs(a1[k] - a2[k]) >= distance:
        return 0.0
    return min(max(a1[j], b1[j]), max(a2[j], b2[j])) - max(min(a1[j], b1[j]), min(a2[j], b2[j]))


def _segments_close(points_a: list[Point], points_b: list[Point]) -> bool:
    return any(_parallel_close(a1, b1, a2, b2, 3.0) >= 6.0
               for a1, b1 in zip(points_a, points_a[1:]) for a2, b2 in zip(points_b, points_b[1:]))


def _penalty_lines(edges: list[EdgeGeom]) -> list[tuple[bool, float, float, float]]:
    out = []
    for e in edges:
        for a, b in zip(e.points, e.points[1:]):
            if abs(a[1] - b[1]) < 0.01:
                out.append((True, a[1], min(a[0], b[0]), max(a[0], b[0])))
            else:
                out.append((False, a[0], min(a[1], b[1]), max(a[1], b[1])))
    return out


def _repair_shared_lines(edges, by_index, port_info, sides, router: "_Router") -> None:
    """Re-route one edge of each pair that still shares a line, steering it away from every other edge (E10-S5).

    A new route is kept only if it shares no line with any other edge, so a repair never moves the problem.
    """
    index_of = {id(e): i for i, e in by_index.items()}
    for e1, e2 in _shared_pairs(edges):
        if not _segments_close(e1.points, e2.points):
            continue  # an earlier repair already fixed this pair
        for moving in (e2, e1):
            others = [e for e in edges if e is not moving]
            i = index_of[id(moving)]
            sp, ss, tp, ts = port_info[i]
            s_side, t_side = sides[i]
            router.penalty = _penalty_lines(others)
            inbound = {"left": 0, "right": 1, "top": 2, "bottom": 3}[t_side]
            path = router.route(ss, _SIDE_DIR[s_side], ts, inbound)
            router.penalty = []
            if path is None:
                continue
            candidate = _simplify([sp, *path, tp])
            if not any(_segments_close(candidate, o.points) for o in others):
                moving.points = candidate
                router.commit(candidate)
                break


# --- entry point ------------------------------------------------------------------------------

def build_geometry(spec: DiagramSpec) -> DiagramGeometry:
    """Lay out a flowchart/architecture spec. Sequence diagrams use build_sequence_geometry."""
    layout = _Layout(spec)
    lr = layout.lr
    positions = layout.run()
    nodes = layout.nodes
    for node_id, (x, y) in positions.items():
        node = nodes[node_id]
        fp = node.footprint
        node.move(x - fp.x, y - fp.y)

    depth: dict[str, int] = {}
    for gid in layout.group_ids:
        d, parent = 0, layout.group_parent[gid]
        while parent is not None and d < 20:
            d, parent = d + 1, layout.group_parent[parent]
        depth[gid] = d
    labels = {g.id: g.label for g in spec.groups}
    groups = [
        GroupGeom(gid, labels[gid], layout.group_parent[gid], layout.group_rects[gid], depth[gid])
        for gid in sorted(layout.group_ids, key=lambda g: (depth[g], layout.group_ids.index(g)))
        if gid in layout.group_rects
    ]

    # Leave room for the title above everything.
    title = TitleGeom(spec.title, Rect(0, 0, text_width(spec.title, TITLE_FONT), 22)) if spec.title else None
    shift_y = MARGIN + (34 if title else 0)
    for node in nodes.values():
        node.move(MARGIN, shift_y)
    for g in groups:
        g.rect = g.rect.moved(MARGIN, shift_y)

    content = None
    for r in [n.footprint for n in nodes.values()] + [g.rect for g in groups]:
        content = r if content is None else content.union(r)
    content = content or Rect(MARGIN, shift_y, 200, 100)
    bounds = content.inflate(MARGIN + 16)

    # Ports: one per edge end, spread along the side by the far end's position.
    ends: dict[tuple[str, str], list[tuple[float, int, str]]] = {}
    valid = [(i, e) for i, e in enumerate(spec.edges) if e.from_node in nodes and e.to_node in nodes and e.from_node != e.to_node]
    sides: dict[int, tuple[str, str]] = {}
    for i, e in valid:
        s_side, t_side = _sides(nodes[e.from_node], nodes[e.to_node], lr)
        sides[i] = (s_side, t_side)
        other_t, other_s = nodes[e.to_node].body, nodes[e.from_node].body
        key_s = other_t.cy if s_side in ("left", "right") else other_t.cx
        key_t = other_s.cy if t_side in ("left", "right") else other_s.cx
        ends.setdefault((e.from_node, s_side), []).append((key_s, i, "s"))
        ends.setdefault((e.to_node, t_side), []).append((key_t, i, "t"))
    # Decision branches leave from different tips of the diamond (flowchart convention).
    for (node_id, side), items in list(ends.items()):
        node = nodes[node_id]
        outgoing = sorted(item for item in items if item[2] == "s")
        if node.kind != "decision" or node.icon is not None or len(outgoing) < 2:
            continue
        tips = ["top", "right", "bottom"] if lr else ["left", "bottom", "right"]
        if len(outgoing) == 2:
            tips = [tips[0], tips[2]]
        ends[(node_id, side)] = [item for item in items if item[2] != "s"]
        for (key, i, which), tip in zip(outgoing, tips):
            sides[i] = (tip, sides[i][1])
            ends.setdefault((node_id, tip), []).append((key, i, which))
    offsets: dict[tuple[int, str], float] = {}
    for (node_id, side), items in ends.items():
        items.sort()
        node = nodes[node_id]
        length = node.body.h if side in ("left", "right") else node.body.w
        spread = [0.0] * len(items) if node.kind == "decision" and node.icon is None else _spread(len(items), length, node.icon is not None)
        for (_, i, which), offset in zip(items, spread):
            offsets[(i, which)] = offset

    router = _Router(nodes, groups, bounds)
    port_info: dict[int, tuple[Point, Point, Point, Point]] = {}
    for i, e in valid:
        s_side, t_side = sides[i]
        sp, ss = _port_points(nodes[e.from_node], s_side, offsets[(i, "s")])
        tp, ts = _port_points(nodes[e.to_node], t_side, offsets[(i, "t")])
        port_info[i] = (sp, ss, tp, ts)
        router.add_coordinates([ss, ts])
    router.build()

    edge_geoms: dict[int, EdgeGeom] = {}
    order = sorted(valid, key=lambda item: abs(port_info[item[0]][1][0] - port_info[item[0]][3][0]) + abs(port_info[item[0]][1][1] - port_info[item[0]][3][1]))
    for i, e in order:
        sp, ss, tp, ts = port_info[i]
        s_side, t_side = sides[i]
        inbound = {"left": 0, "right": 1, "top": 2, "bottom": 3}[t_side]  # direction of travel into the port
        path = router.route(ss, _SIDE_DIR[s_side], ts, inbound)
        if path is None:
            path = [ss, (ts[0], ss[1]), ts] if lr else [ss, (ss[0], ts[1]), ts]
        points = _simplify([sp, *path, tp])
        router.commit(points)
        edge_geoms[i] = EdgeGeom(
            id=f"e{i}_{e.from_node}_{e.to_node}",
            source=e.from_node,
            target=e.to_node,
            points=points,
            lines=wrap(e.label, 22) if e.label else [],
            dashed=e.style == "dashed",
            arrow=e.arrow,
        )
    edges = [edge_geoms[i] for i, _ in valid]
    _nudge_overlaps(edges, router.hard)
    for edge in edges:
        edge.points = _simplify(edge.points)
    _repair_shared_lines(edges, {i: e for i, e in edge_geoms.items()}, port_info, sides, router)

    # Labels: place long ones first; placed labels block later ones.
    blockers = [n.body.inflate(4) for n in nodes.values()] + [n.label.inflate(2) for n in nodes.values() if n.label]
    blockers += [g.title_band for g in groups]
    for g in groups:  # labels never sit on a group border
        r = g.rect
        blockers += [Rect(r.x - 2, r.y - 2, r.w + 4, 4), Rect(r.x - 2, r.y2 - 2, r.w + 4, 4),
                     Rect(r.x - 2, r.y - 2, 4, r.h + 4), Rect(r.x2 - 2, r.y - 2, 4, r.h + 4)]
    labelled = [e for e in edges if e.lines]
    labelled.sort(key=lambda e: -max(text_width(line, EDGE_FONT) for line in e.lines))
    for edge in labelled:
        w = max(text_width(line, EDGE_FONT) for line in edge.lines) + 12
        h = len(edge.lines) * EDGE_LINE_HEIGHT + 6
        near_source = nodes[edge.source].kind == "decision" and nodes[edge.source].icon is None
        _place_label(edge, (round(w), round(h)), blockers, edges, lr, near_source)
        blockers.append(edge.label.inflate(4))

    # Final canvas: everything inside, with a margin.
    extent = content
    for edge in edges:
        for x, y in edge.points:
            extent = extent.union(Rect(x, y, 0, 0))
        if edge.label:
            extent = extent.union(edge.label)
    if title:
        title.rect = Rect(extent.x, MARGIN, title.rect.w, title.rect.h)
        extent = extent.union(title.rect)
    dx, dy = MARGIN - extent.x, MARGIN - extent.y
    for node in nodes.values():
        node.move(dx, dy)
    for g in groups:
        g.rect = g.rect.moved(dx, dy)
    for edge in edges:
        edge.points = [(round(x + dx, 1), round(y + dy, 1)) for x, y in edge.points]
        if edge.label:
            edge.label = edge.label.moved(dx, dy)
    if title:
        title.rect = title.rect.moved(dx, dy)
    width, height = extent.w + 2 * MARGIN, extent.h + 2 * MARGIN
    legend = None
    if {e.dashed for e in edges} == {False, True}:
        # Bottom-left key: "solid = data path, dashed = control / automation" (note §2.5).
        top, items = MARGIN + extent.h + 16, []
        for row, dashed in enumerate((False, True)):
            y = top + row * 20 + 9
            text = LEGEND_TEXT[dashed]
            items.append(LegendItem(dashed, text, ((MARGIN, y), (MARGIN + 36, y)),
                                    Rect(MARGIN + 44, y - 9, text_width(text, EDGE_FONT) + 8, 18)))
        box = items[0].text_rect.union(items[1].text_rect).union(Rect(MARGIN, top, 36, 1))
        legend = LegendGeom(box, items)
        width = max(width, box.x2 + MARGIN)
        height = box.y2 + MARGIN
    return DiagramGeometry(
        direction="LR" if lr else "TB",
        width=math.ceil(width),
        height=math.ceil(height),
        title=title,
        nodes=nodes,
        groups=groups,
        edges=edges,
        family=layout.family,
        legend=legend,
    )


# --- sequence diagrams ------------------------------------------------------------------------

@dataclass
class ParticipantGeom:
    id: str
    lines: list[str]
    actor: bool
    head: Rect
    lifeline_x: float


@dataclass
class MessageGeom:
    id: str
    source: str
    target: str
    points: list[Point]
    lines: list[str]
    label: Rect
    dashed: bool
    async_msg: bool


@dataclass
class NoteGeom:
    id: str
    lines: list[str]
    rect: Rect


@dataclass
class SequenceGeometry:
    width: float
    height: float
    title: TitleGeom | None
    participants: list[ParticipantGeom]
    messages: list[MessageGeom]
    notes: list[NoteGeom]
    lifeline_top: float
    lifeline_bottom: float


def build_sequence_geometry(spec: DiagramSpec) -> SequenceGeometry:
    """Participants spaced so every message label fits between its lifelines; one row per message."""
    title_h = 34 if spec.title else 0
    heads: list[tuple[str, list[str], bool, float, float]] = []
    for p in spec.participants:
        lines = wrap(p.label, 16)
        w = max(110, max(text_width(line) for line in lines) + 28)
        h = (len(lines) * LINE_HEIGHT + 20) if not p.actor else 64 + len(lines) * LINE_HEIGHT
        heads.append((p.id, lines, p.actor, w, h))
    index = {pid: i for i, (pid, *_rest) in enumerate(heads)}
    # minimum distance between neighbouring lifelines
    gaps = [max(120, (heads[i][3] + heads[i + 1][3]) / 2 + 30) for i in range(len(heads) - 1)]
    msg_lines = [wrap(m.label, 28) if m.label else [] for m in spec.messages]
    for m, lines in zip(spec.messages, msg_lines):
        a, b = index.get(m.from_node), index.get(m.to_node)
        if a is None or b is None or a == b or not lines:
            continue
        lo, hi = sorted((a, b))
        need = max(text_width(line, EDGE_FONT) for line in lines) + 40
        span = sum(gaps[lo:hi])
        if span < need:
            extra = (need - span) / (hi - lo)
            for k in range(lo, hi):
                gaps[k] += extra
    head_h = max((h[4] for h in heads), default=40)
    x = MARGIN + heads[0][3] / 2 if heads else MARGIN
    participants = []
    for i, (pid, lines, actor, w, h) in enumerate(heads):
        participants.append(ParticipantGeom(pid, lines, actor, Rect(x - w / 2, MARGIN + title_h, w, head_h), x))
        if i < len(gaps):
            x += gaps[i]
    by_id = {p.id: p for p in participants}

    y = MARGIN + title_h + head_h + 30
    messages, notes = [], []
    for k, (m, lines) in enumerate(zip(spec.messages, msg_lines)):
        src, tgt = by_id.get(m.from_node), by_id.get(m.to_node)
        if src is None or tgt is None:
            continue
        lh = max(1, len(lines)) * EDGE_LINE_HEIGHT
        y += lh + 6
        lw = (max(text_width(line, EDGE_FONT) for line in lines) + 10) if lines else 0
        if src is tgt:
            pts = [(src.lifeline_x, y), (src.lifeline_x + 40, y), (src.lifeline_x + 40, y + 24), (src.lifeline_x, y + 24)]
            label = Rect(src.lifeline_x + 46, y - lh / 2 + 6, lw, lh)
            y += 24
        else:
            pts = [(src.lifeline_x, y), (tgt.lifeline_x, y)]
            mid = (src.lifeline_x + tgt.lifeline_x) / 2
            label = Rect(mid - lw / 2, y - lh - 4, lw, lh)
        messages.append(MessageGeom(f"m_{k}", m.from_node, m.to_node, pts, lines, label, m.return_msg, m.async_msg))
        if m.note:
            anchor = by_id.get(m.over or m.from_node, src)
            note_lines = wrap(m.note, 26)
            nw = max(text_width(line) for line in note_lines) + 20
            nh = len(note_lines) * LINE_HEIGHT + 12
            y += 14
            notes.append(NoteGeom(f"n_{k}", note_lines, Rect(anchor.lifeline_x - nw / 2, y, nw, nh)))
            y += nh
        y += 18
    bottom = y + 20
    right = max([p.head.x2 for p in participants] + [n.rect.x2 for n in notes] + [m.label.x2 for m in messages] + [MARGIN + 200])
    title = TitleGeom(spec.title, Rect(MARGIN, MARGIN, text_width(spec.title, TITLE_FONT), 22)) if spec.title else None
    return SequenceGeometry(
        width=math.ceil(right + MARGIN),
        height=math.ceil(bottom + MARGIN),
        title=title,
        participants=participants,
        messages=messages,
        notes=notes,
        lifeline_top=MARGIN + title_h + head_h,
        lifeline_bottom=bottom,
    )
