from abc import ABC, abstractmethod


class ISystemProbe(ABC):
    @abstractmethod
    async def database_ok(self) -> bool:
        pass

    @abstractmethod
    async def checkpointer_ok(self) -> bool:
        pass
