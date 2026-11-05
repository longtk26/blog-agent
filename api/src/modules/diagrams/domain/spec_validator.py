"""Validator for DiagramSpec ensuring model output correctness before XML or layout generation (E7-S1)."""

from src.modules.diagrams.domain.icons import lookup
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec


def validate_spec(spec: DiagramSpec) -> list[str]:
    """Validate DiagramSpec against strict structural and stylistic rules.
    
    Returns a list of error strings. Empty list indicates spec is valid.
    """
    errors: list[str] = []

    # 1. Sequence diagrams vs flowchart/architecture diagrams
    if spec.type == "sequence":
        return _validate_sequence_spec(spec)

    # 2. Flowchart and Architecture diagrams validation
    if not spec.nodes:
        errors.append("Flowchart and architecture diagrams must define at least one node in 'nodes'")

    # Limits
    if len(spec.nodes) > 30:
        errors.append(f"Too many nodes: {len(spec.nodes)} (maximum is 30)")
    if len(spec.edges) > 50:
        errors.append(f"Too many edges: {len(spec.edges)} (maximum is 50)")

    # ID uniqueness & reserved IDs
    seen_ids: set[str] = set()
    node_ids: set[str] = set()
    for node in spec.nodes:
        if not node.id or not node.id.strip():
            errors.append("Node ID cannot be empty")
            continue
        if node.id in ("0", "1"):
            errors.append(f"Node ID '{node.id}' is reserved in draw.io (0 and 1 are root cells)")
        if node.id in seen_ids:
            errors.append(f"Duplicate ID found: '{node.id}'")
        seen_ids.add(node.id)
        node_ids.add(node.id)

        # Label length check (each line <= 60 chars)
        lines = node.label.split("\n")
        for line in lines:
            if len(line.strip()) > 60:
                errors.append(f"Node '{node.id}' label line exceeds 60 characters: '{line[:40]}...'")
                break

    group_ids: set[str] = set()
    for group in spec.groups:
        if not group.id or not group.id.strip():
            errors.append("Group ID cannot be empty")
            continue
        if group.id in ("0", "1"):
            errors.append(f"Group ID '{group.id}' is reserved in draw.io")
        if group.id in seen_ids:
            errors.append(f"Duplicate ID found across nodes/groups: '{group.id}'")
        seen_ids.add(group.id)
        group_ids.add(group.id)

        for line in group.label.split("\n"):
            if len(line.strip()) > 60:
                errors.append(f"Group '{group.id}' label line exceeds 60 characters: '{line[:40]}...'")
                break

    # Group references and cycle detection
    for node in spec.nodes:
        if node.group and node.group not in group_ids:
            errors.append(f"Node '{node.id}' references non-existent group '{node.group}'")
        if node.icon and lookup(node.icon) is None:
            errors.append(
                f"Node '{node.id}' has unknown icon '{node.icon}': use one of the icon keys listed in the instructions "
                "(e.g. aws:eks, gcp:cloud_run, k8s:pod, gh:github) or leave icon empty"
            )

    parent_map: dict[str, str] = {}
    for group in spec.groups:
        if group.parent:
            if group.parent not in group_ids:
                errors.append(f"Group '{group.id}' references non-existent parent group '{group.parent}'")
            elif group.parent == group.id:
                errors.append(f"Group '{group.id}' cannot be its own parent")
            else:
                parent_map[group.id] = group.parent

    # Cycle detection in groups
    for gid in group_ids:
        visited = set()
        curr = gid
        while curr in parent_map:
            if curr in visited:
                errors.append(f"Group hierarchy contains a cycle involving group '{curr}'")
                break
            visited.add(curr)
            curr = parent_map[curr]

    # Edge references and label checks
    connected_nodes: set[str] = set()
    for idx, edge in enumerate(spec.edges):
        if edge.from_node not in node_ids:
            errors.append(f"Edge {idx} 'from' references non-existent node '{edge.from_node}'")
        else:
            connected_nodes.add(edge.from_node)

        if edge.to_node not in node_ids:
            errors.append(f"Edge {idx} 'to' references non-existent node '{edge.to_node}'")
        else:
            connected_nodes.add(edge.to_node)

        if edge.label:
            for line in edge.label.split("\n"):
                if len(line.strip()) > 60:
                    errors.append(f"Edge label exceeds 60 characters: '{line[:40]}...'")
                    break

    # Orphan node check: each node must have at least one connected edge unless kind is 'note'
    if len(spec.nodes) > 1:
        for node in spec.nodes:
            if node.kind != "note" and node.id not in connected_nodes:
                errors.append(f"Orphan node '{node.id}' has no connected edges (only 'note' kind may be isolated)")

    return errors


def _validate_sequence_spec(spec: DiagramSpec) -> list[str]:
    errors: list[str] = []

    if not spec.participants:
        errors.append("Sequence diagram must have at least one participant")
        return errors

    seen_pids = set()
    for p in spec.participants:
        if not p.id or not p.id.strip():
            errors.append("Participant ID cannot be empty")
            continue
        if p.id in ("0", "1"):
            errors.append(f"Participant ID '{p.id}' is reserved in draw.io")
        if p.id in seen_pids:
            errors.append(f"Duplicate participant ID: '{p.id}'")
        seen_pids.add(p.id)
        for line in p.label.split("\n"):
            if len(line.strip()) > 60:
                errors.append(f"Participant '{p.id}' label line exceeds 60 chars")
                break

    for idx, msg in enumerate(spec.messages):
        if msg.from_node not in seen_pids:
            errors.append(f"Message {idx} 'from' references non-existent participant '{msg.from_node}'")
        if msg.to_node not in seen_pids:
            errors.append(f"Message {idx} 'to' references non-existent participant '{msg.to_node}'")
        if msg.over and msg.over not in seen_pids:
            errors.append(f"Message {idx} 'over' references non-existent participant '{msg.over}'")
        if msg.label:
            for line in msg.label.split("\n"):
                if len(line.strip()) > 60:
                    errors.append(f"Message {idx} label exceeds 60 chars: '{line[:40]}...'")
                    break

    return errors
