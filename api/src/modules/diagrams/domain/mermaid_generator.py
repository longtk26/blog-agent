"""Deterministic Mermaid generator applying owner_dark conventions and formatting (E7-S5)."""

from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec, DiagramNode, DiagramEdge

# Owner's Mermaid colour styles
MERMAID_STYLES_OWNER_DARK = {
    "process": "fill:#0369a1,stroke:#38bdf8,stroke-width:2px,color:#ffffff;",
    "decision": "fill:#b45309,stroke:#fbbf24,stroke-width:2px,color:#ffffff;",
    "datastore": "fill:#15803d,stroke:#4ade80,stroke-width:2px,color:#ffffff;",
    "service": "fill:#4338ca,stroke:#818cf8,stroke-width:2px,color:#ffffff;",
    "actor": "fill:#be123c,stroke:#fb7185,stroke-width:2px,color:#ffffff;",
    "external": "fill:#334155,stroke:#94a3b8,stroke-width:2px,color:#ffffff;",
    "note": "fill:#854d0e,stroke:#facc15,stroke-width:2px,color:#ffffff;",
}


def format_mermaid_label(label: str) -> str:
    """Format label with <b> for the first line/title and <br/> for line breaks."""
    clean = label.replace('"', "'")
    lines = clean.split("\n")
    if not lines:
        return ""
    if len(lines) == 1:
        # Check if contains colon
        if ":" in lines[0]:
            title, _, rest = lines[0].partition(":")
            return f"<b>{title.strip()}:</b><br/>{rest.strip()}"
        return f"<b>{lines[0].strip()}</b>"
    
    first = f"<b>{lines[0].strip()}</b>"
    rest = [l.strip() for l in lines[1:] if l.strip()]
    return "<br/>".join([first] + rest)


def generate_mermaid(spec: DiagramSpec) -> str:
    """Generate deterministic Mermaid diagram definition from DiagramSpec."""
    if spec.type == "sequence":
        return _generate_sequence_mermaid(spec)
    return _generate_flowchart_mermaid(spec)


def _generate_flowchart_mermaid(spec: DiagramSpec) -> str:
    direction = "LR" if spec.direction == "LR" else "TD"
    lines = [f"flowchart {direction}"]

    # Nodes grouped by group_id
    nodes_by_group: dict[str | None, list[DiagramNode]] = {None: []}
    for g in spec.groups:
        nodes_by_group[g.id] = []
    for node in spec.nodes:
        gid = node.group if (node.group and node.group in nodes_by_group) else None
        nodes_by_group[gid].append(node)

    # Subgraphs / Groups
    for g in spec.groups:
        lines.append(f'    subgraph {g.id} ["<b>{g.label}</b>"]')
        for node in nodes_by_group.get(g.id, []):
            lines.append(f"        {_format_node_definition(node)}")
        lines.append("    end")

    # Root nodes
    for node in nodes_by_group[None]:
        lines.append(f"    {_format_node_definition(node)}")

    # Edges
    for edge in spec.edges:
        arrow_str = _format_edge_arrow(edge)
        lines.append(f"    {edge.from_node} {arrow_str} {edge.to_node}")

    # Styles
    lines.append("")
    for node in spec.nodes:
        style = MERMAID_STYLES_OWNER_DARK.get(node.kind, MERMAID_STYLES_OWNER_DARK["process"])
        lines.append(f"    style {node.id} {style}")

    return "\n".join(lines)


def _format_node_definition(node: DiagramNode) -> str:
    fmt_label = format_mermaid_label(node.label)
    k = node.kind
    if k == "decision":
        return f'{node.id}{{"{fmt_label}"}}'
    if k == "datastore":
        return f'{node.id}[("{fmt_label}")]'
    if k == "service":
        return f'{node.id}[["{fmt_label}"]]'
    if k == "actor":
        return f'{node.id}(["{fmt_label}"])'
    if k == "external":
        return f'{node.id}[/"{fmt_label}"/]'
    if k == "note":
        return f'{node.id}>"{fmt_label}"]'
    # Default process
    return f'{node.id}["{fmt_label}"]'


def _format_edge_arrow(edge: DiagramEdge) -> str:
    lbl = f"|{edge.label.replace('|', '/')}|" if edge.label else ""
    if edge.style == "dashed":
        if edge.arrow == "both":
            return f"<-.->{lbl}"
        if edge.arrow == "none":
            return f"-.-{lbl}"
        return f"-.->{lbl}"
    else:
        if edge.arrow == "both":
            return f"<-->{lbl}"
        if edge.arrow == "none":
            return f"---{lbl}"
        return f"-->{lbl}"


def _generate_sequence_mermaid(spec: DiagramSpec) -> str:
    lines = ["sequenceDiagram", "    autonumber"]

    for p in spec.participants:
        role = "actor" if p.actor else "participant"
        label = p.label.replace('"', "'")
        lines.append(f'    {role} {p.id} as {label}')

    for msg in spec.messages:
        label = msg.label.replace('"', "'")
        if msg.return_msg:
            arrow = "-->>"
        elif msg.async_msg:
            arrow = "-)"
        else:
            arrow = "->>"
        lines.append(f"    {msg.from_node}{arrow}{msg.to_node}: {label}")
        if msg.note and msg.over:
            lines.append(f"    Note over {msg.over}: {msg.note}")

    return "\n".join(lines)


def choose_diagram_format(spec: DiagramSpec, task_override: str = "auto") -> str:
    """Decide between 'mermaid' and 'drawio' based on node count, nesting, or cloud keywords (E7-S5)."""
    if task_override in ("mermaid", "drawio"):
        return task_override

    # Sequence diagrams work great in Mermaid
    if spec.type == "sequence":
        return "mermaid"

    # Cloud / AWS architecture diagrams look much better in draw.io
    cloud_keywords = {"aws", "vpc", "subnet", "ec2", "cloudfront", "s3", "rds", "lambda", "cloud"}
    all_text = (
        (spec.title or "").lower()
        + " "
        + " ".join(n.label.lower() for n in spec.nodes)
        + " "
        + " ".join(g.label.lower() for g in spec.groups)
    )
    if any(k in all_text for k in cloud_keywords):
        return "drawio"

    # If > 12 nodes or nested groups, prefer draw.io
    has_nested_groups = any(g.parent for g in spec.groups)
    if len(spec.nodes) <= 12 and not has_nested_groups:
        return "mermaid"
    return "drawio"
