"""Readability guarantees of the diagram layout: nothing overlaps, edges avoid shapes, labels stay clear."""

import itertools
import re

import pytest

from src.modules.diagrams.domain.diagram_builder import build_diagram
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.geometry import Rect, build_geometry, build_sequence_geometry
from src.modules.diagrams.domain.icons import resolve_icon
from src.modules.diagrams.domain.schemas.diagram_spec import (
    DiagramEdge as E,
    DiagramGroup as G,
    DiagramMessage,
    DiagramNode as N,
    DiagramParticipant,
    DiagramSpec,
)


def edge(a: str, b: str, label: str | None = None, **kw) -> E:
    return E(**{"from": a, "to": b, "label": label, **kw})


THREE_TIER = DiagramSpec(
    type="architecture", title="Three-tier web app on AWS", direction="LR",
    groups=[G(id="cloud", label="AWS Cloud"), G(id="vpc", label="VPC (10.0.0.0/16)", parent="cloud"),
            G(id="pub", label="Public Subnet", parent="vpc"), G(id="priv", label="Private Subnet", parent="vpc")],
    nodes=[N(id="user", label="User", kind="actor"),
           N(id="igw", label="[AWS IGW] Internet Gateway", kind="service", group="vpc"),
           N(id="alb", label="[AWS ALB] Load Balancer", kind="service", group="pub"),
           N(id="nat", label="[AWS NAT] NAT Gateway", kind="service", group="pub"),
           N(id="ec2", label="[AWS EC2] App Server", kind="service", group="priv"),
           N(id="rds", label="[AWS RDS] Postgres", kind="datastore", group="priv")],
    edges=[edge("user", "igw", "HTTPS"), edge("igw", "alb", "0.0.0.0/0"), edge("alb", "ec2", "Internal traffic"),
           edge("ec2", "nat", "Outbound"), edge("ec2", "rds", "SQL")],
)

# Shaped after assets/samples/architecture.drawio: dense, with a back edge into an outside service.
MEDIA = DiagramSpec(
    type="architecture", title="Workflow: upload and transcode video", direction="LR",
    groups=[G(id="aws", label="AWS"), G(id="proc", label="Processing", parent="aws")],
    nodes=[N(id="be", label="Backend", kind="service", icon="server"),
           N(id="in", label="S3 (video-inputs/)", kind="datastore", icon="aws:s3", group="aws"),
           N(id="mc", label="media-convert", kind="service", icon="aws:lambda", group="proc"),
           N(id="emc", label="Media Convert", kind="service", icon="aws:mediaconvert", group="proc"),
           N(id="out", label="S3 (video-outputs/)", kind="datastore", icon="aws:s3", group="aws"),
           N(id="eb", label="Event bridge", kind="service", icon="aws:eventbridge", group="aws"),
           N(id="save", label="save-converted-media", kind="service", icon="aws:lambda", group="proc"),
           N(id="stt", label="speech-to-text", kind="service", icon="aws:lambda", group="proc"),
           N(id="tr", label="AWS Transcribe", kind="service", icon="aws:transcribe", group="proc")],
    edges=[edge("be", "in", "Upload video"), edge("in", "mc", "S3 notification"), edge("mc", "emc", "Call job process"),
           edge("emc", "out", "Create processed files"), edge("emc", "eb", "Job status"), edge("eb", "save"),
           edge("save", "be", "Save .m3u8 files", style="dashed"), edge("in", "stt", "S3 notification"),
           edge("stt", "tr", "Create subtitle file"), edge("tr", "out", ".srt")],
)

FLOW = DiagramSpec(
    type="flowchart", title="Fine-tuning decision", direction="TB",
    nodes=[N(id="s", label="Improve LLM performance"), N(id="d1", label="Need dynamic or private facts?", kind="decision"),
           N(id="rag", label="Use RAG (vector DB + search)"), N(id="d2", label="Need custom tone or structure?", kind="decision"),
           N(id="ft", label="Fine-tune (PEFT / QLoRA)"), N(id="pr", label="Use prompting"),
           N(id="data", label="Curated dataset", kind="datastore")],
    edges=[edge("s", "d1"), edge("d1", "rag", "Yes"), edge("d1", "d2", "No"), edge("d2", "ft", "Yes"), edge("d2", "pr", "No"),
           edge("data", "ft", "500+ examples"), edge("rag", "ft", "combine", style="dashed")],
)


def _hits(points, rect: Rect) -> bool:
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if Rect(min(x1, x2), min(y1, y2), abs(x2 - x1) + 0.01, abs(y2 - y1) + 0.01).intersects(rect):
            return True
    return False


@pytest.mark.parametrize("spec", [THREE_TIER, MEDIA, FLOW], ids=["three-tier", "media", "flow"])
def test_layout_is_readable(spec):
    g = build_geometry(spec)
    nodes = g.nodes
    for a, b in itertools.combinations(nodes, 2):
        assert not nodes[a].footprint.intersects(nodes[b].footprint), f"{a} overlaps {b}"
    for e in g.edges:
        assert all(x1 == x2 or y1 == y2 for (x1, y1), (x2, y2) in zip(e.points, e.points[1:])), f"{e.id} not orthogonal"
        start, end = e.points[0], e.points[-1]
        src, tgt = nodes[e.source].body, nodes[e.target].body
        assert src.inflate(0.5).contains(*start) and tgt.inflate(0.5).contains(*end), f"{e.id} does not touch its shapes"
        for key, n in nodes.items():
            if key not in (e.source, e.target):
                assert not _hits(e.points, n.body.inflate(-1)), f"{e.id} crosses {key}"
            if n.label:
                assert not _hits(e.points, n.label.inflate(-1)), f"{e.id} crosses the label of {key}"
        if e.label:
            for key, n in nodes.items():
                assert not e.label.intersects(n.body) and not (n.label and e.label.intersects(n.label)), f"label of {e.id} on {key}"
    labels = [e for e in g.edges if e.label]
    assert len(labels) == sum(1 for e in spec.edges if e.label)
    for a, b in itertools.combinations(labels, 2):
        assert not a.label.intersects(b.label), f"labels of {a.id} and {b.id} overlap"
    for group in g.groups:
        for key, n in nodes.items():
            assert not n.footprint.intersects(group.title_band), f"{key} covers the title of {group.id}"
    for n in spec.nodes:
        if n.group:
            box = next(gr.rect for gr in g.groups if gr.id == n.group)
            fp = nodes[n.id].footprint
            assert box.x <= fp.x and fp.x2 <= box.x2 and box.y <= fp.y and fp.y2 <= box.y2, f"{n.id} outside {n.group}"
    for child in g.groups:
        if child.parent:
            parent = next(gr.rect for gr in g.groups if gr.id == child.parent)
            assert parent.x < child.rect.x and child.rect.x2 < parent.x2 and parent.y < child.rect.y and child.rect.y2 < parent.y2
    # siblings never overlap
    for a, b in itertools.combinations(g.groups, 2):
        if a.parent == b.parent:
            assert not a.rect.intersects(b.rect)


def test_flow_starts_left_and_back_edges_do_not_reorder():
    g = build_geometry(MEDIA)
    assert g.nodes["be"].body.x < g.nodes["in"].body.x < g.nodes["mc"].body.x  # Backend starts the flow


def test_decision_branches_leave_from_different_tips():
    g = build_geometry(FLOW)
    starts = {e.target: e.points[0] for e in g.edges if e.source == "d1"}
    diamond = g.nodes["d1"].body
    assert starts["rag"][0] == pytest.approx(diamond.x) and starts["d2"][0] == pytest.approx(diamond.x2)


def test_icons_resolve_from_tags_keys_and_kinds():
    icon, label = resolve_icon(None, "[AWS EC2] App Server", "service", "architecture")
    assert icon.key == "aws:ec2" and label == "App Server"
    assert resolve_icon("lambda", "media-convert", "service", "flowchart")[0].key == "aws:lambda"
    assert resolve_icon(None, "Postgres (RDS)", "datastore", "architecture")[0].key == "aws:rds"
    assert resolve_icon(None, "User", "actor", "flowchart")[0].key == "user"
    assert resolve_icon(None, "Tokenize text", "process", "flowchart")[0] is None  # flowchart steps stay boxes


def test_unknown_icon_is_a_spec_error():
    from src.modules.diagrams.domain.spec_validator import validate_spec

    spec = DiagramSpec(nodes=[N(id="a", label="A", icon="aws:teleporter"), N(id="b", label="B")], edges=[edge("a", "b")])
    assert any("unknown icon" in e for e in validate_spec(spec))


def test_drawio_matches_geometry_and_round_trips():
    built = build_diagram(THREE_TIER)
    result = validate_drawio_xml(built.drawio_xml, THREE_TIER)
    assert result.is_valid, result.errors
    g = build_geometry(THREE_TIER)
    xml = built.drawio_xml
    # every edge is pinned to the routed ports and carries the routed bends
    for e in g.edges:
        cell = re.search(rf'<mxCell id="{e.id}"[^>]*>.*?</mxCell>', xml, re.S).group(0)
        assert "exitPerimeter=0" in cell and "entryPerimeter=0" in cell
        assert cell.count("<mxPoint") == len(e.points) - 2
    assert 'resIcon=mxgraph.aws4.ec2' in xml and 'grIcon=mxgraph.aws4.group_vpc2' in xml
    assert 'background="#0B1120"' in xml


def test_svg_embeds_drawio_and_is_sized_to_content():
    built = build_diagram(MEDIA)
    assert built.svg.startswith("<svg") and 'content="&lt;mxfile' in built.svg
    assert f'viewBox="0 0 {built.width} {built.height}"' in built.svg
    assert "<script" not in built.svg and " on" not in re.sub(r'content="[^"]*"', "", built.svg).split("<defs>")[0]


def test_sequence_labels_fit_between_lifelines():
    spec = DiagramSpec(
        type="sequence", title="Token refresh",
        participants=[DiagramParticipant(id="c", label="Client"), DiagramParticipant(id="a", label="Auth API"),
                      DiagramParticipant(id="d", label="Database")],
        messages=[DiagramMessage(**{"from": "c", "to": "a", "label": "POST /token with an expired refresh token"}),
                  DiagramMessage(**{"from": "a", "to": "d", "label": "lookup"}),
                  DiagramMessage(**{"from": "a", "to": "c", "label": "401", "return": True})],
    )
    g = build_sequence_geometry(spec)
    xs = {p.id: p.lifeline_x for p in g.participants}
    first = g.messages[0]
    assert xs["c"] < first.label.x and first.label.x2 < xs["a"]
    assert validate_drawio_xml(build_diagram(spec).drawio_xml, spec).is_valid
