import uuid
from typing import Annotated
from fastapi import Depends

from src.libs.database import CheckpointerDep
from src.modules.agent.graph import build_ping_graph
from src.modules.agent.ports.output import IModelFactoryDep, ITracingDep, ModelRole
from src.modules.health.presenter.dtos import GraphPingRequestDto, GraphPingResponseDto


class GraphPingUsecase():
    def __init__(self, checkpointer: CheckpointerDep, models: IModelFactoryDep, tracing: ITracingDep):
        self.checkpointer = checkpointer
        self.models = models
        self.tracing = tracing

    async def execute(self, request: GraphPingRequestDto) -> GraphPingResponseDto:
        model = self.models.get(ModelRole.FAST) if request.use_llm else None
        graph = build_ping_graph(self.checkpointer, model)
        run_id = uuid.uuid4()
        run_config = self.tracing.run_config(
            run_name="graph_ping",
            tags=["health"],
            metadata={"task_id": request.thread_id},
            run_id=run_id,
            configurable={"thread_id": request.thread_id},
        )
        state = await graph.ainvoke({}, config=run_config)
        return GraphPingResponseDto(
            thread_id=request.thread_id,
            count=state["count"],
            reply=state["reply"],
            run_id=str(run_id),
            trace_url=await self.tracing.run_url(run_id),
        )


GraphPingUsecaseDep = Annotated[GraphPingUsecase, Depends(GraphPingUsecase)]
