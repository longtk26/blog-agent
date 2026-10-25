from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ValidationError

from src.modules.agent.nodes.base import workflow_callbacks_ctx

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    pass


async def invoke_structured(
    model,
    schema: type[T],
    messages: list[BaseMessage],
    repair_attempts: int = 1,
    run_name: str | None = None,
    node: str | None = None,
) -> T:
    """Ask for `schema` via provider-native structured output; on a bad answer, retry once with the error.
    Model output is untrusted: it is always re-validated against the Pydantic schema."""
    runnable = model.with_structured_output(schema)
    run_cfg: dict = {}
    if run_name:
        run_cfg["run_name"] = run_name
    if node or run_name:
        run_cfg["metadata"] = {"node": node or run_name}
        run_cfg["tags"] = [f"node:{node or run_name}"]

    # Propagate active callbacks (TokenUsageCallbackHandler, LangChainTracer)
    cbs = workflow_callbacks_ctx.get()
    if cbs:
        run_cfg["callbacks"] = cbs

    history = list(messages)
    last_error: Exception | None = None
    for _ in range(repair_attempts + 1):
        try:
            result = await runnable.ainvoke(history, config=run_cfg if run_cfg else None)
            if result is None:
                raise ValueError("model returned no structured output")
            return result if isinstance(result, schema) else schema.model_validate(result)
        except (ValidationError, OutputParserException, ValueError, TypeError) as exc:
            last_error = exc
            history = [
                *messages,
                HumanMessage(f"Your previous answer was invalid ({type(exc).__name__}: {str(exc)[:500]}). "
                             "Answer again with output that matches the schema exactly."),
            ]
    raise StructuredOutputError(f"{schema.__name__}: {last_error}") from last_error
