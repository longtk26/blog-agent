# Epic 9 — Evaluation & Observability

| | |
|---|---|
| **Milestone** | M5. Tracing already exists from Epic 1. This epic can start in parallel once Epic 3 is done. |
| **Depends on** | Epics 1–3; benefits from 4 (human feedback) and 6 (style profile) |
| **Status** | Draft for review |

## Goal

Measure output quality and cost, and catch regressions when prompts, models or workflow steps change:

- **LangSmith** for traces, datasets, experiments and feedback
- a small, representative **evaluation dataset**
- **deterministic and LLM-as-judge evaluators**
- **cost/latency budgets** visible in the dashboard

## Context
- The brief (§11) defines the criteria: citation coverage, factual support, style consistency, Markdown validity, diagram validity, tool errors, latency and cost.
- Epic 3 validators and the judge already exist. They are reused here as evaluators, not re-implemented.
- Topics should reflect what the owner actually writes, including the empty placeholder folders `blogs/monitoring/` and `blogs/subtitle-to-audio/`.

## In scope
- Trace hygiene.
- Usage/cost capture and budgets.
- Datasets and evaluators.
- Offline eval runner.
- Online feedback from review actions.
- Prompt versioning.
- Ops view in the UI.

## Out of scope
- Production alerting/paging (this is a local tool).
- Automated prompt optimisation.

---

## Stories

### E9-S1 — Trace hygiene & naming
**As** the owner, **I want** traces that are easy to navigate and free of secrets, **so that** debugging a bad article takes minutes.

**Acceptance criteria**
- [ ] Every node has a stable `run_name` (`plan_research`, `assess_source`, `draft_section:<heading>` …). Tools have descriptive names.
- [ ] Each root run carries this metadata: `task_id`, `mode`, `format`, `revision_number`, `graph_version`, `prompt_versions{}`, `style_profile_version`, and `models{role: id}`.
- [ ] Page text sent to the LLM is truncated in traces, configurable through `TRACE_MAX_DOC_CHARS`.
- [ ] A secrets test (extending E1-S5) runs a full mocked task and scans all trace payloads for configured secret values.
- [ ] A saved LangSmith filter or view per task is documented in the README.

**Size:** 2

---

### E9-S2 — Token, cost & latency tracking with budgets
**As** the owner, **I want** to see what each task cost and how long each step took, **so that** I can choose models wisely and avoid surprise bills.

**Acceptance criteria**
- [ ] A callback handler collects `usage_metadata` (input, output and cached tokens) and latency per LLM call, tagged by node and model. The data is stored in `run_usage`.
- [ ] A price table in config (per model, per 1M tokens) is used to compute an estimated cost, labelled as an estimate.
- [ ] Budget enforcement: a `max_cost_usd` per task (default configurable, e.g. $2). When 80% is reached a warning event is emitted. At 100%, the graph stops at the next node boundary and moves to `failed` (`budget_exceeded`, resumable after the budget is raised).
- [ ] The task detail page shows a cost/latency breakdown by stage. The Tasks list shows the total cost per task.

**Size:** 3

---

### E9-S3 — Evaluation dataset
**As** the owner, **I want** a small, stable set of representative topics with expectations, **so that** I can compare versions of the agent objectively.

**Acceptance criteria**
- [ ] `api/evals/dataset.yaml` contains 10–15 examples. Each one has `inputs` (a task request) and `reference` fields:
  - `must_cover[]`
  - `expected_source_types[]`
  - `min_sources`
  - `format`
  - `expected_sections[]`
  - `diagram_expected`
  - `known_facts[]` (short verifiable statements)
- [ ] The topics mix concept and tutorial formats and difficulty levels. Examples: LoRA fine-tuning, RAG vs fine-tuning, the LLM inference lifecycle, Prometheus/Grafana monitoring basics, subtitle-to-audio TTS pipeline, vector databases, a Kubernetes concept, FastAPI dependency injection.
- [ ] A sync script (`make eval-sync`) upserts the YAML into a LangSmith dataset (`blog-agent-eval`) through the `langsmith` client. The YAML in git stays the source of truth.

**Size:** 2

---

### E9-S4 — Evaluators
**As** a developer, **I want** reusable evaluators for each quality criterion, **so that** experiments produce comparable scores.

**Acceptance criteria**
- [ ] **Deterministic evaluators**, which wrap the Epic 3 validators:
  - `markdown_valid` (0/1)
  - `render_contract_violations` (count)
  - `citation_coverage` (% of claim-map sentences that have a source)
  - `source_quality_mix` (% from official docs, papers or repos)
  - `min_sources_met`
  - `required_sections_present`
  - `diagram_valid`, when expected
  - `tool_error_rate`
  - `cost_usd`
  - `latency_s`
- [ ] **LLM-as-judge evaluators**, using a separate judge prompt from the in-workflow judge to avoid self-grading bias where possible:
  - `factual_support` (checked against `known_facts` and the claim quotes)
  - `must_cover_coverage`
  - `style_consistency` (against the active style profile and the samples)
  - `audience_depth_fit`
  - Each one returns a score and a reasoning comment.
- [ ] A **pairwise evaluator** compares two experiments' drafts for the same input ("which better matches the owner's style and the request?"). It is used when prompts change.
- [ ] Each evaluator has unit tests on fixed fixtures.

**Size:** 5

---

### E9-S5 — Offline evaluation runner & regression gate
**As** a developer, **I want** one command that runs the agent on the dataset and compares it with a baseline, **so that** I know whether a change made things better or worse.

**Acceptance criteria**
- [ ] `make eval EXPERIMENT=<name>` runs the graph in an **eval mode**: research plus draft, no interrupts, publishing disabled at the port level. It runs over the dataset with `langsmith` `aevaluate(...)` and bounded concurrency.
- [ ] Results appear as a LangSmith experiment, with metadata for the git SHA, prompt versions and models.
- [ ] `make eval-compare BASE=<exp> NEW=<exp>` prints a table of metric deltas. Any metric dropping more than a configured threshold is marked as a regression (exit code ≠ 0).
- [ ] Web search in eval mode can use **cached search results** (recorded per dataset example). This makes runs reproducible and cheaper. A flag switches to live search.

**Size:** 5

---

### E9-S6 — Online feedback from owner review actions
**As** the owner, **I want** my review behaviour recorded as quality signals, **so that** real usage informs which changes actually help.

**Acceptance criteria**
- [ ] The following are logged as LangSmith feedback on the task's root run:
  - approval: `approved=1` and `revisions_before_approval=n`
  - rejection: `approved=0`, with the reason
  - each revision request: the feedback text and target stage
  - owner edit size: % of lines changed between the last AI revision and the approved revision
- [ ] The UI review page has optional 👍/👎 controls with a comment for each revision. These are also sent as feedback.
- [ ] The README documents how to turn real tasks into new dataset examples from LangSmith (annotation queue or "add to dataset").

**Size:** 2

---

### E9-S7 — Prompt versioning
**As** a developer, **I want** prompts versioned and traceable, **so that** every output can be tied to the exact prompt that produced it.

**Acceptance criteria**
- [ ] Prompts live as files in `src/modules/agent/prompts/` with a `version` header, loaded through a `PromptRegistry`. Each prompt's version and hash go into run metadata and revision metadata.
- [ ] An optional `PROMPT_SOURCE=langsmith` setting pulls prompts from the LangSmith Prompt Hub by commit tag instead of from files. The files remain the default. This is a decision point.
- [ ] A changelog (`prompts/CHANGELOG.md`) is updated with each prompt change and references the eval experiment that justified it.

**Size:** 2

---

### E9-S8 — Ops view in dashboard
**As** the owner, **I want** a simple health and stats page, **so that** I can spot failing tools or rising cost without opening LangSmith.

**Acceptance criteria**
- [ ] The `/settings/ops` page shows, for the last 30 days:
  - tasks by final status
  - average and p90 duration per stage
  - average cost per task
  - tool error rate by tool (search, extract, renderer, publishers)
  - the most recent failures, each with its sanitised error and a LangSmith link
- [ ] Data comes from `task_events`, `run_usage` and `publications`, through one aggregated endpoint (`GET /stats`).

**Size:** 3

---

## Definition of done (epic)
- The dataset is synced to LangSmith.
- `make eval` produces an experiment that has every evaluator.
- A deliberately degraded prompt is flagged as a regression by `make eval-compare`.
- Per-task cost and latency are visible in the UI.
- Owner approvals and rejections appear as feedback on runs.

## Learning map
| Tool | Concepts |
|---|---|
| LangSmith | Datasets & examples, `evaluate`/`aevaluate`, custom & LLM-as-judge evaluators, pairwise experiments, feedback API, annotation queues, Prompt Hub (optional), experiment comparison |
| LangChain | Callback handlers, `usage_metadata` |
| LangGraph | Running the same graph in an "eval mode" (no interrupts, publishing disabled) through config/state flags |

---

## Parked: Milestone 6 — Advanced agents

Do not plan this until Epic 9 metrics exist. Candidates to evaluate against complexity, cost and latency:
- parallel research per question, using the LangGraph `Send` API (map-reduce)
- separate research/writer/diagram **subgraphs** (the diagram subgraph from Epic 7 is the first candidate)
- Deep Agents, for richer planning or filesystem-style context management on very long series

Adopt one only if it improves a measured metric (for example, research coverage or latency) without breaking the approval and safety guarantees.
