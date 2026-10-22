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
