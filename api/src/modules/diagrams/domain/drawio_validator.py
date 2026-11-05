"""XML validation and round-trip verification for draw.io files (E7-S3, hygiene rules from E10-S5)."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Set, Tuple

from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec


# Markup draw.io renders inside html=1 labels. Anything else means a label was not escaped twice
# (`<sha>` must be written `&amp;lt;sha&amp;gt;` in the attribute to display as text).
_LABEL_TAGS = {"br", "b", "i", "u", "s", "font", "span", "div", "p", "sub", "sup", "strong", "em", "code", "hr"}
_TAG = re.compile(r"<\s*/?\s*([A-Za-z][\w:-]*)")
LEGEND_PREFIX = "legend"


def label_markup_errors(cell_id: str, value: str, style: str) -> list[str]:
    if "html=1" not in style or "<" not in value:
        return []
    bad = sorted({t.lower() for t in _TAG.findall(value)} - _LABEL_TAGS)
    return [f"Cell '{cell_id}' label has unescaped markup <{', '.join(bad)}> (escape it twice in the XML)"] if bad else []


@dataclass
class DrawioValidationResult:
    is_valid: bool
    errors: list[str]
    parsed_nodes: set[str]
    parsed_edges: set[tuple[str, str]]


def validate_drawio_xml(xml_content: str, spec: DiagramSpec | None = None, strict: bool = True) -> DrawioValidationResult:
    """Validate draw.io XML structure and optionally perform round-trip check with DiagramSpec.

    strict (generated files) adds the hygiene rules: no XML comments, label markup escaped twice. Owner uploads are
    validated with strict=False, since a hand-edited label may legitimately hold HTML lists or tables.
    """
    errors: list[str] = []
    parsed_nodes: set[str] = set()
    parsed_edges: set[tuple[str, str]] = set()

    if not xml_content or not xml_content.strip():
        return DrawioValidationResult(False, ["XML content is empty"], set(), set())

    if strict and "<!--" in xml_content:
        errors.append("XML comments are not allowed in draw.io files")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        return DrawioValidationResult(False, [f"XML parse error: {exc}"], set(), set())

    # Check root tags
    if root.tag != "mxfile":
        errors.append(f"Root tag must be 'mxfile', got '{root.tag}'")

    diagram = root.find("diagram")
    if diagram is None:
        errors.append("Missing <diagram> element")
        return DrawioValidationResult(False, errors, set(), set())

    graph_model = diagram.find("mxGraphModel")
    if graph_model is None:
        errors.append("Missing <mxGraphModel> element")
        return DrawioValidationResult(False, errors, set(), set())

    model_root = graph_model.find("root")
    if model_root is None:
        errors.append("Missing <root> element under <mxGraphModel>")
        return DrawioValidationResult(False, errors, set(), set())

    # Collect all cells
    all_cells = model_root.findall("mxCell")
    cell_ids: set[str] = set()
    has_root_0 = False
    has_root_1 = False

    for cell in all_cells:
        cid = cell.attrib.get("id")
        if not cid:
            errors.append("mxCell element is missing 'id' attribute")
            continue
        if cid in cell_ids:
            errors.append(f"Duplicate cell id found: '{cid}'")
        cell_ids.add(cid)

        if cid == "0":
            has_root_0 = True
        elif cid == "1":
            has_root_1 = True

    if not has_root_0:
        errors.append("Missing root cell '0'")
    if not has_root_1:
        errors.append("Missing root layer cell '1'")

    # Check vertices and edges
    for cell in all_cells:
        cid = cell.attrib.get("id")
        if cid in ("0", "1"):
            continue

        parent = cell.attrib.get("parent")
        if not parent:
            errors.append(f"Cell '{cid}' is missing 'parent' attribute")
        elif parent not in cell_ids:
            errors.append(f"Cell '{cid}' parent '{parent}' does not exist")

        geom = cell.find("mxGeometry")
        if geom is None:
            errors.append(f"Cell '{cid}' is missing <mxGeometry>")
        if strict:
            errors.extend(label_markup_errors(cid, cell.attrib.get("value", ""), cell.attrib.get("style", "")))

        is_vertex = cell.attrib.get("vertex") == "1"
        is_edge = cell.attrib.get("edge") == "1"

        if is_vertex:
            # Containers and free text (the diagram title, annotations) are not spec nodes.
            style = cell.attrib.get("style", "")
            if cell.attrib.get("container") != "1" and not style.startswith("text;") and not cid.startswith(LEGEND_PREFIX):
                parsed_nodes.add(cid)
        elif is_edge:
            src = cell.attrib.get("source")
            tgt = cell.attrib.get("target")
            if src and tgt:
                if src not in cell_ids:
                    errors.append(f"Edge '{cid}' source '{src}' does not exist")
                if tgt not in cell_ids:
                    errors.append(f"Edge '{cid}' target '{tgt}' does not exist")
                parsed_edges.add((src, tgt))

    # Round-trip verification if spec is provided
    if spec is not None and not errors:
        if spec.type in ("flowchart", "architecture"):
            spec_node_ids = {n.id for n in spec.nodes}
            spec_edge_pairs = {(e.from_node, e.to_node) for e in spec.edges}

            missing_nodes = spec_node_ids - parsed_nodes
            extra_nodes = parsed_nodes - spec_node_ids
            if missing_nodes:
                errors.append(f"Round-trip mismatch: nodes in spec missing from XML: {sorted(missing_nodes)}")
            if extra_nodes:
                errors.append(f"Round-trip mismatch: extra nodes in XML not in spec: {sorted(extra_nodes)}")

            missing_edges = spec_edge_pairs - parsed_edges
            if missing_edges:
                errors.append(f"Round-trip mismatch: edges in spec missing from XML: {sorted(missing_edges)}")
        elif spec.type == "sequence":
            spec_participant_ids = {p.id for p in spec.participants}
            missing_participants = spec_participant_ids - parsed_nodes
            if missing_participants:
                errors.append(f"Round-trip mismatch: participants missing from XML: {sorted(missing_participants)}")

    return DrawioValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        parsed_nodes=parsed_nodes,
        parsed_edges=parsed_edges,
    )
