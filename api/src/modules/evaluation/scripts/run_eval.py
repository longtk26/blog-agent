import argparse
import asyncio
import datetime
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
    ModelFactory,
    PageExtractor,
    TavilySearchProvider,
    WorkflowStore,
)
from src.modules.agent.infrastructure.adapters.token_usage_callback import TokenUsageCallbackHandler
from src.modules.agent.prompts.registry import PromptRegistry
from src.modules.articles.infrastructure.persistence import (
    DraftRepository,
    EvaluationRepository,
    RevisionRepository,
)
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
from src.modules.evaluation.domain.judge_evaluators import (
    judge_audience_depth_fit,
    judge_factual_support,
    judge_must_cover_coverage,
    judge_style_consistency,
)
from src.modules.evaluation.infrastructure.cached_search import CachedSearchProvider
from src.modules.research.infrastructure.persistence import (
    BriefRepository,
    ClaimRepository,
    SourceRepository,
)
from src.modules.shared.domain.entities import (
    ArticleFormat,
    PublicationTarget,
    TargetAudience,
    TaskBudgets,
    TaskMode,
    WritingTaskEntity,
)
from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository

logger = get_logger(__name__)


def get_git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


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
    git_sha = get_git_sha()
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    experiment_name = args.experiment or f"eval_{git_sha}_{timestamp}"

    prompt_versions = PromptRegistry.all_versions()
    prompt_hashes = PromptRegistry.all_hashes()

    models = {
        "planner": config.planner_model,
        "writer": config.writer_model,
        "judge": config.judge_model,
        "diagram": config.diagram_model,
    }

    metadata = {
        "git_sha": git_sha,
        "experiment": experiment_name,
        "prompt_versions": prompt_versions,
        "prompt_hashes": prompt_hashes,
        "models": models,
        "live_search": args.live_search,
    }

    evaluators = [
        eval_markdown_valid,
        eval_render_contract_violations,
        eval_citation_coverage,
        eval_source_quality_mix,
        eval_min_sources_met,
        eval_required_sections_present,
        eval_diagram_valid,
        eval_tool_error_rate,
        eval_cost_usd,
        eval_latency_s,
    ]

    if args.with_judges:
        evaluators.extend([
            judge_factual_support,
            judge_must_cover_coverage,
            judge_style_consistency,
            judge_audience_depth_fit,
        ])

    print("=" * 80)
    print(f"STARTING EVALUATION EXPERIMENT: {experiment_name}")
    print(f"Git SHA:         {git_sha}")
    print(f"Dataset:         {args.dataset}")
    print(f"Max Concurrency: {args.max_concurrency}")
    print(f"Search Mode:     {'LIVE' if args.live_search else 'CACHED'}")
    print(f"Evaluators:      {len(evaluators)} registered")
    print("=" * 80)

    # Setup search provider
    fallback_search = None
    if config.tavily_api_key:
        fallback_search = TavilySearchProvider(config)
    search_provider = CachedSearchProvider(
        fallback_provider=fallback_search,
        live=args.live_search,
        record=True,
    )

    broker = TaskEventBroker()
    store = WorkflowStore(broker)
    model_factory = ModelFactory(config)
    extractor = PageExtractor(config)

    deps = WorkflowDeps(
        store=store,
        models=model_factory,
        search=search_provider,
        extractor=extractor,
        settings=config,
    )

    # In eval mode: checkpointer can be in-memory MemorySaver
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_blog_graph(deps, MemorySaver())
    tracing = LangSmithTracing(config)

    async def predict(inputs: dict) -> dict:
        topic = inputs.get("topic") or "Evaluation Topic"
        mode_val = inputs.get("mode", "full")
        mode = TaskMode(mode_val) if mode_val in TaskMode._value2member_map_ else TaskMode.FULL
        fmt_val = inputs.get("format", "concept")
        fmt = ArticleFormat(fmt_val) if fmt_val in ArticleFormat._value2member_map_ else ArticleFormat.CONCEPT
        aud_val = inputs.get("audience")
        aud = TargetAudience(aud_val) if aud_val in TargetAudience._value2member_map_ else None

        task_entity = WritingTaskEntity(
            topic=topic,
            mode=mode,
            format=fmt,
            target_audience=aud,
            requirements=inputs.get("requirements"),
            must_cover=inputs.get("must_cover") or [],
            budgets=TaskBudgets(
                max_cost_usd=config.task_default_max_cost_usd,
                max_queries=inputs.get("max_queries", 6),
                max_sources=inputs.get("max_sources", 10),
            ),
        )

        task = await arun_in_session(lambda s: TaskRepository(s).create(task_entity))
        task_id = str(task.id)

        usage_cb = TokenUsageCallbackHandler(
            task_id=task.id,
            workflow_store=store,
            config=config,
            current_stage_resolver=lambda: "eval",
        )

        run_config = tracing.run_config(
            run_name="blog_task_eval",
            tags=["mode:eval", f"exp:{experiment_name}"],
            metadata={
                "task_id": task_id,
                "mode": mode.value,
                "format": fmt.value,
                "experiment": experiment_name,
                "git_sha": git_sha,
                **metadata,
            },
            configurable={"thread_id": task_id},
        )
        run_config.setdefault("callbacks", []).append(usage_cb)

        start_time = time.time()
        initial_state = {
            "task_id": task_id,
            "mode": mode.value,
            "eval_mode": True,
            "review_outline": False,
        }

        try:
            await graph.ainvoke(initial_state, config=run_config)
        except Exception as exc:
            logger.error(f"Error in graph execution for task {task_id}: {exc}")

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
            data=args.dataset,
            evaluators=evaluators,
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
                res = ev(inputs=ex["inputs"], outputs=out, reference=ex["reference"])
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
