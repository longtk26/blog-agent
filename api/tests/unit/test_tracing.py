import json
import os

import pytest
import requests
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tracers.langchain import LangChainTracer
from langsmith import Client

from src.configs.config import Config
from src.modules.agent.graph import build_ping_graph
from src.modules.agent.infrastructure.adapters.langsmith_tracing import (
    LangSmithTracing,
    build_secret_anonymizer,
    disable_env_tracing,
)

FAKE_PROVIDER_KEY = "sk-ant-FAKE-provider-key-0001"
FAKE_LANGSMITH_KEY = "lsv2_FAKE_langsmith_key_0002"


class CapturingSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.bodies: list[str] = []

    def request(self, method, url, **kwargs):
        body = kwargs.get("data") or json.dumps(kwargs.get("json") or {})
        self.bodies.append(body.decode(errors="ignore") if isinstance(body, bytes) else str(body))
        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        response.url = url
        return response


def make_config(**overrides) -> Config:
    return Config(_env_file=None, db_url="postgresql://u:p@localhost/db", env="test", **overrides)


def test_disabled_tracing_adds_metadata_but_no_tracer():
    tracing = LangSmithTracing(make_config())
    run_config = tracing.run_config(run_name="x", tags=["health"], metadata={"task_id": "t1"})
    assert tracing.enabled is False
    assert run_config["callbacks"] == []
    assert run_config["tags"] == ["env:test", "health"]
    assert run_config["metadata"]["task_id"] == "t1"
    assert "graph_version" in run_config["metadata"]


def test_enabled_tracing_attaches_langchain_tracer():
    config = make_config(langsmith_tracing=True, langsmith_api_key=FAKE_LANGSMITH_KEY)
    client = Client(
        api_key=FAKE_LANGSMITH_KEY, api_url="http://ls.invalid", session=CapturingSession(), auto_batch_tracing=False
    )
    tracing = LangSmithTracing(config, client=client)
    run_config = tracing.run_config(run_name="x", configurable={"thread_id": "t1"})
    assert any(isinstance(cb, LangChainTracer) for cb in run_config["callbacks"])
    assert run_config["configurable"] == {"thread_id": "t1"}


def test_disable_env_tracing_removes_auto_tracing_flags(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    disable_env_tracing()
    assert "LANGSMITH_TRACING" not in os.environ
    assert "LANGCHAIN_TRACING_V2" not in os.environ


async def test_trace_payload_never_contains_configured_secrets():
    config = make_config(
        langsmith_tracing=True, langsmith_api_key=FAKE_LANGSMITH_KEY, anthropic_api_key=FAKE_PROVIDER_KEY
    )
    session = CapturingSession()
    client = Client(
        api_key=FAKE_LANGSMITH_KEY,
        api_url="http://ls.invalid",
        session=session,
        auto_batch_tracing=False,
        anonymizer=build_secret_anonymizer(config.secret_values()),
    )
    tracing = LangSmithTracing(config, client=client)

    # Simulate a worst case: the secret leaks into model output.
    model = GenericFakeChatModel(messages=iter([AIMessage(content=f"pong {FAKE_PROVIDER_KEY}")]))
    graph = build_ping_graph(checkpointer=None, model=model)
    run_config = tracing.run_config(run_name="graph_ping", metadata={"task_id": "t1"})
    await graph.ainvoke({}, config=run_config)
    for callback in run_config["callbacks"]:
        callback.wait_for_futures()

    payload = "\n".join(session.bodies)
    assert session.bodies, "expected trace requests to be captured"
    assert "graph_ping" in payload
    assert FAKE_PROVIDER_KEY not in payload
    assert FAKE_LANGSMITH_KEY not in payload
    assert "[REDACTED]" in payload
