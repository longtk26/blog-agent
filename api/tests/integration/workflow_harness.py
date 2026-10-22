import asyncio
import uuid

from src.configs import config
from src.libs.database import run_in_session
from src.libs.events import TaskEventBroker
from src.modules.agent.graph.blog_graph import build_blog_graph
from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.infrastructure.adapters import LangGraphWorkflowRunner, LangSmithTracing, WorkflowStore
from src.modules.articles.infrastructure.persistence import DraftRepository, EvaluationRepository, RevisionRepository
from src.modules.research.infrastructure.persistence import BriefRepository, ClaimRepository, SourceRepository
from src.modules.shared.domain.entities import TaskMode, WritingTaskEntity
from src.modules.tasks.infrastructure.persistence import TaskEventRepository, TaskRepository
from tests.fakes import FakeExtractor, FakeModelFactory, FakeSearchProvider, WritingScript


class Harness:
    def __init__(self, checkpointer, extractor: FakeExtractor | None = None, responder=None):
        self.script = responder or WritingScript()
        self.broker = TaskEventBroker()
        self.store = WorkflowStore(self.broker)
        self.models = FakeModelFactory(self.script)
        self.search = FakeSearchProvider()
        self.extractor = extractor or FakeExtractor()
        deps = WorkflowDeps(store=self.store, models=self.models, search=self.search, extractor=self.extractor, settings=config)
        self.graph = build_blog_graph(deps, checkpointer.saver)
        self.runner = LangGraphWorkflowRunner(self.graph, self.store, LangSmithTracing(config), 2, [])

    def create_task(self, mode: TaskMode = TaskMode.RESEARCH_ONLY, **fields) -> uuid.UUID:
        entity = WritingTaskEntity(topic="How LoRA fine-tuning works", mode=mode, **fields)
        return run_in_session(lambda s: TaskRepository(s).create(entity)).id

    async def wait(self, task_id: uuid.UUID, timeout: float = 20) -> None:
        running = self.runner._running.get(str(task_id))
        if running is not None:
            await asyncio.wait_for(asyncio.shield(running), timeout)

    async def run(self, task_id: uuid.UUID) -> None:
        await self.runner.start(str(task_id))
        await self.wait(task_id)

    def task(self, task_id):
        return run_in_session(lambda s: TaskRepository(s).get(task_id))

    def sources(self, task_id):
        return run_in_session(lambda s: SourceRepository(s).list_by_task(task_id))

    def claims(self, task_id):
        return run_in_session(lambda s: ClaimRepository(s).list_by_task(task_id))

    def brief(self, task_id):
        return run_in_session(lambda s: BriefRepository(s).get_by_task(task_id))

    def events(self, task_id):
        return run_in_session(lambda s: TaskEventRepository(s).list_after(task_id, 0, 5000))

    def revisions(self, task_id):
        return run_in_session(lambda s: RevisionRepository(s).list_by_task(task_id))

    def evaluations(self, revision_id):
        return run_in_session(lambda s: EvaluationRepository(s).list_by_revision(revision_id))

    def draft(self, task_id):
        return run_in_session(lambda s: DraftRepository(s).get(task_id))
