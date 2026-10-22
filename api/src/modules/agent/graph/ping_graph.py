from typing import TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


class PingState(TypedDict, total=False):
    count: int
    reply: str


def build_ping_graph(checkpointer: BaseCheckpointSaver | None, model: BaseChatModel | None = None):
    """Smoke-test graph: increments a counter per run on the same thread, proving checkpoint persistence."""

    async def ping(state: PingState) -> PingState:
        reply = "pong"
        if model is not None:
            message = await model.ainvoke("Reply with the single word: pong")
            reply = str(message.content)[:50]
        return {"count": state.get("count", 0) + 1, "reply": reply}

    builder = StateGraph(PingState)
    builder.add_node("ping", ping)
    builder.add_edge(START, "ping")
    builder.add_edge("ping", END)
    return builder.compile(checkpointer=checkpointer)
