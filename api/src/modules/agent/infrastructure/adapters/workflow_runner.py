import asyncio
import uuid
from typing import Annotated, Any

from fastapi import Depends, Request
from langgraph.types import Command

from src.configs.logger import Redactor, get_logger, task_id_ctx
from src.libs.exceptions import ConflictException, ErrorCode
from src.modules.agent.nodes.base import NodeFailed, TaskCancelled, safe_error
from src.modules.agent.ports.output.tracing import ITracing
from src.modules.agent.ports.output.workflow_runner import IWorkflowRunner, ThreadStatus
from src.modules.agent.ports.output.workflow_store import IWorkflowStore
from src.modules.agent.prompts.research import PROMPT_VERSION as RESEARCH_PROMPT_VERSION
from src.modules.shared.domain.value_objects import ACTIVE_STATUSES, TaskStatus

logger = get_logger(__name__)

PROMPT_VERSIONS = {"research": RESEARCH_PROMPT_VERSION}
RECURSION_LIMIT = 80


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


class LangGraphWorkflowRunner(IWorkflowRunner):
    """Runs one LangGraph thread per task (thread_id = task_id) as a managed asyncio task.

    Durability comes from the Postgres checkpointer: a run can stop anywhere (failure, restart,
    interrupt) and continue later from the last checkpoint.
    """

    def __init__(self, graph, store: IWorkflowStore, tracing: ITracing, max_concurrency: int, secrets: list[str]):
        self.graph = graph
        self.store = store
        self.tracing = tracing
        self.redactor = Redactor(secrets)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._running: dict[str, asyncio.Task] = {}

    @staticmethod
    def _thread(task_id: str) -> dict:
        return {"configurable": {"thread_id": task_id}}

    def is_running(self, task_id: str) -> bool:
        task = self._running.get(str(task_id))
        return task is not None and not task.done()

    async def start(self, task_id: str) -> None:
        self._launch(str(task_id), {"task_id": str(task_id)})

    async def resume(self, task_id: str, command: dict[str, Any] | None = None) -> None:
        task_id = str(task_id)
        snapshot = await self.graph.aget_state(self._thread(task_id))
        if not snapshot.values:
            # Never checkpointed (e.g. failed before the first step): start from the beginning.
            return self._launch(task_id, {"task_id": task_id})
        if not snapshot.next:
            raise ConflictException("The workflow has finished; there is nothing to resume", code=ErrorCode.NOTHING_TO_RESUME)
        self._launch(task_id, Command(resume=command) if command is not None else None)

    async def thread_status(self, task_id: str) -> ThreadStatus:
        snapshot = await self.graph.aget_state(self._thread(str(task_id)))
        if not snapshot.values:
            return ThreadStatus.NONE
        if any(task.interrupts for task in snapshot.tasks):
            return ThreadStatus.INTERRUPTED
        return ThreadStatus.PENDING if snapshot.next else ThreadStatus.FINISHED

    async def cancel(self, task_id: str) -> None:
        task = self._running.get(str(task_id))
        if task is not None and not task.done():
            task.cancel()

    def _launch(self, task_id: str, graph_input: Any) -> None:
        if self.is_running(task_id):
            raise ConflictException("The task is already running", code=ErrorCode.TASK_RUNNING)
        task = asyncio.create_task(self._run(task_id, graph_input), name=f"blog-task-{task_id}")
        self._running[task_id] = task
        task.add_done_callback(lambda _: self._running.pop(task_id, None))

    async def _run(self, task_id: str, graph_input: Any) -> None:
        async with self._semaphore:
            token = task_id_ctx.set(task_id)
            task_uuid = uuid.UUID(task_id)
            try:
                task = await self.store.get_task(task_uuid)
                run_id = uuid.uuid4()
                await self.store.update_task(task_uuid, last_run_id=run_id)
                run_config = self.tracing.run_config(
                    run_name="blog_task",
                    tags=[f"mode:{task.mode}", f"format:{task.format}"],
                    metadata={
                        "task_id": task_id,
                        "mode": str(task.mode),
                        "format": str(task.format),
                        "prompt_versions": PROMPT_VERSIONS,
                    },
                    run_id=run_id,
                    configurable={"thread_id": task_id},
                )
                run_config["recursion_limit"] = RECURSION_LIMIT
                logger.info("Workflow run started", extra={"context": {"run_id": str(run_id), "resume": graph_input is None or isinstance(graph_input, Command)}})

                async for mode, chunk in self.graph.astream(graph_input, run_config, stream_mode=["updates", "custom"]):
                    if mode == "custom" and isinstance(chunk, dict) and chunk.get("type"):
                        payload = _jsonable({k: v for k, v in chunk.items() if k != "type"})
                        await self.store.record_event(task_uuid, chunk["type"], payload)
                    elif mode == "updates" and isinstance(chunk, dict) and "__interrupt__" in chunk:
                        values = [_jsonable(getattr(i, "value", i)) for i in chunk["__interrupt__"]]
                        await self.store.record_event(task_uuid, "paused", {"interrupts": values})
                logger.info("Workflow run stopped", extra={"context": {"run_id": str(run_id)}})
            except (NodeFailed, TaskCancelled):
                pass  # already recorded by the node wrapper / cancel use case
            except asyncio.CancelledError:
                logger.info("Workflow run cancelled")
                raise
            except Exception as exc:
                logger.exception("Workflow run crashed")
                current = await self.store.get_task(task_uuid)
                await self.store.fail_task(task_uuid, current.status, safe_error(exc, self.redactor))
            finally:
                task_id_ctx.reset(token)

    async def recover(self) -> None:
        """After a restart: active tasks without a live run become failed+resumable (unless paused at an
        interrupt, which is a valid resting state), and queued tasks are started."""
        for task in await self.store.list_tasks(sorted(ACTIVE_STATUSES)):
            task_id = str(task.id)
            thread = await self.thread_status(task_id)
            if thread == ThreadStatus.INTERRUPTED:
                continue
            resumable = thread != ThreadStatus.FINISHED
            await self.store.fail_task(task.id, task.status, "Interrupted by API restart", resumable=resumable)
            logger.info("Marked interrupted task as failed", extra={"context": {"task_id": task_id, "resumable": resumable}})
        for task in await self.store.list_tasks([TaskStatus.QUEUED]):
            await self.start(str(task.id))

    async def shutdown(self, timeout: float = 5.0) -> None:
        tasks = [t for t in self._running.values() if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)


def get_workflow_runner(request: Request) -> IWorkflowRunner:
    return request.app.state.workflow_runner


IWorkflowRunnerDep = Annotated[IWorkflowRunner, Depends(get_workflow_runner)]
