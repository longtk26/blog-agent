"""E10-S2/S7: diagrams are published from draw.io's render, reviewed, and repaired for at most N rounds."""

import uuid
from types import SimpleNamespace

import pytest

from src.modules.diagrams.domain.schemas.diagram_review import DiagramReview, ReviewIssue, review_score
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramEdge, DiagramNode, DiagramSpec
from src.modules.diagrams.infrastructure.adapters.diagram_renderer_adapter import RendererUnavailableException
from src.modules.diagrams.ports.output.diagram_renderer import RenderResult
from src.modules.diagrams.usecases.generate_diagram_usecase import GenerateDiagramUsecase, review_feedback

PNG = b"\x89PNG\r\n\x1a\nfake"


def spec(title: str) -> DiagramSpec:
    return DiagramSpec(
        type="architecture", title=title, direction="LR",
        nodes=[DiagramNode(id="a", label="API", kind="service", icon="aws:ec2"),
               DiagramNode(id="b", label="DB", kind="datastore", icon="aws:rds")],
        edges=[DiagramEdge(**{"from": "a", "to": "b", "label": "SQL"})],
    )


def review(*severities: str) -> DiagramReview:
    issues = [ReviewIssue(check=1, severity=s, description=f"{s} overlap", labels_involved=["API"]) for s in severities]
    return DiagramReview(passed=not any(s == "major" for s in severities), issues=issues)


class ScriptedModel:
    """with_structured_output(schema).ainvoke(...) returns the next scripted answer; records every call."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[tuple[list, dict]] = []

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages, config=None):
        self.calls.append((messages, config or {}))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class Models:
    def __init__(self, planner, vision):
        self.by_role = {"planner": planner, "vision": vision}

    def get(self, role):
        return self.by_role[str(role.value if hasattr(role, "value") else role)]


class Renderer:
    def __init__(self, fail: Exception | None = None):
        self.fail = fail
        self.drawio_calls: list[str] = []

    async def render_drawio(self, xml, embed_diagram=True):
        if self.fail:
            raise self.fail
        self.drawio_calls.append(xml)
        return RenderResult(svg=f'<svg content="x">{len(self.drawio_calls)}</svg>', png_bytes=PNG, sha256=f"sha{len(self.drawio_calls)}")

    async def render_mermaid(self, code):
        return RenderResult(svg="<svg>m</svg>", png_bytes=PNG, sha256="m")

    async def health(self):
        return True


class Repo:
    def __init__(self):
        self.created = []

    def create(self, asset):
        self.created.append(asset)
        return asset


def settings(tmp_path, review_on=True, rounds=2):
    return SimpleNamespace(data_dir=str(tmp_path), diagram_visual_review=review_on, diagram_review_max_rounds=rounds)


def task():
    return SimpleNamespace(id=uuid.uuid4(), topic="Topic", diagram_format="drawio")


async def run(uc):
    return await uc.execute(task=task(), slot_id="diagram_s1", section_heading="H", section_goal="G")


async def test_publishes_drawio_render_and_repairs_until_review_passes(tmp_path):
    planner = ScriptedModel([spec("first"), spec("second")])
    vision = ScriptedModel([review("major", "minor"), review("minor")])
    renderer, repo = Renderer(), Repo()
    uc = GenerateDiagramUsecase(Models(planner, vision), renderer, repo, settings(tmp_path))

    asset, snippet = await run(uc)

    assert len(renderer.drawio_calls) == 2                      # every round is rendered by draw.io
    assert asset.spec["title"] == "second" and asset.review_rounds == 2
    assert asset.review["status"] == "passed" and asset.review["major"] == 0 and asset.review["chosen_round"] == 1
    assert asset.sha256 == "sha2" and asset.validation_status == "valid"
    assert open(asset.svg_path).read().startswith("<svg") and open(asset.png_path, "rb").read() == PNG
    assert open(asset.source_path).read() == renderer.drawio_calls[1]
    assert snippet.strip().startswith(f"![second](asset://{asset.id}")
    # the second generation saw the first render's issues as feedback
    second_prompt = planner.calls[1][0][-1].content
    assert "major overlap" in second_prompt and "automated review" in second_prompt
    # the review got the PNG as an image
    image_part = vision.calls[0][0][-1].content[1]
    assert image_part["type"] == "image_url" and image_part["image_url"]["url"].startswith("data:image/png;base64,")


async def test_keeps_the_round_with_fewest_major_issues(tmp_path):
    planner = ScriptedModel([spec("r0"), spec("r1"), spec("r2")])
    vision = ScriptedModel([review("major", "major"), review("major"), review("major", "major", "major")])
    uc = GenerateDiagramUsecase(Models(planner, vision), Renderer(), Repo(), settings(tmp_path, rounds=2))

    asset, _ = await run(uc)

    assert len(planner.calls) == 3                              # 1 + max 2 repair rounds, never more
    assert asset.spec["title"] == "r1" and asset.review["major"] == 1 and asset.review_rounds == 3
    assert asset.validation_status == "warning" and asset.review["status"] == "issues"


async def test_review_disabled_means_one_generation_and_no_vision_call(tmp_path):
    planner = ScriptedModel([spec("only")])
    vision = ScriptedModel([])
    uc = GenerateDiagramUsecase(Models(planner, vision), Renderer(), Repo(), settings(tmp_path, review_on=False))

    asset, _ = await run(uc)

    assert vision.calls == [] and asset.review["status"] == "disabled" and asset.review_rounds == 1


async def test_review_model_failure_keeps_the_diagram(tmp_path):
    planner = ScriptedModel([spec("kept")])
    vision = ScriptedModel([RuntimeError("vision quota")])
    uc = GenerateDiagramUsecase(Models(planner, vision), Renderer(), Repo(), settings(tmp_path))

    asset, _ = await run(uc)

    assert asset.spec["title"] == "kept" and asset.review["status"] == "skipped" and asset.review_rounds == 1


async def test_renderer_down_fails_the_slot_instead_of_publishing_a_placeholder(tmp_path):
    planner = ScriptedModel([spec("x")])
    repo = Repo()
    uc = GenerateDiagramUsecase(
        Models(planner, ScriptedModel([])), Renderer(fail=RendererUnavailableException("down")), repo, settings(tmp_path)
    )
    with pytest.raises(RendererUnavailableException):
        await run(uc)
    assert repo.created == []


async def test_review_calls_carry_tracing_callbacks_and_metadata(tmp_path):
    planner = ScriptedModel([spec("t")])
    vision = ScriptedModel([review()])
    uc = GenerateDiagramUsecase(Models(planner, vision), Renderer(), Repo(), settings(tmp_path))
    marker = object()

    await uc.execute(task=task(), slot_id="diagram_s1", section_heading="H", section_goal="G", callbacks=[marker])

    config = vision.calls[0][1]
    assert config["run_name"] == "review_diagram" and config["callbacks"] == [marker]
    assert config["metadata"]["slot_id"] == "diagram_s1" and config["metadata"]["round"] == 0
    assert planner.calls[0][1]["callbacks"] == [marker]


def test_feedback_lists_vision_issues_and_lint_findings():
    from src.modules.diagrams.domain.layout_lint import LintFinding
    from src.modules.diagrams.usecases.generate_diagram_usecase import RenderedDiagram

    cand = RenderedDiagram(spec("f"), "drawio", "<mxfile/>", "<svg/>", PNG, "s",
                           lint=[LintFinding("edge_on_border", "edge e1 runs along the border of group vpc")],
                           review=review("major"))
    text = review_feedback(cand)
    assert "[major]" in text and "Any text overlapping" in text and "(API)" in text
    assert "[layout] edge e1 runs along the border of group vpc" in text
    assert cand.major == 2 and cand.minor == 0


def test_review_score_formula():
    assert review_score(0, 0) == 1.0
    assert review_score(1, 2) == pytest.approx(0.65)
    assert review_score(5, 0) == 0.0
