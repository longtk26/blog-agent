import argparse
import asyncio
import datetime
import inspect
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

# Ensure api/ root is on sys.path
API_ROOT = Path(__file__).resolve().parents[4]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from langsmith import Client
from langsmith.evaluation import aevaluate

from src.configs.config import Config, load_config
from src.configs.logger import get_logger
from src.libs.database import arun_in_session
from src.libs.events import TaskEventBroker
from src.modules.agent.graph.blog_graph import build_blog_graph
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.infrastructure.adapters import (
    LangSmithTracing,
    WorkflowStore,
    disable_env_tracing,
    get_model_factory,
)
from src.modules.agent.infrastructure.adapters.token_usage_callback import TokenUsageCallbackHandler
from src.modules.agent.nodes.base import workflow_callbacks_ctx
from src.modules.agent.prompts.registry import get_prompt_registry
from src.modules.articles.infrastructure.persistence import RevisionRepository
from src.modules.evaluation.domain.deterministic_evaluators import (
    eval_citation_coverage,
    eval_cost_usd,
    eval_diagram_valid,
    eval_latency_s,
    eval_markdown_valid,
    eval_min_sources_met,
    eval_render_contract_violations,
    eval_required_sections_present,
    eval_source_quality_mix,
    eval_tool_error_rate,
)
from src.modules.evaluation.domain.diagram_evaluators import (
    eval_diagram_icons_resolved,
    eval_diagram_visual_quality,
)
from src.modules.evaluation.domain.judge_evaluators import (
    eval_audience_depth_fit,
    eval_factual_support,
    eval_must_cover_coverage,
    eval_style_consistency,
)
from src.modules.evaluation.infrastructure.cached_search import CachedSearchProvider
from src.modules.research.infrastructure.persistence import BriefRepository, SourceRepository
from src.modules.shared.domain.entities import (
    IncludeDiagram,
    TaskBudgets,
    TaskMode,
    WritingTaskEntity,
)
from src.modules.shared.domain.entities.writing_task_entity import TaskDepth, TaskFormat
from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository

logger = get_logger(__name__)

DETERMINISTIC_EVALUATORS = [
    eval_markdown_valid,
    eval_render_contract_violations,
    eval_citation_coverage,
    eval_source_quality_mix,
    eval_min_sources_met,
    eval_required_sections_present,
    eval_diagram_valid,
    eval_diagram_icons_resolved,   # E10-S8
    eval_diagram_visual_quality,   # E10-S8: stored review, or the same reviewer run on the PNG
    eval_tool_error_rate,
    eval_cost_usd,
    eval_latency_s,
]
JUDGE_EVALUATORS = [eval_factual_support, eval_must_cover_coverage, eval_style_consistency, eval_audience_depth_fit]


def get_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _enum(enum_cls, value, default):
    return enum_cls(value) if value in enum_cls._value2member_map_ else default


def build_task_entity(inputs: dict, config: Config) -> WritingTaskEntity:
    """A writing task from a dataset example's inputs (same fields as the dashboard's task form)."""
    return WritingTaskEntity(
        topic=inputs.get("topic") or "Evaluation Topic",
        mode=_enum(TaskMode, inputs.get("mode"), TaskMode.ARTICLE),
        audience=inputs.get("audience"),
        depth=_enum(TaskDepth, inputs.get("depth"), TaskDepth.INTERMEDIATE),
        format=_enum(TaskFormat, inputs.get("format"), TaskFormat.CONCEPT),
        requirements=inputs.get("requirements"),
        include_diagram=_enum(IncludeDiagram, inputs.get("include_diagram"), IncludeDiagram.AUTO),
        diagram_format=inputs.get("diagram_format", "auto"),   # E10-S8 diagram cases pin draw.io
        budgets=TaskBudgets(
            max_cost_usd=config.task_default_max_cost_usd,
            max_queries=inputs.get("max_queries", 6),
            max_sources=inputs.get("max_sources", 10),
        ),
    )


def as_langsmith_evaluator(fn):
    """Adapt an evaluator written as fn(*args, inputs=, outputs=, reference=) to LangSmith's named-argument form.

    LangSmith 0.14 rejects `*args` signatures; this also awaits the async (LLM) evaluators.
    """

    async def evaluator(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
        return await run_evaluator(fn, inputs, outputs, reference_outputs)

    evaluator.__name__ = fn.__name__
    return evaluator


async def run_evaluator(fn, inputs: dict, outputs: dict, reference: dict) -> dict:
    result = fn(inputs=inputs, outputs=outputs or {}, reference=reference or {})
    return await result if inspect.isawaitable(result) else result


def model_names(models) -> dict[str, str]:
    names = {}
    for role in ("planner", "writer", "fast", "judge", "vision"):
        try:
            spec = models.spec(role)
            if spec.model:
                names[role] = spec.model
        except Exception:
            pass
    return names


async def run_offline_eval():
    parser = argparse.ArgumentParser(description="Run offline evaluation experiment on LangSmith dataset")
    parser.add_argument("--experiment", "-e", type=str, default=None, help="Name of experiment")
    parser.add_argument("--dataset", "-d", type=str, default="blog-agent-eval", help="LangSmith dataset name")
    parser.add_argument("--max-concurrency", "-c", type=int, default=2, help="Max parallel task runs")
    parser.add_argument("--live-search", action="store_true", help="Perform live web search instead of cached search")
    parser.add_argument("--with-judges", action="store_true", help="Include LLM-as-judge evaluators")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of dataset examples to evaluate")
    args = parser.parse_args()

    config = load_config()
    config.export_provider_env()     # same start-up as the API (src/main.py)
    disable_env_tracing()
    git_sha = get_git_sha()
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    experiment_name = args.experiment or f"eval_{git_sha}_{timestamp}"

    registry = get_prompt_registry()
    model_factory = get_model_factory()
    metadata = {
        "git_sha": git_sha,
        "experiment": experiment_name,
        "prompt_versions": registry.all_versions(),
        "prompt_hashes": registry.all_hashes(),
        "models": model_names(model_factory),
        "live_search": args.live_search,
    }

    evaluators = list(DETERMINISTIC_EVALUATORS)
    if args.with_judges:
        evaluators.extend(JUDGE_EVALUATORS)

    print("=" * 80)
    print(f"STARTING EVALUATION EXPERIMENT: {experiment_name}")
    print(f"Git SHA:         {git_sha}")
    print(f"Dataset:         {args.dataset}")
    print(f"Max Concurrency: {args.max_concurrency}")
    print(f"Search Mode:     {'LIVE' if args.live_search else 'CACHED'}")
    print(f"Evaluators:      {len(evaluators)} registered")
    print("=" * 80)

    # Same adapters as the API (src/main.py); search goes through the replayable cache.
    from src.modules.diagrams.infrastructure.adapters.diagram_renderer_adapter import DiagramRendererAdapter
    from src.modules.research.infrastructure.adapters import get_page_extractor, get_search_provider
    from src.modules.styles.infrastructure.adapters import PgVectorStore, get_embedding_service

    search_provider = CachedSearchProvider(fallback_provider=get_search_provider(), live=args.live_search, record=True)
    store = WorkflowStore(TaskEventBroker())
    deps = WorkflowDeps(
        store=store,
        models=model_factory,
        search=search_provider,
        extractor=get_page_extractor(),
        settings=config,
        vector_store=PgVectorStore(),
        embeddings=get_embedding_service(),
        renderer=DiagramRendererAdapter(),
    )

    # In eval mode the checkpointer can be in memory: eval runs never pause for review.
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_blog_graph(deps, MemorySaver())
    tracing = LangSmithTracing(config)

    async def predict(inputs: dict) -> dict:
        task_entity = build_task_entity(inputs, config)
        task = await arun_in_session(lambda s: TaskRepository(s).create(task_entity))
        task_id = str(task.id)

        run_config = tracing.run_config(
            run_name="blog_task_eval",
            tags=["mode:eval", f"exp:{experiment_name}"],
            metadata={
                "task_id": task_id,
                "mode": str(task.mode),
                "format": str(task.format),
                **metadata,
            },
            callbacks=[TokenUsageCallbackHandler(task.id, store, config)],
            configurable={"thread_id": task_id},
        )

        start_time = time.time()
        initial_state = {"task_id": task_id, "mode": str(task.mode), "eval_mode": True, "review_outline": False}

        # Like LangGraphWorkflowRunner._run: callbacks visible to nodes, custom events recorded as task events.
        cb_token = workflow_callbacks_ctx.set(run_config.get("callbacks", []))
        try:
            async for mode, chunk in graph.astream(initial_state, run_config, stream_mode=["updates", "custom"]):
                if mode == "custom" and isinstance(chunk, dict) and chunk.get("type"):
                    payload = json.loads(json.dumps({k: v for k, v in chunk.items() if k != "type"}, default=str))
                    await store.record_event(task.id, chunk["type"], payload)
        except Exception as exc:
            logger.error(f"Error in graph execution for task {task_id}: {exc}")
        finally:
            workflow_callbacks_ctx.reset(cb_token)

        duration = time.time() - start_time

        # Flush usage callbacks
        for cb in run_config.get("callbacks", []):
            if hasattr(cb, "wait_for_futures"):
                cb.wait_for_futures()

        # Load final state entities from DB
        revision = await arun_in_session(lambda s: RevisionRepository(s).latest(task.id))
        sources = await arun_in_session(lambda s: SourceRepository(s).list_by_task(task.id))
        brief = await arun_in_session(lambda s: BriefRepository(s).get_by_task(task.id))
        events = await arun_in_session(lambda s: TaskEventRepository(s).list_after(task.id, 0, 1000))
        cost_usd = await store.get_task_cost(task.id)
        diagram_assets = await store.list_diagram_assets(task.id)

        tool_errors = len([e for e in events if e.event_type in ("search_error", "extract_error", "tool_error")])

        return {
            "markdown": revision.markdown if revision else "",
            "metadata": {
                "title": revision.title if revision else task.topic,
                "slug": revision.slug if revision else "",
                "description": revision.description if revision else "",
                "tags": revision.tags if revision else [],
            },
            "claim_map": revision.claim_map if revision else [],
            "diagrams": revision.diagrams if revision else [],
            "diagram_assets": [a.model_dump(mode="json") for a in diagram_assets],
            "sources": [s.model_dump(mode="json") for s in sources],
            "brief": brief.model_dump(mode="json") if brief else {},
            "tool_errors": tool_errors,
            "cost_usd": cost_usd,
            "latency_s": duration,
        }

    # Run evaluation via LangSmith aevaluate
    results_dir = API_ROOT / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    client = Client() if config.langsmith_api_key else None

    # Load dataset examples
    if client and config.langsmith_api_key:
        print(f"Running LangSmith aevaluate on dataset '{args.dataset}'...")
        eval_results = await aevaluate(
            predict,
            data=client.list_examples(dataset_name=args.dataset, limit=args.limit) if args.limit else args.dataset,
            evaluators=[as_langsmith_evaluator(ev) for ev in evaluators],
            experiment_prefix=experiment_name,
            metadata=metadata,
            max_concurrency=args.max_concurrency,
            client=client,
        )
    else:
        print("LangSmith API key not configured or offline; evaluating against local dataset.yaml...")
        import yaml
        dataset_file = API_ROOT / "evals" / "dataset.yaml"
        with open(dataset_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        examples = raw.get("examples", [])
        if args.limit:
            examples = examples[: args.limit]

        scores: dict[str, list[float]] = {}
        for ex in examples:
            print(f"Evaluating {ex['id']}...")
            out = await predict(ex["inputs"])
            for ev in evaluators:
                res = await run_evaluator(ev, ex["inputs"], out, ex["reference"])
                key = res["key"]
                score = res.get("score")
                if score is not None:
                    scores.setdefault(key, []).append(float(score))

        summary_metrics = {k: round(sum(v) / len(v), 4) for k, v in scores.items() if v}
        saved_payload = {
            "experiment": experiment_name,
            "git_sha": git_sha,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metadata": metadata,
            "metrics": summary_metrics,
        }
        out_file = results_dir / f"{experiment_name}.json"
        out_file.write_text(json.dumps(saved_payload, indent=2), encoding="utf-8")
        print(f"Results saved to {out_file}")
        print("\nSummary Metrics:")
        for k, v in summary_metrics.items():
            print(f"  {k:28s}: {v}")
        return

    # If run via aevaluate on LangSmith, save results summary
    metrics_summary: dict[str, float] = {}
    async for result in eval_results:
        for res in result.get("evaluation_results", {}).get("results", []):
            if res.score is not None:
                metrics_summary.setdefault(res.key, []).append(float(res.score))

    aggregated = {k: round(sum(v) / len(v), 4) for k, v in metrics_summary.items() if v}
    saved_payload = {
        "experiment": experiment_name,
        "git_sha": git_sha,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "metadata": metadata,
        "metrics": aggregated,
    }
    out_file = results_dir / f"{experiment_name}.json"
    out_file.write_text(json.dumps(saved_payload, indent=2), encoding="utf-8")
    print(f"\nExperiment complete. Saved summary to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_offline_eval())
