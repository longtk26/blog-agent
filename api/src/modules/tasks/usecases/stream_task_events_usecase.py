import asyncio
import json
import uuid
from typing import Annotated, AsyncIterator, Awaitable, Callable
from fastapi import Depends

from src.libs.events import EventBrokerDep
from src.libs.exceptions import NotFoundException
from src.modules.agent.ports.output import IWorkflowRunnerDep, ThreadStatus
from src.modules.shared.domain.value_objects import ACTIVE_STATUSES, TaskStatus
from src.modules.tasks.ports.output import ITaskEventFeedDep
from src.modules.tasks.presenter.dtos import TaskEventDto

HEARTBEAT_SECONDS = 15.0


class StreamTaskEventsUsecase():
    """Server-Sent Events: replay persisted events after `after_id`, then push new ones live.
    The stream ends once the task is at rest (not running and not in an active status, or paused)."""

    def __init__(self, feed: ITaskEventFeedDep, runner: IWorkflowRunnerDep, broker: EventBrokerDep):
        self.feed = feed
        self.runner = runner
        self.broker = broker

    async def open(
        self, task_id: uuid.UUID, after_id: int, is_disconnected: Callable[[], Awaitable[bool]]
    ) -> AsyncIterator[str]:
        if await self.feed.status(task_id) is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        return self._stream(task_id, after_id, is_disconnected)

    async def _at_rest(self, task_id: uuid.UUID) -> TaskStatus | None:
        if self.runner.is_running(str(task_id)):
            return None
        status = await self.feed.status(task_id)
        if status == TaskStatus.QUEUED:
            return None
        if status in ACTIVE_STATUSES and await self.runner.thread_status(str(task_id)) != ThreadStatus.INTERRUPTED:
            return None
        return status

    async def _stream(
        self, task_id: uuid.UUID, after_id: int, is_disconnected: Callable[[], Awaitable[bool]]
    ) -> AsyncIterator[str]:
        last_id = after_id
        yield "retry: 3000\n\n"
        while True:
            wake = self.broker.snapshot(str(task_id))  # take before reading so no notify is missed
            events = await self.feed.events_after(task_id, last_id)
            for event in events:
                last_id = event.id
                yield f"id: {event.id}\ndata: {TaskEventDto.from_entity(event).model_dump_json()}\n\n"
            if events:
                continue

            status = await self._at_rest(task_id)
            if status is not None:
                yield f"event: end\ndata: {json.dumps({'status': str(status)})}\n\n"
                return
            try:
                await asyncio.wait_for(wake.wait(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
            if await is_disconnected():
                return


StreamTaskEventsUsecaseDep = Annotated[StreamTaskEventsUsecase, Depends(StreamTaskEventsUsecase)]
