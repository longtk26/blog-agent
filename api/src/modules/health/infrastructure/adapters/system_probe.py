from typing import Annotated

from fastapi import Depends
from starlette.concurrency import run_in_threadpool

from src.libs.database import CheckpointerManagerDep, db_session_manager
from src.modules.health.ports.output.system_probe import ISystemProbe


class SystemProbe(ISystemProbe):
    def __init__(self, checkpointer_manager: CheckpointerManagerDep):
        self.checkpointer_manager = checkpointer_manager

    async def database_ok(self) -> bool:
        return await run_in_threadpool(db_session_manager.ping)

    async def checkpointer_ok(self) -> bool:
        return await self.checkpointer_manager.ping()


ISystemProbeDep = Annotated[ISystemProbe, Depends(SystemProbe)]
