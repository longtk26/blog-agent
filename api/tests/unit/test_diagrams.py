"""Unit tests for DiagramSpec, validation, layout, draw.io XML and Mermaid generators (Epic 7)."""

from pathlib import Path
import pytest

from src.modules.diagrams.domain.diagram_builder import build_diagram
from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.geometry import Rect, build_geometry
from src.modules.diagrams.domain.mermaid_generator import (
    choose_diagram_format,
    generate_mermaid,
)
from src.modules.diagrams.domain.schemas.diagram_spec import (
    DiagramEdge,
    DiagramGroup,
    DiagramMessage,
    DiagramNode,
    DiagramParticipant,
    DiagramSpec,
)
from src.modules.diagrams.domain.spec_validator import validate_spec
from src.modules.diagrams.domain.svg_sanitizer import sanitize_svg_content


def test_spec_validation_success():
    spec = DiagramSpec(
        type="architecture",
        title="Sample Architecture",
        direction="LR",
        groups=[DiagramGroup(id="g1", label="Data Tier")],
        nodes=[
            DiagramNode(id="n1", label="API Gateway", kind="service"),
            DiagramNode(id="n2", label="Database", kind="datastore", group="g1"),
        ],
        edges=[
            DiagramEdge(from_node="n1", to_node="n2", label="reads/writes"),
        ],
    )
    errors = validate_spec(spec)
    assert errors == []


def test_spec_validation_errors():
    # Orphan node, missing group, invalid edge target
    spec = DiagramSpec(
        type="flowchart",
        nodes=[
            DiagramNode(id="n1", label="Process 1", kind="process", group="non_existent"),
            DiagramNode(id="n2", label="Orphan Process", kind="process"),
            DiagramNode(id="0", label="Reserved ID Node", kind="process"),
        ],
        edges=[
            DiagramEdge(from_node="n1", to_node="missing_target"),
        ],
    )
    errors = validate_spec(spec)
    assert any("reserved" in e for e in errors)
    assert any("non-existent group" in e for e in errors)
    assert any("missing_target" in e for e in errors)
    assert any("Orphan node" in e for e in errors)


def test_spec_validation_empty_nodes():
    spec = DiagramSpec(type="flowchart", nodes=[], edges=[])
    errors = validate_spec(spec)
    assert any("at least one node" in e for e in errors)


def test_spec_validation_group_cycle():
    spec = DiagramSpec(
        type="flowchart",
        groups=[
            DiagramGroup(id="g1", label="G1", parent="g2"),
            DiagramGroup(id="g2", label="G2", parent="g1"),
        ],
        nodes=[
            DiagramNode(id="n1", label="Node 1", kind="process", group="g1"),
            DiagramNode(id="n2", label="Node 2", kind="process", group="g2"),
        ],
        edges=[DiagramEdge(from_node="n1", to_node="n2")],
    )
    errors = validate_spec(spec)
    assert any("cycle" in e for e in errors)


def test_spec_validation_sequence():
    spec = DiagramSpec(
        type="sequence",
        participants=[
            DiagramParticipant(id="u", label="User", actor=True),
            DiagramParticipant(id="s", label="Server"),
        ],
        messages=[
            DiagramMessage(from_node="u", to_node="s", label="POST /login"),
            DiagramMessage(from_node="s", to_node="u", label="200 OK", return_msg=True),
            DiagramMessage(from_node="u", to_node="unknown", label="invalid"),
        ],
    )
    errors = validate_spec(spec)
    assert len(errors) == 1
    assert "unknown" in errors[0]


def test_deterministic_layout():
    spec = DiagramSpec(
        type="flowchart",
        direction="LR",
        nodes=[
            DiagramNode(id="a", label="Start", kind="process"),
            DiagramNode(id="b", label="End", kind="process"),
        ],
        edges=[DiagramEdge(from_node="a", to_node="b")],
    )
    first, second = build_geometry(spec), build_geometry(spec)
    assert first.nodes["a"].body == second.nodes["a"].body
    assert first.edges[0].points == second.edges[0].points
    assert first.nodes["a"].body.x2 < first.nodes["b"].body.x
    assert build_diagram(spec).drawio_xml == build_diagram(spec).drawio_xml


def test_drawio_xml_generation_and_roundtrip():
    spec = DiagramSpec(
        type="architecture",
        title="Microservice Architecture",
        direction="LR",
        groups=[DiagramGroup(id="grp_backend", label="Backend Services")],
        nodes=[
            DiagramNode(id="client", label="Web Client", kind="actor"),
            DiagramNode(id="api", label="API Gateway", kind="service", group="grp_backend"),
            DiagramNode(id="db", label="Postgres DB", kind="datastore", group="grp_backend"),
        ],
        edges=[
            DiagramEdge(from_node="client", to_node="api", label="HTTP"),
            DiagramEdge(from_node="api", to_node="db", label="SQL"),
        ],
    )
    xml = generate_drawio_xml(spec)
    assert "<mxfile" in xml
    assert 'id="client"' in xml
    assert 'id="grp_backend"' in xml

    res = validate_drawio_xml(xml, spec)
    assert res.is_valid, f"Validation errors: {res.errors}"
    assert res.parsed_nodes == {"client", "api", "db"}
    assert res.parsed_edges == {("client", "api"), ("api", "db")}


def test_mermaid_generation():
    spec = DiagramSpec(
        type="flowchart",
        direction="TB",
        groups=[DiagramGroup(id="stage1", label="Data Prep")],
        nodes=[
            DiagramNode(id="raw", label="1. Raw Data\nPast papers", kind="datastore", group="stage1"),
            DiagramNode(id="sft", label="2. SFT Model\nInstruct model", kind="process", group="stage1"),
            DiagramNode(id="deploy", label="3. Ollama", kind="service"),
        ],
        edges=[
            DiagramEdge(from_node="raw", to_node="sft"),
            DiagramEdge(from_node="sft", to_node="deploy", label="export"),
        ],
    )
    mmd = generate_mermaid(spec)
    assert "flowchart TD" in mmd
    assert "subgraph stage1" in mmd
    assert 'raw[("<b>1. Raw Data</b><br/>Past papers")]' in mmd
    assert "style raw fill:#15803d" in mmd
    assert "style sft fill:#0369a1" in mmd
    assert "style deploy fill:#4338ca" in mmd


def test_choose_diagram_format():
    simple_spec = DiagramSpec(
        nodes=[DiagramNode(id=f"n{i}", label=f"N{i}") for i in range(5)],
        edges=[DiagramEdge(from_node="n0", to_node=f"n{i}") for i in range(1, 5)],
    )
    assert choose_diagram_format(simple_spec, "auto") == "mermaid"

    complex_spec = DiagramSpec(
        nodes=[DiagramNode(id=f"n{i}", label=f"N{i}") for i in range(15)],
        edges=[DiagramEdge(from_node="n0", to_node=f"n{i}") for i in range(1, 15)],
    )
    assert choose_diagram_format(complex_spec, "auto") == "drawio"
    assert choose_diagram_format(complex_spec, "mermaid") == "mermaid"

    aws_spec = DiagramSpec(
        title="AWS VPC Architecture",
        nodes=[
            DiagramNode(id="ec2", label="EC2 Instance"),
            DiagramNode(id="s3", label="S3 Bucket"),
        ],
        edges=[DiagramEdge(from_node="ec2", to_node="s3")],
    )
    assert choose_diagram_format(aws_spec, "auto") == "drawio"


def test_svg_sanitizer():
    dirty_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<script>alert("xss")</script>'
        '<rect x="0" y="0" width="10" height="10" onclick="evil()" />'
        '<a href="javascript:alert(1)"><circle r="5" /></a>'
        '<a href="https://malicious.site"><path d="M0 0" /></a>'
        '</svg>'
    )
    clean = sanitize_svg_content(dirty_svg)
    assert "<script" not in clean
    assert "onclick" not in clean
    assert "javascript:" not in clean
    assert "https://malicious.site" not in clean
    assert 'href="#"' in clean or 'href=""' in clean


@pytest.mark.asyncio
async def test_diagram_asset_usecases(tmp_path, monkeypatch):
    import uuid
    from unittest.mock import AsyncMock, MagicMock
    from src.configs.config import config
    from src.modules.diagrams.ports.output.diagram_renderer import RenderResult
    from src.modules.diagrams.usecases.diagram_asset_usecases import DiagramAssetUsecases
    from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity

    monkeypatch.setattr(config, "data_dir", str(tmp_path))

    class InMemoryRepo:
        def __init__(self):
            self.items = {}

        def create(self, a):
            self.items[a.id] = a
            return a

        def get(self, aid):
            return self.items.get(aid)

        def get_by_slot(self, tid, slot):
            for a in self.items.values():
                if a.task_id == tid and a.slot_id == slot:
                    return a
            return None

        def list_by_task(self, tid):
            return [a for a in self.items.values() if a.task_id == tid]

        def update(self, a):
            self.items[a.id] = a
            return a

    repo = InMemoryRepo()
    task_repo = MagicMock()
    renderer = MagicMock()
    renderer.render_mermaid = AsyncMock(return_value=RenderResult(svg="<svg>mermaid</svg>", png_bytes=b"png", sha256="abc"))
    renderer.render_drawio = AsyncMock(return_value=RenderResult(svg="<svg>drawio</svg>", png_bytes=b"png", sha256="def"))

    usecases = DiagramAssetUsecases(repo, task_repo, renderer)

    task_id = uuid.uuid4()
    spec = DiagramSpec(
        nodes=[DiagramNode(id="n1", label="Node 1"), DiagramNode(id="n2", label="Node 2")],
        edges=[DiagramEdge(from_node="n1", to_node="n2")],
    )
    asset = DiagramAssetEntity(
        task_id=task_id,
        slot_id="diagram_sec1",
        format="drawio",
        spec=spec.model_dump(),
        source_path=str(tmp_path / "diagram_sec1.drawio"),
        svg_path=str(tmp_path / "diagram_sec1.svg"),
    )
    repo.create(asset)

    # 1. List
    assert len(usecases.list_diagrams(task_id)) == 1

    # 2. Switch to mermaid
    updated = await usecases.switch_format(task_id, "diagram_sec1", "mermaid")
    assert updated.format == "mermaid"
    assert updated.source_path.endswith(".mmd")
    assert renderer.render_mermaid.called

    # 3. Replace by upload .svg
    svg_upload = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'.encode("utf-8")
    replaced = await usecases.replace_by_upload(task_id, "diagram_sec1", svg_upload, "diagram.svg")
    assert replaced.sha256 != ""
    assert Path(replaced.svg_path).is_file()

