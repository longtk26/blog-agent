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


async def test_full_mocked_task_scans_all_traces_for_secrets():
    fake_openai = "sk-proj-FAKE-openai-key-9999"
    fake_tavily = "tvly-FAKE-tavily-key-8888"
    fake_devto = "devto_FAKE_key_7777"
    fake_sanity = "sk-sanity-FAKE-token-6666"

    config = make_config(
        langsmith_tracing=True,
        langsmith_api_key=FAKE_LANGSMITH_KEY,
        anthropic_api_key=FAKE_PROVIDER_KEY,
        openai_api_key=fake_openai,
        tavily_api_key=fake_tavily,
        dev_to_api_key=fake_devto,
        sanity_api_write_token=fake_sanity,
    )
    all_secrets = config.secret_values()
    assert len(all_secrets) >= 6

    session = CapturingSession()
    client = Client(
        api_key=FAKE_LANGSMITH_KEY,
        api_url="http://ls.invalid",
        session=session,
        auto_batch_tracing=False,
        anonymizer=build_secret_anonymizer(all_secrets),
    )
    tracing = LangSmithTracing(config, client=client)

    # Build a multi-node workflow representing the full task pipeline
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict

    class MockTaskState(TypedDict):
        task_id: str
        query: str
        search_result: str
        draft: str
        judge_verdict: str

    async def plan_research_node(state: MockTaskState):
        # Leaking Tavily key into research plan
        return {"query": f"search for {fake_tavily} and LoRA"}

    async def search_node(state: MockTaskState):
        # Tool execution returning page with secret
        return {"search_result": f"Found page containing secret {fake_devto} and {fake_openai}"}

    async def draft_section_node(state: MockTaskState):
        # LLM output leaking provider key
        return {"draft": f"# Draft\nUsing key {FAKE_PROVIDER_KEY} to authenticate with {fake_sanity}"}

    async def judge_node(state: MockTaskState):
        # Judge reviewing draft
        return {"judge_verdict": f"Score 4/4; verified against {FAKE_LANGSMITH_KEY}"}

    builder = StateGraph(MockTaskState)
    builder.add_node("plan_research", plan_research_node)
    builder.add_node("search", search_node)
    builder.add_node("draft_section", draft_section_node)
    builder.add_node("judge_draft", judge_node)

    builder.add_edge(START, "plan_research")
    builder.add_edge("plan_research", "search")
    builder.add_edge("search", "draft_section")
    builder.add_edge("draft_section", "judge_draft")
    builder.add_edge("judge_draft", END)

    mock_graph = builder.compile()

    run_config = tracing.run_config(
        run_name="blog_task",
        tags=["mode:full", "env:test"],
        metadata={
            "task_id": "test-task-123",
            "mode": "full",
            "format": "tutorial",
            "revision_number": 1,
            "graph_version": "v1",
        },
    )

    initial_state = {
        "task_id": "test-task-123",
        "query": f"Initial prompt with {fake_openai}",
        "search_result": "",
        "draft": "",
        "judge_verdict": "",
    }

    result = await mock_graph.ainvoke(initial_state, config=run_config)
    assert result["judge_verdict"]

    for cb in run_config.get("callbacks", []):
        if hasattr(cb, "wait_for_futures"):
            cb.wait_for_futures()

    all_bodies = "\n".join(session.bodies)
    assert len(session.bodies) > 0, "Tracer should have captured multiple node events"

    # Verify that NONE of the configured secrets appear in any trace payload
    for secret in all_secrets:
        assert secret not in all_bodies, f"Configured secret {secret} leaked into trace payload!"

    # Verify that redactions occurred
    assert "[REDACTED]" in all_bodies

