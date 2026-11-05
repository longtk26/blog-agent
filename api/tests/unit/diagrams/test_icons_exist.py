"""E10-S3: every icon style the agent can emit names a shape draw.io actually has.

Runs offline against tests/fixtures/drawio_shape_index.json.gz, a name list derived from draw.io's shape index at the
commit pinned in catalogue/icon_allowlist.json (`make diagrams-icons` regenerates both).
"""

import gzip
import hashlib
import json
import re
from pathlib import Path

import pytest

from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.icons import CATALOGUE_PATH, ICONS, resolve_icon
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramEdge, DiagramNode, DiagramSpec

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "drawio_shape_index.json.gz"
ALLOWLIST = CATALOGUE_PATH.parent / "icon_allowlist.json"


@pytest.fixture(scope="module")
def index() -> dict:
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    data["shapes"] = set(data["shapes"])
    data["res_icons"] = set(data["res_icons"])
    data["image_style_sha256"] = set(data["image_style_sha256"])
    return data


def _param(style: str, name: str) -> str | None:
    match = re.search(rf"(?:^|;){name}=([^;]+)", style)
    return match.group(1) if match else None


def test_fixture_matches_the_pinned_index_commit(index):
    pinned = json.loads(ALLOWLIST.read_text())["index"]["commit"]
    catalogue = json.loads(CATALOGUE_PATH.read_text())
    assert index["commit"] == pinned == catalogue["index_commit"]


def test_every_allowlisted_icon_is_in_the_catalogue():
    keys = [item["key"] for item in json.loads(ALLOWLIST.read_text())["icons"]]
    assert sorted(keys) == sorted(ICONS)


@pytest.mark.parametrize("key", sorted(ICONS))
def test_icon_shape_names_exist_in_drawio_index(index, key):
    icon = ICONS[key]
    shape = _param(icon.drawio_shape, "shape")
    assert shape, f"{key}: no shape= in {icon.drawio_shape!r}"
    if shape == "image":
        entry = json.loads(CATALOGUE_PATH.read_text())["icons"][key]
        digest = hashlib.sha256(entry["index_style"].encode("utf-8")).hexdigest()
        assert digest in index["image_style_sha256"], f"{key}: image style is not an index entry"
        image = _param(icon.drawio_shape, "image")
        assert image and image.startswith("data:image/"), f"{key}: only embedded data: images are allowed"
        assert image == _param(entry["index_style"], "image")
        return
    assert shape in index["shapes"], f"{key}: shape {shape!r} is not in draw.io's index"
    res_icon = _param(icon.drawio_shape, "resIcon")
    if shape == "mxgraph.aws4.resourceIcon":
        assert res_icon in index["res_icons"], f"{key}: resIcon {res_icon!r} is not in draw.io's index"
    else:
        assert res_icon is None, f"{key}: resIcon only belongs on mxgraph.aws4.resourceIcon tiles"
    pr_icon = _param(icon.drawio_shape, "prIcon")
    if pr_icon:
        assert pr_icon in index["pr_icons"].get(shape, []), f"{key}: prIcon {pr_icon!r} unknown for {shape}"


def test_aws_resource_icons_are_standalone_shapes():
    # ALB/NLB/NAT/IGW/Parameter Store/Users are standalone stencils, not resourceIcon tiles (E10-S3).
    for key in ("aws:alb", "aws:nlb", "aws:nat", "aws:igw", "aws:parameter_store", "user", "users"):
        icon = ICONS[key]
        assert icon.drawio_shape.startswith("shape=mxgraph.aws4.") and "resourceIcon" not in icon.drawio_shape
        assert icon.stroke == "none" and not icon.tile
    for key in ("aws:ec2", "aws:eks", "aws:ecr", "aws:s3", "aws:route53", "aws:iam"):
        assert "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4." in ICONS[key].drawio_shape
        assert ICONS[key].stroke.upper() == "#FFFFFF" and ICONS[key].tile


def test_gcp_icons_share_one_colour_and_prefer_gcp3():
    gcp = {k: v for k, v in ICONS.items() if k.startswith("gcp:")}
    assert len(gcp) >= 10
    assert {v.color.upper() for v in gcp.values()} == {"#4285F4"}
    for key in ("gcp:gke", "gcp:cloud_run", "gcp:compute_engine", "gcp:cloud_sql", "gcp:cloud_storage", "gcp:bigquery"):
        assert gcp[key].drawio_shape.startswith("shape=mxgraph.gcp3."), key


def test_generated_xml_only_uses_indexed_shapes(index):
    """End to end: a diagram using every icon only emits shape names from the index."""
    keys = sorted(ICONS)
    nodes = [DiagramNode(id=f"n{i}", label=k, kind="service", icon=k) for i, k in enumerate(keys)]
    edges = [DiagramEdge(**{"from": f"n{i}", "to": f"n{i + 1}"}) for i in range(len(keys) - 1)]
    xml = generate_drawio_xml(DiagramSpec(type="architecture", title="all icons", nodes=nodes, edges=edges))
    for style in re.findall(r'style="([^"]*)"', xml):
        shape = _param(style, "shape")
        if shape and shape.startswith("mxgraph."):
            assert shape in index["shapes"], shape
        res = _param(style, "resIcon")
        if res:
            assert res in index["res_icons"], res


def test_unknown_key_falls_back_to_kind_shape():
    icon, label = resolve_icon("gcp:teleporter", "Thing", "process", "architecture")
    assert icon is None and label == "Thing"
