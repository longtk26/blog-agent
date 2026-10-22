import asyncio
from collections import defaultdict
from typing import Annotated

from fastapi import Depends


class TaskEventBroker:
    """In-process wake-up signal per task. Events themselves are persisted in `task_events`;
    the broker only tells live SSE streams that something new is there to read."""

    def __init__(self):
        self._events: dict[str, asyncio.Event] = defaultdict(asyncio.Event)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def snapshot(self, task_id: str) -> asyncio.Event:
        return self._events[str(task_id)]

    def notify(self, task_id: str) -> None:
        task_id = str(task_id)
        if self._loop is not None and self._loop.is_running():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is not self._loop:
                self._loop.call_soon_threadsafe(self._notify, task_id)
                return
        self._notify(task_id)

    def _notify(self, task_id: str) -> None:
        event = self._events.pop(task_id, None)
        if event is not None:
            event.set()


event_broker = TaskEventBroker()


def get_event_broker() -> TaskEventBroker:
    return event_broker


EventBrokerDep = Annotated[TaskEventBroker, Depends(get_event_broker)]
