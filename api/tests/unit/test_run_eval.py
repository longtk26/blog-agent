"""run_eval.py must import and wire evaluators the way LangSmith expects (it was broken at import before Epic 10)."""

import yaml
from pathlib import Path

import pytest
from langsmith.evaluation.evaluator import _normalize_evaluator_func

from src.configs.config import Config
from src.modules.evaluation.scripts import run_eval
from src.modules.shared.domain.entities import IncludeDiagram, TaskMode
from src.modules.shared.domain.entities.writing_task_entity import TaskDepth, TaskFormat

DATASET = Path(__file__).resolve().parents[2] / "evals" / "dataset.yaml"


def config() -> Config:
    return Config(_env_file=None, db_url="postgresql://u:p@localhost/db")


def test_every_dataset_example_builds_a_valid_task():
    for ex in yaml.safe_load(DATASET.read_text())["examples"]:
        task = run_eval.build_task_entity(ex["inputs"], config())
        assert task.topic == ex["inputs"]["topic"]
        assert task.mode == TaskMode.ARTICLE
        assert task.include_diagram == IncludeDiagram(ex["inputs"].get("include_diagram", "auto"))


def test_task_fields_map_from_inputs():
    task = run_eval.build_task_entity(
        {"topic": "T", "depth": "deep_dive", "format": "tutorial", "audience": "SREs", "diagram_format": "drawio",
         "include_diagram": "yes", "max_queries": 3},
        config(),
    )
    assert (task.depth, task.format, task.audience, task.diagram_format) == (TaskDepth.DEEP_DIVE, TaskFormat.TUTORIAL, "SREs", "drawio")
    assert task.budgets.max_queries == 3
    unknown = run_eval.build_task_entity({"topic": "T", "format": "poem", "mode": "full"}, config())
    assert unknown.format == TaskFormat.CONCEPT and unknown.mode == TaskMode.ARTICLE


@pytest.mark.parametrize("fn", run_eval.DETERMINISTIC_EVALUATORS + run_eval.JUDGE_EVALUATORS, ids=lambda f: f.__name__)
def test_wrapped_evaluators_pass_langsmith_signature_check(fn):
    _normalize_evaluator_func(run_eval.as_langsmith_evaluator(fn))  # raises ValueError for unsupported signatures


async def test_wrapper_runs_sync_and_async_evaluators():
    sync = run_eval.as_langsmith_evaluator(run_eval.eval_cost_usd)
    assert (await sync({}, {"cost_usd": 0.5}, {}))["score"] == 0.5
    visual = run_eval.as_langsmith_evaluator(run_eval.eval_diagram_visual_quality)
    out = {"diagram_assets": [{"slot_id": "s", "review": {"status": "passed", "major": 0, "minor": 0}, "spec": {}}]}
    assert (await visual({}, out, {}))["score"] == 1.0


def test_model_names_lists_configured_roles():
    from src.modules.agent.infrastructure.adapters.langchain_model_factory import LangChainModelFactory

    cfg = Config(_env_file=None, db_url="postgresql://u:p@localhost/db", llm_default_model="google_genai:gemini-x")
    assert run_eval.model_names(LangChainModelFactory(cfg))["vision"] == "google_genai:gemini-x"
