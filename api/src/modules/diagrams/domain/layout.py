"""Deterministic layout for diagrams using Graphviz DOT or deterministic fallback (E7-S2)."""

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, Tuple

from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec, DiagramNode


@dataclass
class NodeRect:
    x: int
    y: int
    width: int
    height: int


@dataclass
class LayoutResult:
    nodes: dict[str, NodeRect]  # node_id -> NodeRect
    groups: dict[str, NodeRect]  # group_id -> NodeRect
    total_width: int
    total_height: int


def snap(val: float, grid: int = 10) -> int:
    return int(round(val / grid) * grid)


def compute_node_dimensions(node: DiagramNode) -> tuple[int, int]:
    """Compute width and height based on label length and line count."""
    lines = node.label.split("\n")
    max_line_len = max(len(l) for l in lines) if lines else 10
    
    # Base dimensions depending on kind
    if node.kind == "decision":
        w = max(140, max_line_len * 9 + 40)
        h = max(80, len(lines) * 22 + 40)
    elif node.kind == "datastore":
        w = max(130, max_line_len * 8 + 30)
        h = max(80, len(lines) * 20 + 40)
    elif node.kind == "actor":
        w = 80
        h = 100
    else:
        w = max(140, max_line_len * 8 + 30)
        h = max(60, len(lines) * 20 + 30)
        
    return snap(w), snap(h)


def compute_layout(spec: DiagramSpec) -> LayoutResult:
    """Compute deterministic (x, y) coordinates for all nodes and groups.
    
    Uses Graphviz `dot -Tplain` if available, otherwise falls back to a 
    deterministic topological rank layout.
    """
    if spec.type == "sequence":
        return _layout_sequence(spec)

    dot_bin = shutil.which("dot")
    if dot_bin:
        try:
            return _layout_graphviz(spec, dot_bin)
        except Exception:
            # Fall back if dot execution fails
            pass

    return _layout_deterministic_fallback(spec)


def _build_dot_source(spec: DiagramSpec) -> tuple[str, dict[str, tuple[int, int]]]:
    """Generate Graphviz DOT source from DiagramSpec."""
    sizes: dict[str, tuple[int, int]] = {}
    lines = [
        "digraph G {",
        f"  rankdir={spec.direction};",
        "  nodesep=0.6;",
        "  ranksep=0.8;",
        "  compound=true;",
        '  node [shape=box];',
    ]

    # Group nodes by group_id
    nodes_by_group: dict[str | None, list[DiagramNode]] = {None: []}
    for g in spec.groups:
        nodes_by_group[g.id] = []
    for node in spec.nodes:
        gid = node.group if (node.group and node.group in nodes_by_group) else None
        nodes_by_group[gid].append(node)

    # Output clusters
    for g in spec.groups:
        lines.append(f'  subgraph "cluster_{g.id}" {{')
        lines.append(f'    label="{g.label}";')
        for node in nodes_by_group.get(g.id, []):
            w, h = compute_node_dimensions(node)
            sizes[node.id] = (w, h)
            lines.append(f'    "{node.id}" [width={w / 72.0:.2f}, height={h / 72.0:.2f}];')
        lines.append("  }")

    # Root nodes
    for node in nodes_by_group[None]:
        w, h = compute_node_dimensions(node)
        sizes[node.id] = (w, h)
        lines.append(f'  "{node.id}" [width={w / 72.0:.2f}, height={h / 72.0:.2f}];')

    # Edges
    for edge in spec.edges:
        lines.append(f'  "{edge.from_node}" -> "{edge.to_node}";')

    lines.append("}")
    return "\n".join(lines), sizes


def _layout_graphviz(spec: DiagramSpec, dot_bin: str) -> LayoutResult:
    dot_src, sizes = _build_dot_source(spec)
    proc = subprocess.run(
        [dot_bin, "-Tplain"],
        input=dot_src,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    graph_height = 0.0
    graph_width = 0.0
    pos: dict[str, tuple[float, float]] = {}

    for line in proc.stdout.splitlines():
        tokens = shlex.split(line)
        if not tokens:
            continue
        if tokens[0] == "graph":
            graph_width = float(tokens[2]) * 72
            graph_height = float(tokens[3]) * 72
        elif tokens[0] == "node":
            nid = tokens[1]
            pos[nid] = (float(tokens[2]) * 72, float(tokens[3]) * 72)

    # Flip Y axis (Graphviz origin is bottom-left, draw.io is top-left)
    node_rects: dict[str, NodeRect] = {}
    for node in spec.nodes:
        w, h = sizes.get(node.id, (140, 60))
        if node.id in pos:
            xc, yc = pos[node.id]
            x = snap(xc - w / 2)
            y = snap((graph_height - yc) - h / 2)
            node_rects[node.id] = NodeRect(x=max(20, x), y=max(20, y), width=w, height=h)
        else:
            node_rects[node.id] = NodeRect(x=40, y=40, width=w, height=h)

    # Compute bounding boxes for groups
    group_rects = _compute_group_boxes(spec, node_rects)

    return LayoutResult(
        nodes=node_rects,
        groups=group_rects,
        total_width=snap(max(graph_width + 80, 800)),
        total_height=snap(max(graph_height + 80, 600)),
    )


def _layout_deterministic_fallback(spec: DiagramSpec) -> LayoutResult:
    """Fallback layout engine ensuring deterministic coordinate placement without Graphviz."""
    node_rects: dict[str, NodeRect] = {}
    sizes = {n.id: compute_node_dimensions(n) for n in spec.nodes}

    # Graph adjacency and in-degree
    adj: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    in_degree: dict[str, int] = {n.id: 0 for n in spec.nodes}
    for e in spec.edges:
        if e.from_node in adj and e.to_node in in_degree:
            adj[e.from_node].append(e.to_node)
            in_degree[e.to_node] += 1

    # Assign layers/ranks deterministically
    ranks: dict[str, int] = {}
    queue = [n.id for n in spec.nodes if in_degree[n.id] == 0]
    if not queue and spec.nodes:
        queue = [spec.nodes[0].id]

    for nid in queue:
        ranks[nid] = 0

    visited = set()
    while queue:
        curr = queue.pop(0)
        visited.add(curr)
        cur_rank = ranks[curr]
        for neighbor in adj.get(curr, []):
            ranks[neighbor] = max(ranks.get(neighbor, 0), cur_rank + 1)
            if neighbor not in visited and neighbor not in queue:
                queue.append(neighbor)

    for n in spec.nodes:
        if n.id not in ranks:
            ranks[n.id] = 0

    # Group nodes by rank
    ranks_map: dict[int, list[str]] = {}
    for nid, r in sorted(ranks.items(), key=lambda item: (item[1], item[0])):
        ranks_map.setdefault(r, []).append(nid)

    is_lr = spec.direction == "LR"
    max_x, max_y = 60, 60

    for r in sorted(ranks_map.keys()):
        node_ids_in_rank = ranks_map[r]
        for idx, nid in enumerate(node_ids_in_rank):
            w, h = sizes[nid]
            if is_lr:
                x = 60 + r * 260
                y = 60 + idx * 120
            else:
                x = 60 + idx * 220
                y = 60 + r * 140
            node_rects[nid] = NodeRect(x=snap(x), y=snap(y), width=w, height=h)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

    group_rects = _compute_group_boxes(spec, node_rects)

    return LayoutResult(
        nodes=node_rects,
        groups=group_rects,
        total_width=snap(max_x + 80),
        total_height=snap(max_y + 80),
    )


def _compute_group_boxes(spec: DiagramSpec, node_rects: dict[str, NodeRect]) -> dict[str, NodeRect]:
    group_rects: dict[str, NodeRect] = {}
    pad = 30
    for g in spec.groups:
        member_rects = [node_rects[n.id] for n in spec.nodes if n.group == g.id and n.id in node_rects]
        if member_rects:
            min_x = min(r.x for r in member_rects) - pad
            min_y = min(r.y for r in member_rects) - (pad + 10)  # extra room for title
            max_x = max(r.x + r.width for r in member_rects) + pad
            max_y = max(r.y + r.height for r in member_rects) + pad
            group_rects[g.id] = NodeRect(x=snap(min_x), y=snap(min_y), width=snap(max_x - min_x), height=snap(max_y - min_y))
        else:
            group_rects[g.id] = NodeRect(x=40, y=40, width=200, height=120)
    return group_rects


def _layout_sequence(spec: DiagramSpec) -> LayoutResult:
    """Pure arithmetic sequence layout."""
    node_rects: dict[str, NodeRect] = {}
    p_count = len(spec.participants)
    m_count = len(spec.messages)
    
    total_w = snap(max(800, p_count * 200 + 100))
    total_h = snap(max(500, m_count * 60 + 160))

    for idx, p in enumerate(spec.participants):
        x = snap(60 + idx * 200)
        y = 50
        node_rects[p.id] = NodeRect(x=x, y=y, width=120, height=total_h - 100)

    return LayoutResult(
        nodes=node_rects,
        groups={},
        total_width=total_w,
        total_height=total_h,
    )
