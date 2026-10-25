# Blog Agent

A personal AI technical writer that runs locally. You give it a topic. It researches the topic, drafts an article in your style, and waits for your approval of an exact revision. It only publishes to Sanity (leon-pham.vercel.app) or DEV Community after that approval.

- **api/**: FastAPI, LangChain, LangGraph (Postgres checkpointer) and LangSmith tracing. Built on the `feat/fastapi` template with hexagonal modules.
- **ui/**: Next.js 16 dashboard (shadcn, TanStack Query). The browser only talks to the UI's `/api/agent/*` proxy, which adds the API key on the server.
- **db**: Postgres 16 (pgvector image). Business tables are managed by Alembic. LangGraph checkpoints live in their own `langgraph` schema.
- **pdm/**: epics and stories ([epics_overview.md](pdm/epics_overview.md)).

## First-time setup

1. Install Docker Desktop. On WSL, enable *Settings → Resources → WSL integration* for your distro.
2. `make up`. The first run creates `.env` from `.env.example`.
3. Edit `.env`:
   - `LLM_DEFAULT_MODEL` and the matching provider key (e.g. `ANTHROPIC_API_KEY`)
   - optionally `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`
   - optionally `AGENT_API_KEY` (`openssl rand -hex 24`)
4. Run `make up` again.
5. Open http://127.0.0.1:3100. The top-bar badge should read **API healthy**.

## Where secrets live

| Secret | File | Read by |
|---|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | `.env` | api only |
| `LANGSMITH_API_KEY` | `.env` | api only |
| `AGENT_API_KEY` | `.env` | api, plus the ui **server** (proxy) via compose |
| Sanity / Dev.to tokens (Epics 5, 8) | `.env` | api only |

Nothing is exposed as `NEXT_PUBLIC_*`. See [SECURITY.md](SECURITY.md).

## Commands

```bash
make up            # build + start everything (BLOGS=1 also mounts ../blogs for Epic 5 export)
make down          # stop (data kept)
make logs SERVICE=api
make reset-db      # wipe tasks + checkpoints (asks for confirmation)

make install       # host deps for hybrid dev (api/.venv via uv, ui via pnpm)
make dev           # Postgres in Docker; API :8100 and UI :3100 on the host with hot reload

make test              # API unit tests + UI typecheck/lint
make test-integration  # API tests against the compose Postgres
```

| Service | URL |
|---|---|
| Dashboard | http://127.0.0.1:3100 |
| API docs | http://127.0.0.1:8100/docs (requires `X-Agent-Key` when `AGENT_API_KEY` is set) |
| Postgres | `127.0.0.1:5433` |

All ports bind to `127.0.0.1` only. The UI uses port 3100 so it doesn't clash with profile-ui on 3000.

### Smoke-testing the workflow runtime

Set `DEBUG=true`. Then `POST /health/graph {"thread_id": "demo"}` runs a tiny LangGraph graph with the Postgres checkpointer. Calling it again, even after `make down && make up`, increments `count`, which shows that checkpoints persist. Pass `"use_llm": true` to also call the configured fast model. With tracing on, the run shows up in LangSmith and the response includes `trace_url`.

## Observability & Evaluation (Epic 9)

### 1. LangSmith Saved Filters & Views
Every root run in LangSmith is tagged with execution metadata: `task_id`, `mode`, `format`, `revision_number`, `graph_version`, `prompt_versions`, `prompt_hashes`, `style_profile_version`, and `models`.

- **Filter by specific task ID:** In the LangSmith project view (`blog-agent-local`), enter the filter expression:
  ```text
  metadata.task_id = "<your-task-id>"
  ```
- **Filter by mode:**
  ```text
  tag = "mode:article"
  ```
- **Saved view:** In LangSmith, save a view named `Tasks By Mode` with columns for `task_id`, `mode`, `status`, and `total_cost_usd`.

### 2. Evaluation Commands
The dataset in `api/evals/dataset.yaml` is the source of truth for evaluation benchmarks.

```bash
# Sync local YAML dataset to LangSmith (dataset: blog-agent-eval)
make eval-sync

# Run offline evaluation experiment across the dataset in eval mode (no interrupts, publishing disabled)
make eval EXPERIMENT=my_experiment_name

# Compare two evaluation experiments with regression threshold gate (exit code != 0 on regression)
make eval-compare BASE=baseline NEW=my_experiment_name
```

### 3. Adding Real Tasks to the Evaluation Dataset
To capture interesting real-world tasks and failures as regression tests:

1. **In LangSmith:**
   - Locate the root trace for the task in project `blog-agent-local`.
   - Click **Add to Dataset** (or send to an Annotation Queue e.g. `blog-agent-annotation-queue`).
   - Select target dataset: `blog-agent-eval`.
2. **Define Expectations:**
   - Review and populate reference fields: `must_cover`, `expected_source_types`, `min_sources`, `format`, `expected_sections`, `diagram_expected`, and `known_facts`.
3. **Commit to Git:**
   - Append the new entry to `api/evals/dataset.yaml` to ensure git remains the source of truth for all runs.

