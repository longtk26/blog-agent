# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in the blog-agent API.

## Commands

```bash
make install                    # uv venv + requirements-dev.txt
make run                        # fastapi dev on 127.0.0.1:8100 (reads ../.env, then .env)
make newmg name="<description>" # Auto-generate Alembic migration from model changes
make mghead                     # Apply all pending migrations
make mgdown                     # Rollback last migration
make test-unit                  # pytest -m "not integration"
TEST_DB_URL=postgresql://... make test   # include integration tests (real Postgres)
```

## Architecture

The API uses module-based hexagonal (clean) architecture, bootstrapped from template branch `feat/fastapi`. See `blog-agent/.agents/skills/fastapi-skills/SKILL.md` for the full conventions.

```
src/
├── main.py              # create_app(): middlewares, exception handlers; lifespan opens the LangGraph checkpointer
├── routers.py           # Central router registry
├── configs/             # config.py (Pydantic Settings), logger.py (JSON logs + secret redaction)
├── libs/
│   ├── database/        # session.py (SQLModel, psycopg3), checkpointer.py (AsyncPostgresSaver, schema "langgraph")
│   ├── exceptions/      # BaseException(+code), ErrorCode, handlers -> {code, message, details, request_id}
│   ├── security/        # RequestContext / ApiKey / JsonContentType ASGI middlewares, slowapi limiter
│   └── decorators/      # @Transactional
└── modules/
    ├── agent/           # Workflow layer: ports (IModelFactory, ITracing, IWorkflowRunner), adapters, graph/, nodes/, prompts/, tools/
    ├── health/          # /health, debug-only /health/llm and /health/graph
    └── shared/          # domain entities + SQLModel models
```

## Key conventions

- **Dep re-exports.** `ports/output/__init__.py` re-exports `I<Name>Dep` lazily through module `__getattr__`. This lets adapters import their port without a circular import. Keep that pattern when adding ports.
- **LLM access.** Always go through `IModelFactoryDep.get(ModelRole.X)`. Never call `init_chat_model` or read provider env vars in nodes.
- **Tracing.** Every graph or model invocation passes `ITracingDep.run_config(...)`, which supplies run name, tags, metadata (`task_id`, …) and a redacting LangSmith tracer. Env auto-tracing is turned off on purpose.
- **Graph state.** Keep it small: store ids, and put large content in DB tables. Checkpoint tables belong to LangGraph, not Alembic. `alembic/env.py` ignores non-public schemas.
- **Errors.** Raise `BaseException` subclasses with an `ErrorCode`. Never return raw stack traces.
- **Requests.** State-changing requests must be JSON (CSRF guard). Upload endpoints must be added to `JsonContentTypeMiddleware(multipart_path_prefixes=...)`.

## Stack

FastAPI 0.124, SQLModel 0.0.27 + Alembic 1.17 on psycopg 3, LangChain 1.4, LangGraph 1.2 (+ checkpoint-postgres 3.2), LangSmith 0.14, slowapi.
