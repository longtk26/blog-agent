from typing import TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    pass


async def invoke_structured(model, schema: type[T], messages: list[BaseMessage], repair_attempts: int = 1) -> T:
    """Ask for `schema` via provider-native structured output; on a bad answer, retry once with the error.
    Model output is untrusted: it is always re-validated against the Pydantic schema."""
    runnable = model.with_structured_output(schema)
    history = list(messages)
    last_error: Exception | None = None
    for _ in range(repair_attempts + 1):
        try:
            result = await runnable.ainvoke(history)
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
