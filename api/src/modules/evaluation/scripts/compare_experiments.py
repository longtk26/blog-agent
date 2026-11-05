import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[4]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

RESULTS_DIR = API_ROOT / "evals" / "results"

# Lower is better metrics
LOWER_IS_BETTER = {
    "render_contract_violations",
    "tool_error_rate",
    "cost_usd",
    "latency_s",
}

# Per-metric regression tolerance thresholds
DEFAULT_THRESHOLDS = {
    "markdown_valid": 0.0,            # 0 tolerance for markdown validity drop
    "render_contract_violations": 0.0, # 0 tolerance for new contract violations
    "citation_coverage": 0.08,        # allow up to 8% fluctuation
    "source_quality_mix": 0.10,
    "min_sources_met": 0.05,
    "required_sections_present": 0.05,
    "diagram_valid": 0.05,
    "diagram_visual_quality": 0.10,   # E10-S8: 0.10 = two minor issues or less than half a major one
    "diagram_icons_resolved": 0.05,
    "tool_error_rate": 0.05,
    "cost_usd": 0.50,                 # $0.50 cost increase threshold
    "latency_s": 15.0,                # 15s latency regression threshold
    "factual_support": 0.3,           # on 1-5 scale
    "must_cover_coverage": 0.3,
    "style_consistency": 0.3,
    "audience_depth_fit": 0.3,
}


def load_experiment_metrics(name: str) -> dict:
    file_path = RESULTS_DIR / f"{name}.json"
    if file_path.exists():
        data = json.loads(file_path.read_text(encoding="utf-8"))
        return data.get("metrics", {})

    # Try matching without exact extension or looking in LangSmith
    matches = list(RESULTS_DIR.glob(f"*{name}*.json"))
    if matches:
        data = json.loads(matches[0].read_text(encoding="utf-8"))
        return data.get("metrics", {})

    # Fallback to querying LangSmith if client is available
    try:
        from langsmith import Client
        from src.configs.config import load_config

        config = load_config()
        if config.langsmith_api_key:
            client = Client()
            projects = list(client.list_projects(reference_dataset_name="blog-agent-eval"))
            for p in projects:
                if name in (p.name or ""):
                    runs = list(client.list_runs(project_id=p.id))
                    # Summarize scores
                    scores: dict[str, list[float]] = {}
                    for r in runs:
                        for fb in client.list_feedback(run_ids=[r.id]):
                            if fb.score is not None:
                                scores.setdefault(fb.key, []).append(float(fb.score))
                    if scores:
                        return {k: round(sum(v) / len(v), 4) for k, v in scores.items() if v}
    except Exception as exc:
        print(f"Warning: could not query LangSmith for experiment {name}: {exc}", file=sys.stderr)

    raise FileNotFoundError(f"Experiment results not found for '{name}' in {RESULTS_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Compare two eval experiments and detect regressions")
    parser.add_argument("--base", "-b", type=str, required=True, help="Baseline experiment name")
    parser.add_argument("--new", "-n", type=str, required=True, help="New experiment name")
    parser.add_argument("--threshold", "-t", type=float, default=None, help="Global regression threshold override")
    args = parser.parse_args()

    base_metrics = load_experiment_metrics(args.base)
    new_metrics = load_experiment_metrics(args.new)

    all_keys = sorted(set(base_metrics.keys()) | set(new_metrics.keys()))
    if not all_keys:
        print("No metrics found in either experiment.", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print(f"EXPERIMENT COMPARISON: BASE ({args.base}) vs NEW ({args.new})")
    print("=" * 80)
    print(f"{'Metric':<30} {'Base':>8} {'New':>8} {'Delta':>8}  {'Status':<10}")
    print("-" * 80)

    regressions = []
    for key in all_keys:
        b_val = base_metrics.get(key)
        n_val = new_metrics.get(key)

        if b_val is None or n_val is None:
            b_str = f"{b_val:.2f}" if b_val is not None else "N/A"
            n_str = f"{n_val:.2f}" if n_val is not None else "N/A"
            print(f"{key:<30} {b_str:>8} {n_str:>8} {'N/A':>8}  {'SKIP':<10}")
            continue

        delta = n_val - b_val
        delta_str = f"{delta:+.2f}"
        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLDS.get(key, 0.05)

        is_regression = False
        if key in LOWER_IS_BETTER:
            # For lower-is-better, an increase greater than threshold is a regression
            if delta > threshold:
                is_regression = True
        else:
            # For higher-is-better, a drop greater than threshold is a regression
            if delta < -threshold:
                is_regression = True

        if is_regression:
            status = "REGRESSION"
            regressions.append((key, b_val, n_val, delta, threshold))
        else:
            status = "PASS"

        print(f"{key:<30} {b_val:>8.2f} {n_val:>8.2f} {delta_str:>8}  {status:<10}")

    print("=" * 80)

    if regressions:
        print(f"FAILED: {len(regressions)} regression(s) detected:")
        for key, b_val, n_val, delta, th in regressions:
            print(f"  - {key}: {b_val:.2f} -> {n_val:.2f} (delta: {delta:+.2f}, threshold: {th})")
        sys.exit(1)
    else:
        print("SUCCESS: All metric deltas within acceptable thresholds. No regressions.")
        sys.exit(0)


if __name__ == "__main__":
    main()
