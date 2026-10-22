import time
from typing import Annotated
from fastapi import Depends

from src.configs.logger import get_logger
from src.modules.agent.ports.output import IModelFactoryDep, ITracingDep, ModelRole
from src.modules.health.presenter.dtos import LlmPingResponseDto, LlmRolePingDto

logger = get_logger(__name__)


class PingLlmUsecase():
    def __init__(self, models: IModelFactoryDep, tracing: ITracingDep):
        self.models = models
        self.tracing = tracing

    async def execute(self) -> LlmPingResponseDto:
        results: dict[str, LlmRolePingDto] = {}
        for role in ModelRole:
            spec = self.models.spec(role)
            if spec.model is None:
                results[role.value] = LlmRolePingDto(model=None, ok=False, error="not configured")
                continue

            started = time.perf_counter()
            try:
                model = self.models.get(role).bind(max_tokens=1)
                await model.ainvoke(
                    "ping", config=self.tracing.run_config(run_name=f"llm_ping:{role.value}", tags=["health"])
                )
                results[role.value] = LlmRolePingDto(
                    model=spec.model, ok=True, latency_ms=int((time.perf_counter() - started) * 1000)
                )
            except Exception as exc:
                logger.warning("LLM ping failed", extra={"context": {"role": role.value, "error": type(exc).__name__}})
                results[role.value] = LlmRolePingDto(model=spec.model, ok=False, error=type(exc).__name__)
        return LlmPingResponseDto(roles=results)


PingLlmUsecaseDep = Annotated[PingLlmUsecase, Depends(PingLlmUsecase)]
