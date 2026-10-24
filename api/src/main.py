import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from src.configs import config
from src.configs.logger import get_logger, setup_logging
from src.libs.database import CheckpointerManager
from src.libs.events import event_broker
from src.libs.exceptions import register_exception_handlers
from src.libs.security import ApiKeyMiddleware, JsonContentTypeMiddleware, RequestContextMiddleware, limiter
from src.modules.agent.graph.blog_graph import build_blog_graph
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.infrastructure.adapters import (
    LangGraphWorkflowRunner,
    WorkflowStore,
    disable_env_tracing,
    get_model_factory,
    get_tracing,
)
from src.modules.research.infrastructure.adapters import get_page_extractor, get_search_provider
from src.routers import all_router

setup_logging(config)
config.export_provider_env()
disable_env_tracing()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for router in all_router:
        app.include_router(router)

    checkpointer_manager = CheckpointerManager(
        config.db_url, schema=config.checkpoint_schema, max_size=config.checkpoint_pool_size
    )
    await checkpointer_manager.open()
    app.state.checkpointer_manager = checkpointer_manager

    event_broker.bind_loop(asyncio.get_running_loop())
    store = WorkflowStore(event_broker)
    from src.modules.styles.infrastructure.adapters import PgVectorStore, get_embedding_service

    deps = WorkflowDeps(
        store=store,
        models=get_model_factory(),
        search=get_search_provider(),
        extractor=get_page_extractor(),
        settings=config,
        vector_store=PgVectorStore(),
        embeddings=get_embedding_service(),
    )
    runner = LangGraphWorkflowRunner(
        build_blog_graph(deps, checkpointer_manager.saver),
        store,
        get_tracing(),
        max_concurrency=config.workflow_max_concurrency,
        secrets=config.secret_values(),
    )
    app.state.workflow_runner = runner
    await runner.recover()
    logger.info(
        "API started",
        extra={
            "context": {
                "env": config.env,
                "tracing": config.tracing_enabled,
                "auth": bool(config.agent_api_key),
                "search": deps.search.name,
                "extractor": deps.extractor.name,
            }
        },
    )
    yield
    await runner.shutdown()
    get_tracing().flush()
    await checkpointer_manager.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Blog Agent API", lifespan=lifespan)
    app.state.limiter = limiter
    register_exception_handlers(app)

    # Starlette runs the last-added middleware first: RequestContext -> CORS -> ApiKey -> ContentType -> RateLimit
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(JsonContentTypeMiddleware)
    app.add_middleware(
        ApiKeyMiddleware,
        api_key=config.agent_api_key.get_secret_value() if config.agent_api_key else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Agent-Key", "X-Request-ID", "Last-Event-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
