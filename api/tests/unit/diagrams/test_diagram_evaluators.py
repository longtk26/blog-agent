"""E10-S8: diagram_visual_quality and diagram_icons_resolved."""

import pytest

from src.modules.diagrams.domain.schemas.diagram_review import DiagramReview, ReviewIssue
from src.modules.evaluation.domain.diagram_evaluators import (
    eval_diagram_icons_resolved,
    eval_diagram_visual_quality,
)


def asset(slot="s1", review=None, png_path=None, icons=()):
    return {
        "slot_id": slot,
        "review": review,
        "png_path": png_path,
        "spec": {"title": "T", "type": "architecture",
                 "nodes": [{"id": f"n{i}", "label": f"N{i}", "icon": k} for i, k in enumerate(icons)]},
    }


def test_icons_resolved_counts_catalogue_hits():
    out = {"diagram_assets": [asset(icons=("aws:eks", "gcp:cloud_run", "k8s:pod", "aws:teleporter", None))]}
    res = eval_diagram_icons_resolved(inputs={}, outputs=out, reference={})
    assert res["score"] == 0.75 and "aws:teleporter" in res["comment"]
    assert eval_diagram_icons_resolved(inputs={}, outputs={}, reference={})["score"] == 1.0


async def test_visual_quality_uses_stored_reviews():
    out = {"diagram_assets": [
        asset("a", {"status": "passed", "major": 0, "minor": 0}),
        asset("b", {"status": "issues", "major": 1, "minor": 2}),
    ]}
    res = await eval_diagram_visual_quality(inputs={}, outputs=out, reference={})
    assert res["score"] == pytest.approx((1.0 + 0.65) / 2)


async def test_visual_quality_reviews_png_when_no_stored_review(tmp_path):
    png = tmp_path / "d.png"
    png.write_bytes(b"\x89PNG fake")

    class Model:
        calls = 0

        def with_structured_output(self, schema):
            return self

        async def ainvoke(self, messages, config=None):
            Model.calls += 1
            return DiagramReview(passed=False, issues=[ReviewIssue(check=2, severity="major", description="x")])

    out = {"diagram_assets": [asset("old", {"status": "disabled"}, str(png))]}
    res = await eval_diagram_visual_quality(inputs={}, outputs=out, reference={}, model=Model())
    assert Model.calls == 1 and res["score"] == 0.75 and "reviewed now" in res["comment"]


async def test_visual_quality_missing_diagram():
    expected = await eval_diagram_visual_quality(inputs={"include_diagram": "yes"}, outputs={}, reference={})
    assert expected["score"] == 0.0
    optional = await eval_diagram_visual_quality(inputs={}, outputs={}, reference={})
    assert optional["score"] is None
