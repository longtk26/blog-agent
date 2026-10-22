from typing import Annotated
from fastapi import Depends

from src.configs import config
from src.modules.agent.ports.output import IModelFactoryDep, ITracingDep, ModelRole
from src.modules.health.ports.output import ISystemProbeDep
from src.modules.research.ports.output import ISearchProviderDep
from src.modules.health.presenter.dtos import (
    ComponentStatusDto,
    HealthCheckResponseDto,
    LlmStatusDto,
    SearchStatusDto,
    TracingStatusDto,
)


class HealthCheckUsecase():
    def __init__(self, probe: ISystemProbeDep, models: IModelFactoryDep, tracing: ITracingDep, search: ISearchProviderDep):
        self.probe = probe
        self.search = search
        self.models = models
        self.tracing = tracing

    async def execute(self) -> HealthCheckResponseDto:
        database_ok = await self.probe.database_ok()
        checkpointer_ok = await self.probe.checkpointer_ok()
        roles = self.models.describe()

        return HealthCheckResponseDto(
            status="healthy" if database_ok and checkpointer_ok else "degraded",
            app=config.app_name,
            env=config.env,
            database=ComponentStatusDto(ok=database_ok),
            checkpointer=ComponentStatusDto(ok=checkpointer_ok),
            llm=LlmStatusDto(
                configured=all(roles.values()),
                default_provider=self.models.spec(ModelRole.WRITER).provider,
                roles=roles,
            ),
            search=SearchStatusDto(provider=self.search.name),
            tracing=TracingStatusDto(
                enabled=self.tracing.enabled,
                project=self.tracing.project if self.tracing.enabled else None,
            ),
        )


HealthCheckUsecaseDep = Annotated[HealthCheckUsecase, Depends(HealthCheckUsecase)]
