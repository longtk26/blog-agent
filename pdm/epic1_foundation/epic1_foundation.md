# Epic 1 — Foundation & Local Runtime

| | |
|---|---|
| **Milestone** | MVP |
| **Depends on** | — |
| **Status** | Draft for review |

## Goal

Running `docker compose up` in `blog-agent/` starts a working FastAPI backend, Next.js dashboard and Postgres on the owner's machine. The LLM provider is configurable, LangSmith tracing works, and secrets are handled safely. Every later epic builds on this skeleton without reworking it.

## Context

- The agent runs **locally only**, on demand. There is no cloud deployment and no multi-user support.
- The backend must be cloned from the template branch `feat/fastapi` (`https://github.com/longtk26/template-frameworks.git`) and follow the hexagonal module layout in `blog-agent/.agents/skills/fastapi-skills`.
- The frontend must follow `blog-agent/.agents/skills/nextjs-skills`: `pnpx create-next-app`, pnpm, shadcn, React Query, Zustand, RHF + Zod.
- The owner's site uses a forced dark theme with zinc/shadcn "new-york". The dashboard should feel consistent with it.

## In scope

- Repo layout, Docker Compose, env management, Makefile.
- FastAPI bootstrap, config, logging, rate limiting, health check.
- Postgres plus Alembic, and the LangGraph checkpointer setup.
- LLM model factory and LangSmith tracing.
- Next.js app shell, API client, providers.
- Local security baseline.

## Out of scope

- Any workflow logic (Epic 2+).
- pgvector (Epic 6).
- The renderer container (Epic 7).

---

## Stories

### E1-S1 — Repository layout & developer workflow
**As** the owner, **I want** a clear `blog-agent/` layout with one-command workflows, **so that** I can start, stop and reset the agent without remembering details.

**Acceptance criteria**
- [ ] The folder structure matches the layout in [epics_overview.md §2](../epics_overview.md#proposed-repository-layout): `api/`, `ui/`, `data/` (git-ignored), `docker-compose.yml`, `.env.example`, `Makefile`, `README.md`.
- [ ] The `Makefile` has these targets:
  - `make up` / `make down` / `make logs`
  - `make reset-db` (asks for confirmation)
  - `make dev` (hybrid mode: Postgres in Docker, API and UI run locally with hot reload)
  - `make migrate`
  - `make test`
- [ ] The README documents first-time setup in 5 steps or fewer, plus where each secret goes.
- [ ] `.gitignore` excludes `.env*` (but not `.env.example`), `data/` and `.venv`.

**Size:** 2

---

### E1-S2 — Bootstrap FastAPI service from template
**As** a developer, **I want** the API bootstrapped from the `feat/fastapi` template, **so that** DI, transactions, exceptions and logging conventions come for free.

**Acceptance criteria**
- [ ] `blog-agent/api` is cloned from `feat/fastapi` with `.git` removed and becomes part of the repo.
- [ ] `src/configs/config.py` (Pydantic Settings) declares every env var used by the project. Secrets use `SecretStr`. Missing required values fail startup with a clear message.
- [ ] The `health` module exposes `GET /health`. It reports DB connectivity, checkpointer readiness, the configured LLM provider name (not the key), and whether LangSmith tracing is on.
- [ ] Rate limiting (`slowapi`) is applied globally with a generous local default. Stricter limits apply to task creation and publish endpoints.
- [ ] The structured logger is configured. A `request_id` and a `task_id` (when present) are bound to every log line.
- [ ] All six skill pillars pass the skill's PR checklist.

**Technical notes**
- Add a `src/modules/agent/` package for workflow code: `graph/`, `nodes/`, `prompts/`, `tools/`. Use cases interact with it only through an output port, `IWorkflowRunner`.
- Use Python 3.12. Pin `langchain`, `langgraph`, `langgraph-checkpoint-postgres` and `langsmith` versions in `requirements.txt`.

**Size:** 3

---

### E1-S3 — Postgres, migrations & LangGraph checkpointer
**As** a developer, **I want** one Postgres instance for both business data and LangGraph checkpoints, **so that** paused reviews survive restarts.

**Acceptance criteria**
- [ ] Docker Compose runs `pgvector/pgvector:pg16`. The extension itself is not enabled until Epic 6. A named volume persists the data.
- [ ] Alembic is configured as in the template (`make newmg`, `make mghead`, `make mgdown`). The initial migration runs on API container start.
- [ ] On startup, an `AsyncPostgresSaver` is created from a psycopg connection pool and `setup()` is run, targeting a dedicated `langgraph` schema.
- [ ] The saver is exposed through DI as `CheckpointerDep`.
- [ ] Alembic autogenerate ignores the `langgraph` schema.
- [ ] Integration test: write a checkpoint for a dummy graph, restart the app, and read it back.

**Technical notes**
- Keep business tables (Alembic/SQLModel) separate from checkpoint tables (owned by LangGraph). The brief requires this: "workflow state distinct from durable business records".

**Size:** 3

---

### E1-S4 — Configurable LLM model factory
**As** the owner, **I want** to choose the LLM provider and model per role through env vars, **so that** I can balance cost and quality without code changes.

**Acceptance criteria**
- [ ] Settings define model roles. Each role is a `provider:model` string passed to LangChain `init_chat_model`:

  | Role | Used for |
  |---|---|
  | `LLM_PLANNER_MODEL` | Research plan, outline |
  | `LLM_WRITER_MODEL` | Drafting, revisions |
  | `LLM_FAST_MODEL` | Extraction, classification |
  | `LLM_JUDGE_MODEL` | Evaluation |

- [ ] Any role left unset falls back to `LLM_DEFAULT_MODEL`.
- [ ] Per-role temperature, `max_tokens` and timeout are configurable. Retries are bounded (default 2).
- [ ] A `ModelFactory` adapter (output port `IModelFactory`) returns a configured `BaseChatModel`. Nodes never read env directly.
- [ ] `GET /health/llm`, gated behind a debug flag, runs a 1-token ping per configured role.
- [ ] Unit tests use LangChain's `GenericFakeChatModel` through the same port.

**Open decision:** D1 (provider/model defaults).

**Size:** 2

---

### E1-S5 — LangSmith tracing baseline
**As** the owner, **I want** every agent run traced in LangSmith, **so that** I can see what the agent did and debug bad outputs from day 1.

**Acceptance criteria**
- [ ] Tracing is controlled by `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` (default `blog-agent-local`) and `LANGSMITH_ENDPOINT`. Turning it off disables tracing cleanly.
- [ ] Every graph invocation passes a `RunnableConfig` with:
  - `run_name="blog_task"`
  - `tags=[mode, env]`
  - `metadata={task_id, revision_number, graph_version, prompt_versions}`
- [ ] Secrets never appear in traces. A test asserts that the trace payload of a run whose settings contain a fake key does not contain the key.
- [ ] Optional `LANGSMITH_HIDE_INPUTS`/`OUTPUTS` setting (decision D9).
- [ ] The task detail API returns the LangSmith run URL when tracing is enabled.

**Size:** 2

---

### E1-S6 — Bootstrap Next.js dashboard & app shell
**As** the owner, **I want** a dashboard shell with navigation, **so that** later features plug into a consistent layout.

**Acceptance criteria**
- [ ] The app is created with `pnpx create-next-app@latest` (TypeScript, Tailwind, ESLint, App Router, `src/`, `@/*`, pnpm).
- [ ] shadcn is initialised with the "new-york" style and zinc base color. Dark mode is the default and the toggle is optional. Design tokens live in `globals.css` with no hard-coded colors.
- [ ] Providers are in place: `QueryClientProvider` with sensible defaults, `ThemeProvider` and `Toaster` (sonner).
- [ ] Layout is built outside-in:
  - Sidebar items: **New task**, **Tasks**, **Style** (Epic 6, hidden for now), **Settings**.
  - A top bar shows backend health (polls `/health`).
- [ ] `lib/api-client.ts` is a typed fetch wrapper. It maps API errors (the template's `BaseException` format) to `TApiError`, and toasts show them.
- [ ] There are **no** `NEXT_PUBLIC_*` env vars. The browser calls the same-origin proxy `/api/agent/*`, and the server-only env vars `AGENT_API_URL` and `AGENT_API_KEY` stay on the server. *(Changed during implementation; see notes below.)*
- [ ] The feature folder pattern (`features/<feature>/{api,components,hooks,schemas,query-keys.ts}`) is established with a `health` feature as the example.

**Size:** 3

---

### E1-S7 — Docker Compose runtime
**As** the owner, **I want** `docker compose up` to start everything, **so that** I can run the agent on demand with no manual steps.

**Acceptance criteria**
- [ ] Services:
  - `db`, with a healthcheck.
  - `api`: depends on a healthy `db`, runs migrations and then `uvicorn`.
  - `ui`: a Next.js standalone build.
- [ ] All published ports bind to `127.0.0.1`: UI `127.0.0.1:3100`, API `127.0.0.1:8100`, DB `127.0.0.1:5433`. This avoids clashing with profile-ui on 3000.
- [ ] Volumes:
  - `pgdata`
  - `./data` mounted to `/app/data` (assets/exports)
  - **optional** `../blogs` mounted to `/app/blogs` (used in Epic 5 export; read-write; toggled by an env var)
- [ ] `api` reads `blog-agent/.env`. `ui` receives only `AGENT_API_URL` and `AGENT_API_KEY`, as server-side env vars.
- [ ] A cold start to a healthy state takes 2 minutes or less on a dev laptop after the images are built.
- [ ] `docker compose down` then `up` keeps all tasks and checkpoints.

**Size:** 3

---

### E1-S8 — Local security baseline
**As** the owner, **I want** sensible protections even though the agent is local, **so that** publishing credentials can't leak or be triggered by another site in my browser.

**Acceptance criteria**
- [ ] CORS allows only the UI origin.
- [ ] Optional `AGENT_API_KEY`: when it is set, the API requires the `X-Agent-Key` header. The UI attaches the key from server-side code only: a Next.js route handler or server action proxy, never a `NEXT_PUBLIC_*` value. (Decision D7.)
- [ ] State-changing endpoints reject requests without `Content-Type: application/json`. This mitigates CSRF from simple forms.
- [ ] A log redaction filter masks values of known secret settings and `Authorization`/`api-key` headers.
- [ ] `SECURITY.md` in `blog-agent/` lists the secrets, where they live, and the threat model (local single user, untrusted web content, untrusted model output).

**Size:** 2

---

## Definition of done (epic)
- `make up` brings up a healthy stack, and the dashboard shows "API healthy, LLM configured, tracing on/off".
- A dummy LangGraph graph run appears in LangSmith with task metadata and survives an API restart through the checkpointer.
- The skill checklists (FastAPI and Next.js) pass.

## Learning map
| Tool | Concepts |
|---|---|
| LangChain | `init_chat_model`, `BaseChatModel`, `RunnableConfig`, fake chat models for tests |
| LangGraph | Checkpointers (`AsyncPostgresSaver`), threads, `setup()` |
| LangSmith | Env-based tracing, projects, run metadata/tags, hiding inputs/outputs |

---

## Implementation notes (delivered 2026-10-22)

| Story | Where | Notes |
|---|---|---|
| E1-S1 | `Makefile`, `README.md`, `.env.example`, `.gitignore` | `make help` lists the targets. `make dev` runs the API and UI on the host with hot reload, against the Docker db. |
| E1-S2 | `api/` (from `feat/fastapi`) | The template's example `users` module was removed. `BaseException` gained an `ErrorCode`, and all errors return `{code, message, details?, request_id}`. Logs are JSON, carry `request_id`/`task_id` context vars, and pass through a redaction filter. slowapi sets a global limit, and debug endpoints get a strict one. |
| E1-S3 | `api/src/libs/database/checkpointer.py` | The driver changed from psycopg2 to **psycopg 3** for both SQLAlchemy and LangGraph, so there is one driver. Checkpoints live in schema `langgraph` (`search_path` on the pool). Alembic ignores non-public schemas, and `alembic check` is clean. |
| E1-S4 | `agent/infrastructure/adapters/langchain_model_factory.py` | Roles planner/writer/fast/judge fall back to `LLM_DEFAULT_MODEL`. The `/health/llm` 1-token ping only works with `DEBUG=true`. Provider packages: anthropic, openai, google-genai. |
| E1-S5 | `agent/infrastructure/adapters/langsmith_tracing.py` | The tracer is attached explicitly, using our own `Client` with a secret anonymizer. Env auto-tracing flags are removed at startup, so traces are never sent twice or unredacted. The run URL comes from `client.runs.get_url`. |
| E1-S6 | `ui/` | Next.js **16.4** (App Router, Cache Components, Turbopack), with shadcn preset `vega` on Radix and the neutral palette. Additions: `success`/`warning` tokens, and a health badge in the top bar that polls `/health` every 15 s. |
| E1-S7 | `docker-compose.yml`, `api/Dockerfile`, `ui/Dockerfile` | The UI uses port 3100, the API 8100 and the DB 5433, all on `127.0.0.1`. The optional `../blogs` mount is `docker-compose.blogs.yml`, used via `make up BLOGS=1`. |
| E1-S8 | `SECURITY.md`, `libs/security/` | Changed from the plan: instead of the browser calling the API directly, a **same-origin proxy** adds the key on the server and blocks cross-site writes. CORS is therefore defence in depth. |

**Verification:**
- 27 pytest tests pass: unit tests, plus integration tests against a real Postgres 16. They cover checkpoint persistence across a manager restart, schema isolation, the health API, debug gating, the error format, the CSRF/API-key middlewares, model-factory fallback, and a captured LangSmith payload that must not contain configured secrets.
- The UI passes `next build`, `tsc` and `eslint`.
- A manual end-to-end check went through proxy → API with the key enabled. `/health/graph` count went 1 → 2 across an API restart.

**Docker verified:**
- `make up` builds and starts db, api and ui. db and api report healthy.
- `/health` returns healthy through the UI proxy, and all pages return 200.
- API logs are JSON.
- `make test-integration` passes 27/27 against the Compose Postgres.

From WSL, the Makefile uses the `docker` CLI and falls back to Docker Desktop's `docker.exe` when that isn't available.

**Not verified:** a real LLM call and a real LangSmith trace, because no keys are configured yet.
