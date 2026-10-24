import os
import re
import uuid
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client
from langsmith.anonymizer import create_anonymizer

from src.configs import config as app_config
from src.configs.config import Config
from src.configs.logger import REDACTED, get_logger
from src.modules.agent.ports.output.tracing import ITracing

logger = get_logger(__name__)

GRAPH_VERSION = "0.1.0"

# LangChain auto-attaches an env-configured tracer when these are set. We attach our own
# tracer (with a redacting client) explicitly instead, so traces are never sent twice or unredacted.
ENV_TRACING_FLAGS = ("LANGSMITH_TRACING", "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING")


def disable_env_tracing() -> None:
    for flag in ENV_TRACING_FLAGS:
        os.environ.pop(flag, None)


class LangSmithTracing(ITracing):
    def __init__(self, config: Config, client: Client | None = None):
        self.config = config
        self.enabled = config.tracing_enabled
        self.project = config.langsmith_project
        self._project_id: str | None = None
        self.client = client
        if self.enabled and self.client is None:
            self.client = Client(
                api_key=config.langsmith_api_key.get_secret_value(),
                api_url=config.langsmith_endpoint,
                anonymizer=build_secret_anonymizer(config.secret_values()),
                hide_inputs=config.langsmith_hide_inputs,
                hide_outputs=config.langsmith_hide_outputs,
            )

    def run_config(
        self,
        *,
        run_name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        run_id: uuid.UUID | None = None,
        callbacks: list[BaseCallbackHandler] | None = None,
        configurable: dict[str, Any] | None = None,
    ) -> RunnableConfig:
        handlers: list[BaseCallbackHandler] = list(callbacks or [])
        if self.enabled:
            handlers.append(LangChainTracer(client=self.client, project_name=self.project))

        run_config: RunnableConfig = {
            "run_name": run_name,
            "tags": [f"env:{self.config.env}", *(tags or [])],
            "metadata": {"graph_version": GRAPH_VERSION, "env": self.config.env, **(metadata or {})},
            "callbacks": handlers,
        }
        if run_id is not None:
            run_config["run_id"] = run_id
        if configurable:
            run_config["configurable"] = configurable
        return run_config

    async def run_url(self, run_id: uuid.UUID | str) -> str | None:
        if not self.enabled:
            return None
        try:
            if self._project_id is None:
                self._project_id = str(self.client.read_project(project_name=self.project).id)
            response = await self.client.runs.get_url(str(run_id), project_id=self._project_id, trace_id=str(run_id))
            return getattr(response, "url", None)
        except Exception as exc:
            logger.warning("Could not resolve LangSmith run URL", extra={"context": {"error": type(exc).__name__}})
            return None

    def record_feedback(
        self, run_id: uuid.UUID | str, key: str, *, score: float | None = None, comment: str | None = None, value: Any = None
    ) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            # The redacting anonymizer only covers runs, so feedback text is redacted here too.
            redact = build_secret_anonymizer(self.config.secret_values())
            self.client.create_feedback(
                run_id, key, score=score, value=value, comment=redact(comment) if (redact and comment) else comment,
                trace_id=run_id, feedback_source_type="app",
            )
        except Exception as exc:
            logger.warning("Could not record LangSmith feedback", extra={"context": {"error": type(exc).__name__}})

    def flush(self) -> None:
        if self.enabled and self.client is not None:
            try:
                self.client.flush(timeout=5)
            except Exception:
                logger.warning("LangSmith flush failed")


def build_secret_anonymizer(secrets: list[str]):
    rules = [{"pattern": re.compile(re.escape(secret)), "replace": REDACTED} for secret in secrets]
    return create_anonymizer(rules) if rules else None


@lru_cache
def get_tracing() -> ITracing:
    return LangSmithTracing(app_config)


ITracingDep = Annotated[ITracing, Depends(get_tracing)]
