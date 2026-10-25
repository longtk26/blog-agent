import asyncio
import inspect
import time
import uuid
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from src.configs.config import Config
from src.configs.logger import get_logger
from src.modules.agent.ports.output.workflow_store import IWorkflowStore
from src.modules.agent.utils import compute_token_cost

logger = get_logger(__name__)


class TokenUsageCallbackHandler(AsyncCallbackHandler, BaseCallbackHandler):
    """E9-S2: Collects token usage (input, output, cached) and latency per LLM call,
    tagged by node and model, and persists records in `run_usage`.
    """

    def __init__(self, task_id: uuid.UUID, store: IWorkflowStore, config: Config):
        super().__init__()
        self.task_id = task_id
        self.store = store
        self.config = config
        self._starts: dict[uuid.UUID, float] = {}
        self._models: dict[uuid.UUID, str] = {}
        self._nodes: dict[uuid.UUID, str] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_start(serialized, run_id=run_id, tags=tags, metadata=metadata, **kwargs)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_start(serialized, run_id=run_id, tags=tags, metadata=metadata, **kwargs)

    async def on_llm_start_async(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_start(serialized, run_id=run_id, tags=tags, metadata=metadata, **kwargs)

    async def on_chat_model_start_async(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_start(serialized, run_id=run_id, tags=tags, metadata=metadata, **kwargs)

    def _record_start(
        self,
        serialized: dict[str, Any] | None,
        *,
        run_id: uuid.UUID,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._starts[run_id] = time.perf_counter()
        meta = metadata or {}
        model_name = (
            meta.get("ls_model_name")
            or meta.get("model_name")
            or (serialized or {}).get("name")
            or (serialized or {}).get("kwargs", {}).get("model")
            or (serialized or {}).get("kwargs", {}).get("model_name")
            or getattr(self.config, "llm_default_model", None)
            or "default"
        )
        self._models[run_id] = str(model_name)

        # Node name resolution
        node = meta.get("node") or meta.get("langgraph_node") or "unknown"
        if node == "unknown" and tags:
            for tag in tags:
                if tag.startswith("node:"):
                    node = tag.split(":", 1)[1]
                    break
        self._nodes[run_id] = str(node)

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        await self._process_end(response, run_id=run_id, **kwargs)

    def on_llm_end_sync(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._process_end(response, run_id=run_id, **kwargs))
        except RuntimeError:
            pass

    async def _process_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            start = self._starts.pop(run_id, None)
            latency_ms = int((time.perf_counter() - start) * 1000) if start else 0
            model = self._models.pop(run_id, getattr(self.config, "llm_default_model", None) or "default")
            node = self._nodes.pop(run_id, "unknown")

            input_tokens = 0
            output_tokens = 0
            cached_tokens = 0
            total_tokens = 0

            # 1. From response.llm_output
            if response.llm_output:
                usage = response.llm_output.get("token_usage") or response.llm_output.get("usage") or {}
                if isinstance(usage, dict):
                    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
                    cached_tokens = usage.get("cached_tokens") or 0
                    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)

            # 2. From generation message.usage_metadata
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg and hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        um = msg.usage_metadata
                        input_tokens = max(input_tokens, um.get("input_tokens", 0))
                        output_tokens = max(output_tokens, um.get("output_tokens", 0))
                        total_tokens = max(total_tokens, um.get("total_tokens", 0))
                        details = um.get("input_token_details") or {}
                        if isinstance(details, dict):
                            cached_tokens = max(cached_tokens, details.get("cache_read", 0))
                    elif gen and getattr(gen, "generation_info", None):
                        gi = gen.generation_info or {}
                        um = gi.get("usage_metadata") or {}
                        if isinstance(um, dict):
                            input_tokens = max(input_tokens, um.get("input_tokens", 0))
                            output_tokens = max(output_tokens, um.get("output_tokens", 0))
                            total_tokens = max(total_tokens, um.get("total_tokens", 0))

            if total_tokens == 0:
                total_tokens = input_tokens + output_tokens

            cost_usd = compute_token_cost(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                pricing_table=self.config.model_pricing,
            )

            record_call = self.store.record_usage(
                task_id=self.task_id,
                run_id=run_id,
                node=node,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
            )
            if inspect.isawaitable(record_call):
                await record_call
        except Exception as exc:
            logger.warning(f"Error collecting token usage: {exc}")
