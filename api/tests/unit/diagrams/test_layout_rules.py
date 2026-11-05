"""E10-S5/S6: layout rules from the hand-built Memory Up diagrams, checked on the computed geometry."""

import re
import xml.etree.ElementTree as ET

import pytest

from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.geometry import build_geometry
from src.modules.diagrams.domain.group_styles import group_style
from src.modules.diagrams.domain.layout_lint import BORDER_CLEARANCE, LintFinding, lint_geometry
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from tests.unit.diagrams.fixtures import EKS_GITOPS, GCP_SERVERLESS, WEBHOOK_SEQUENCE, edge
from tests.unit.test_diagram_geometry import FLOW, MEDIA, THREE_TIER

ALL = [THREE_TIER, MEDIA, FLOW, EKS_GITOPS, GCP_SERVERLESS]
IDS = ["three-tier", "media", "flow", "eks-gitops", "gcp"]


@pytest.mark.parametrize("spec", ALL, ids=IDS)
def test_fixtures_have_zero_lint_findings(spec):
    findings = lint_geometry(build_geometry(spec))
    assert findings == [], "\n".join(map(str, findings))


@pytest.mark.parametrize("spec", ALL, ids=IDS)
def test_layout_is_deterministic(spec):
    assert generate_drawio_xml(spec) == generate_drawio_xml(spec)


@pytest.mark.parametrize("spec", ALL, ids=IDS)
def test_generated_xml_passes_strict_hygiene(spec):
    xml = generate_drawio_xml(spec)
    result = validate_drawio_xml(xml, spec)
    assert result.is_valid, result.errors
    ids = re.findall(r'<mxCell id="([^"]+)"', xml)
    assert len(ids) == len(set(ids)) and "<!--" not in xml


def test_lint_catches_each_problem():
    """The lint is only useful if it fires: build a geometry and break it on purpose."""
    g = build_geometry(THREE_TIER)
    e = g.edges[0]
    vpc = next(gr for gr in g.groups if gr.id == "vpc")
    y = vpc.rect.y + 2
    e.points = [e.points[0], (e.points[0][0], y), (vpc.rect.x2 - 20, y), (vpc.rect.x2 - 20, e.points[-1][1]), e.points[-1]]
    g.edges[1].points = list(e.points)
    checks = {f.check for f in lint_geometry(g)}
    assert {"edge_on_border", "shared_segment"} <= checks
    assert all(isinstance(f, LintFinding) for f in lint_geometry(g))


def test_edges_keep_clear_of_group_borders():
    g = build_geometry(EKS_GITOPS)
    for e in g.edges:
        for (x1, y1), (x2, y2) in zip(e.points, e.points[1:]):
            for gr in g.groups:
                r = gr.rect
                if y1 == y2 and min(x1, x2) < r.x2 and max(x1, x2) > r.x and abs(x2 - x1) > 6:
                    assert min(abs(y1 - r.y), abs(y1 - r.y2)) >= BORDER_CLEARANCE, (e.id, gr.id)


def test_regional_services_form_a_row_along_the_region_bottom():
    g = build_geometry(EKS_GITOPS)
    row = [g.nodes[k] for k in ("ecr", "s3", "ssm")]
    vpc = next(gr.rect for gr in g.groups if gr.id == "vpc")
    region = next(gr.rect for gr in g.groups if gr.id == "region")
    assert all(n.row for n in row)
    assert len({n.body.y for n in row}) == 1, "one row"
    assert all(n.body.y > vpc.y2 and n.footprint.y2 <= region.y2 for n in row), "below the VPC, inside the region"
    # their edges arrive from above, vertically
    for e in g.edges:
        if e.target in ("ecr", "s3", "ssm"):
            (x1, y1), (x2, y2) = e.points[-2], e.points[-1]
            assert x1 == x2 and y1 < y2, e.id


def test_nodes_linked_to_the_row_move_their_label_off_the_bottom():
    g = build_geometry(EKS_GITOPS)
    assert g.nodes["api"].label_side == "top"          # LR: left/right for flow, bottom for the row
    assert g.nodes["worker"].label_side == "bottom"    # not linked to the row: unchanged


def test_external_systems_sit_on_the_side_of_their_neighbours():
    g = build_geometry(EKS_GITOPS)
    cloud = next(gr.rect for gr in g.groups if gr.id == "cloud")
    nat = g.nodes["nat"].body
    assert nat.cx < cloud.cx                                        # NAT is in the left half of the cloud ...
    for ext in ("db", "acme", "github"):
        assert g.nodes[ext].body.x2 < cloud.x, f"{ext} should be left of the cloud, next to its neighbour"


def test_legend_appears_only_when_both_edge_styles_are_used():
    g = build_geometry(EKS_GITOPS)
    assert g.legend is not None and [i.dashed for i in g.legend.items] == [False, True]
    assert g.legend.rect.y2 <= g.height
    xml = generate_drawio_xml(EKS_GITOPS)
    assert "legend_line_1" in xml and "control / automation" in xml
    assert build_geometry(THREE_TIER).legend is None


def test_edge_parent_is_innermost_common_container_with_relative_waypoints():
    xml = generate_drawio_xml(EKS_GITOPS)
    g = build_geometry(EKS_GITOPS)
    cells = {c.get("id"): c for c in ET.fromstring(xml).iter("mxCell")}
    ing_api = next(e for e in g.edges if e.source == "ing" and e.target == "api")
    assert cells[ing_api.id].get("parent") == "ns_app"
    user_igw = next(e for e in g.edges if e.source == "user")
    assert cells[user_igw.id].get("parent") == "1"
    ns = next(gr.rect for gr in g.groups if gr.id == "ns_app")
    pts = [(float(p.get("x")), float(p.get("y"))) for p in cells[ing_api.id].iter("mxPoint")]
    for (x, y), (ax, ay) in zip(pts, ing_api.points[1:-1]):
        assert x == pytest.approx(ax - ns.x, abs=0.11) and y == pytest.approx(ay - ns.y, abs=0.11)


def test_html_labels_are_escaped_twice():
    spec = DiagramSpec(
        type="flowchart", title="tags",
        nodes=[{"id": "a", "label": "build <sha> & push"}, {"id": "b", "label": 'say "hi"'}],
        edges=[edge("a", "b", "<tag>")],
    )
    xml = generate_drawio_xml(spec)
    assert "&amp;lt;sha&amp;gt; &amp;amp; push" in xml and "&amp;lt;tag&amp;gt;" in xml
    assert validate_drawio_xml(xml, spec).is_valid


def test_validator_rejects_comments_and_unescaped_label_markup():
    bad = generate_drawio_xml(THREE_TIER).replace("<root>", "<root><!-- hi -->", 1)
    assert any("comments" in e for e in validate_drawio_xml(bad).errors)
    raw = generate_drawio_xml(THREE_TIER).replace('value="User"', 'value="&lt;sha&gt;"', 1)
    assert any("unescaped markup" in e for e in validate_drawio_xml(raw).errors)
    assert validate_drawio_xml(raw, strict=False).is_valid       # owner uploads are not held to generator hygiene


def test_group_styles_follow_the_diagram_cloud():
    assert "mxgraph.aws4.group" in group_style("VPC", "aws").drawio
    gcp_vpc = group_style("VPC network", "gcp")
    assert "mxgraph.aws4" not in gcp_vpc.drawio and "#34A853" in gcp_vpc.drawio
    assert "#326CE5" in group_style("Namespace: app", "aws").drawio
    assert build_geometry(GCP_SERVERLESS).family == "gcp" and build_geometry(EKS_GITOPS).family == "aws"
    xml = generate_drawio_xml(GCP_SERVERLESS)
    assert "mxgraph.aws4.group" not in xml and "mxgraph.gcp3.cloudrun" in xml


def test_gcp_label_inference_never_picks_aws_icons():
    spec = DiagramSpec(
        type="architecture", title="lb",
        nodes=[{"id": "a", "label": "Load Balancer", "kind": "service"},
               {"id": "b", "label": "API", "kind": "service", "icon": "gcp:cloud_run"},
               {"id": "c", "label": "Cloud SQL", "kind": "datastore", "icon": "gcp:cloud_sql"}],
        edges=[edge("a", "b"), edge("b", "c")],
    )
    assert build_geometry(spec).nodes["a"].icon.key == "gcp:load_balancing"


def test_prompt_lists_keys_only_within_budget():
    from src.modules.agent.prompts.diagram import diagram_messages, icon_key_list

    keys = icon_key_list()
    assert "shape=" not in keys and "mxgraph" not in keys
    assert len(keys) / 4 <= 300, "icon keys must stay under ~300 prompt tokens"
    system = diagram_messages("t", "h", "g")[0].content
    assert "gcp: " not in system or "gcp (gcp:)" in system
    assert "k8s (k8s:)" in system and "gh (gh:): github" in system


@pytest.mark.parametrize("spec", ALL + [WEBHOOK_SEQUENCE], ids=IDS + ["sequence"])
def test_labelled_edges_have_an_explicit_dark_label_background(spec):
    """draw.io exports resolve labelBackgroundColor=default (or none) to white: light text on white is unreadable."""
    from src.modules.diagrams.domain.palette import LABEL_BG

    for cell in ET.fromstring(generate_drawio_xml(spec)).iter("mxCell"):
        if cell.get("edge") == "1" and cell.get("value"):
            assert f"labelBackgroundColor={LABEL_BG};" in cell.get("style", ""), cell.get("id")
