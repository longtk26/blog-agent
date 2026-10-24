import uuid
from typing import Annotated

from fastapi import Depends

from src.configs import config
from src.configs.logger import get_logger
from src.libs.decorators.transactional_decorator import Transactional
from src.libs.events import EventBrokerDep
from src.libs.exceptions import BadRequestException, ConflictException, ErrorCode, NotFoundException
from src.modules.agent.ports.output import ITracingDep, IWorkflowRunnerDep
from src.modules.articles.domain.content_hash import compute_content_hash, revision_content_hash
from src.modules.articles.domain.markdown_tools import changed_sections, draft_sections_from_markdown
from src.modules.articles.domain.validators import ValidationContext, has_blockers, validate_article
from src.modules.articles.ports.output import IDraftRepoDep, IEvaluationRepoDep, IRevisionRepoDep
from src.modules.articles.presenter.dtos import RevisionResponseDto
from src.modules.research.ports.output import ISourceRepoDep
from src.modules.reviews.ports.output import IApprovalRepoDep
from src.modules.reviews.presenter.dtos import (
    ApprovalDto,
    ApprovalListResponseDto,
    CreateApprovalDto,
    CreateOwnerRevisionDto,
    ReviewRequestDto,
)
from src.modules.shared.domain.entities import (
    ApprovalEntity,
    ArticleDraftEntity,
    ArticleRevisionEntity,
    EvaluationResultEntity,
    EventActor,
    IssueSeverity,
    PublicationTarget,
    RevisionAuthor,
    SourceStatus,
    WritingTaskEntity,
)
from src.modules.shared.domain.value_objects import CANCELLABLE_STATUSES, EDITABLE_STATUSES, TaskStatus
from src.modules.tasks.domain.task_transitions import TaskTransitioner
from src.modules.tasks.ports.output import ITaskEventRepoDep, ITaskRepoDep
from src.modules.tasks.presenter.dtos import TaskResponseDto

logger = get_logger(__name__)

# Revision metadata an owner edit carries over from the revision it was based on.
_CARRIED_METADATA = ("outline", "style_guide_version", "render_contract_version", "prompt_version", "models")


class _Review():
    def __init__(
        self,
        tasks: ITaskRepoDep,
        events: ITaskEventRepoDep,
        revisions: IRevisionRepoDep,
        evaluations: IEvaluationRepoDep,
        approvals: IApprovalRepoDep,
        runner: IWorkflowRunnerDep,
        tracing: ITracingDep,
        broker: EventBrokerDep,
    ):
        self.tasks = tasks
        self.events = events
        self.revisions = revisions
        self.evaluations = evaluations
        self.approvals = approvals
        self.runner = runner
        self.tracing = tracing
        self.broker = broker
        self.transitioner = TaskTransitioner(tasks, events)

    def _get_task(self, task_id: uuid.UUID, for_update: bool = False) -> WritingTaskEntity:
        task = self.tasks.get(task_id, for_update=for_update)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        return task

    def _ensure_idle(self, task_id: uuid.UUID) -> None:
        if self.runner.is_running(str(task_id)):
            raise ConflictException("The task is running; wait for it to stop or cancel it", code=ErrorCode.TASK_RUNNING)

    def _latest(self, task_id: uuid.UUID, expected_id: uuid.UUID) -> ArticleRevisionEntity:
        latest = self.revisions.latest(task_id)
        if latest is None:
            raise ConflictException("The task has no revision yet", code=ErrorCode.NOTHING_TO_RESUME)
        if latest.id != expected_id:
            raise ConflictException(
                f"Revision r{latest.revision_number} is newer than the one you reviewed; reload and try again",
                code=ErrorCode.STALE_REVISION,
            )
        return latest

    async def _pending_type(self, task_id: uuid.UUID) -> str | None:
        return (await self.runner.pending_interrupt(str(task_id)) or {}).get("type")

    def _feedback(self, task: WritingTaskEntity, score: float, comment: str | None, value: dict) -> None:
        if task.last_run_id:
            self.tracing.record_feedback(task.last_run_id, "owner_review", score=score, comment=comment, value=value)


class CreateOwnerRevisionUsecase(_Review):
    """E4-S3: the owner's own edit becomes a new immutable revision (deterministic checks only, no LLM)."""

    def __init__(
        self,
        tasks: ITaskRepoDep,
        events: ITaskEventRepoDep,
        revisions: IRevisionRepoDep,
        evaluations: IEvaluationRepoDep,
        approvals: IApprovalRepoDep,
        runner: IWorkflowRunnerDep,
        tracing: ITracingDep,
        broker: EventBrokerDep,
        drafts: IDraftRepoDep,
        sources: ISourceRepoDep,
    ):
        super().__init__(tasks, events, revisions, evaluations, approvals, runner, tracing, broker)
        self.drafts = drafts
        self.sources = sources

    async def execute(self, task_id: uuid.UUID, dto: CreateOwnerRevisionDto) -> RevisionResponseDto:
        self._ensure_idle(task_id)
        waiting_to_publish = await self._pending_type(task_id) == "awaiting_publish"
        revision, evaluation, reopened = self._create(task_id, dto)
        self.broker.notify(task_id)
        if reopened and waiting_to_publish:
            # The approval is void; move the thread from "waiting to publish" back to "waiting for review".
            await self.runner.resume(str(task_id), {"action": "reopen", "revision_id": str(revision.id)})
        return RevisionResponseDto.from_entity(revision, [evaluation])

    @Transactional
    def _create(self, task_id: uuid.UUID, dto: CreateOwnerRevisionDto):
        task = self._get_task(task_id, for_update=True)  # row lock: concurrent saves serialise here
        if task.status not in EDITABLE_STATUSES:
            raise ConflictException(f"A task in '{task.status}' cannot be edited", code=ErrorCode.INVALID_TRANSITION)
        base = self._latest(task_id, dto.base_revision_id)
        meta = dto.metadata.to_entity()
        markdown = dto.markdown.replace("\r\n", "\n").rstrip() + "\n"
        content_hash = compute_content_hash(
            title=meta.title, slug=meta.slug, description=meta.description, tags=meta.tags, markdown=markdown
        )
        if content_hash == base.content_hash:
            raise BadRequestException("Nothing changed compared to the latest revision", code=ErrorCode.NO_CHANGES)
        if self.revisions.slug_taken(meta.slug, task_id):
            raise ConflictException(f"The slug '{meta.slug}' is used by another task", code=ErrorCode.SLUG_TAKEN)

        outline = task.outline or base.metadata.get("outline") or {}
        sources = self.sources.list_by_task(task_id, [SourceStatus.ASSESSED, SourceStatus.LOW_QUALITY])
        issues = validate_article(
            markdown,
            ValidationContext(
                format=str(task.format),
                metadata=meta,
                source_urls={u for s in sources for u in (s.url, s.canonical_url)},
                must_cover=outline.get("must_cover", []),
                covered_requirements=set(outline.get("covered_requirements", [])),
                expected_words=None,
            ),
        )
        draft = self.drafts.get(task_id) or ArticleDraftEntity(task_id=task_id)
        draft.sections = draft_sections_from_markdown(markdown, draft.sections)
        draft.metadata = meta
        draft.markdown = markdown
        draft.issues = issues
        draft.judge = None  # the judge saw older text
        draft.self_revisions = 0
        self.drafts.save(draft)

        changed = changed_sections(base.markdown, markdown)
        revision = self.revisions.create(
            ArticleRevisionEntity(
                task_id=task_id,
                revision_number=base.revision_number + 1,
                parent_revision_id=base.id,
                title=meta.title,
                slug=meta.slug,
                description=meta.description,
                tags=meta.tags,
                markdown=markdown,
                created_by=RevisionAuthor.OWNER,
                content_hash=content_hash,
                metadata={
                    **{k: base.metadata[k] for k in _CARRIED_METADATA if k in base.metadata},
                    "claim_map": {s.key: s.claim_map for s in draft.sections if s.claim_map},
                    "unsupported_statements": [
                        u for u in base.metadata.get("unsupported_statements", []) if u[:40] and u[:40] in markdown
                    ],
                    "word_count": len(markdown.split()),
                    "sections_changed": changed,
                },
            )
        )
        [evaluation] = self.evaluations.add_many(
            [EvaluationResultEntity(revision_id=revision.id, kind="deterministic", passed=not has_blockers(issues), issues=issues)]
        )

        superseded = self.approvals.supersede_for_task(task_id)
        reopened = task.status != TaskStatus.AWAITING_REVIEW
        if reopened:
            self.transitioner.transition(task_id, TaskStatus.AWAITING_REVIEW, actor=EventActor.OWNER, reason="owner_edit")
        self.transitioner.record(
            task_id,
            "revision_saved",
            {
                "revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "content_hash": content_hash[:12],
                "created_by": "owner",
                "sections_changed": changed,
                "superseded_approvals": superseded,
            },
            actor=EventActor.OWNER,
        )
        return revision, evaluation, reopened


class ReviewTaskUsecase(_Review):
    """E4-S5 / E4-S8: request an AI revision with feedback, or reject the task (ends the workflow thread)."""

    async def execute(self, task_id: uuid.UUID, dto: ReviewRequestDto) -> TaskResponseDto:
        if dto.action == "revise":
            return await self._revise(task_id, dto)
        return await self._reject(task_id, dto)

    async def _revise(self, task_id: uuid.UUID, dto: ReviewRequestDto) -> TaskResponseDto:
        task = self._get_task(task_id)
        self._ensure_idle(task_id)
        if task.status != TaskStatus.AWAITING_REVIEW:
            raise ConflictException(f"A task in '{task.status}' is not waiting for review", code=ErrorCode.INVALID_TRANSITION)
        if await self._pending_type(task_id) != "awaiting_review":
            raise ConflictException("The workflow is not waiting for a review decision", code=ErrorCode.NOTHING_TO_RESUME)
        rounds = sum(1 for r in self.revisions.list_by_task(task_id) if r.metadata.get("review"))
        if rounds >= config.max_review_rounds:
            raise ConflictException(
                f"This task already had {rounds} AI revision rounds (limit {config.max_review_rounds}); edit it yourself or clone it",
                code=ErrorCode.REVIEW_ROUNDS_EXCEEDED,
            )

        command = {
            "action": "revise",
            "revision_id": str(dto.revision_id),
            "feedback": dto.feedback.strip(),
            "scope": dto.scope.model_dump(),
            "round": rounds + 1,
        }
        task = self._request(task_id, dto, command)
        self.broker.notify(task_id)
        self._feedback(task, 0, command["feedback"], {"action": "revise", "target": dto.scope.target, "round": command["round"]})
        await self.runner.resume(str(task_id), command)
        return TaskResponseDto.from_entity(task, is_running=True)

    @Transactional
    def _request(self, task_id: uuid.UUID, dto: ReviewRequestDto, command: dict) -> WritingTaskEntity:
        self._get_task(task_id, for_update=True)
        self._latest(task_id, dto.revision_id)
        self.transitioner.record(
            task_id,
            "revision_requested",
            {"feedback": command["feedback"][:500], "scope": command["scope"], "round": command["round"]},
            actor=EventActor.OWNER,
        )
        return self.transitioner.transition(
            task_id, TaskStatus.REVISION_REQUESTED, actor=EventActor.OWNER, reason="revision_requested"
        )

    async def _reject(self, task_id: uuid.UUID, dto: ReviewRequestDto) -> TaskResponseDto:
        task = self._get_task(task_id)
        if task.status not in CANCELLABLE_STATUSES:
            raise BadRequestException(f"A task in '{task.status}' cannot be rejected", code=ErrorCode.INVALID_TRANSITION)
        running = self.runner.is_running(str(task_id))
        pending = None if running else await self._pending_type(task_id)
        task = self._mark_rejected(task_id, dto.reason)
        self.broker.notify(task_id)
        self._feedback(task, 0, dto.reason, {"action": "reject"})
        if running:
            await self.runner.cancel(str(task_id))
        elif pending in ("awaiting_review", "awaiting_publish"):
            await self.runner.resume(str(task_id), {"action": "reject"})  # lets the thread reach END
        return TaskResponseDto.from_entity(task, is_running=False)

    @Transactional
    def _mark_rejected(self, task_id: uuid.UUID, reason: str | None) -> WritingTaskEntity:
        self.approvals.supersede_for_task(task_id)
        task = self.transitioner.transition(task_id, TaskStatus.REJECTED, actor=EventActor.OWNER, reason="rejected")
        if reason:
            self.transitioner.record(task_id, "rejected", {"reason": reason[:1000]}, actor=EventActor.OWNER)
        return task


class ApproveRevisionUsecase(_Review):
    """E4-S6: approve one exact revision (bound to its recomputed content hash) for chosen destinations."""

    async def execute(self, revision_id: uuid.UUID, dto: CreateApprovalDto) -> ApprovalListResponseDto:
        revision = self.revisions.get(revision_id)
        if revision is None:
            raise NotFoundException(f"Revision '{revision_id}' not found")
        task_id = revision.task_id
        self._ensure_idle(task_id)
        if await self._pending_type(task_id) != "awaiting_review":
            raise ConflictException("The workflow is not waiting for a review decision", code=ErrorCode.NOTHING_TO_RESUME)

        task, approvals = self._approve(revision, dto)
        self.broker.notify(task_id)
        self._feedback(
            task, 1, None, {"action": "approve", "revision": revision.revision_number, "destinations": [str(d) for d in dto.destinations]}
        )
        await self.runner.resume(str(task_id), {"action": "approve", "revision_id": str(revision.id)})
        return ApprovalListResponseDto(items=[ApprovalDto.from_entity(a) for a in approvals])

    @Transactional
    def _approve(self, revision: ArticleRevisionEntity, dto: CreateApprovalDto):
        task = self._get_task(revision.task_id, for_update=True)
        if task.status != TaskStatus.AWAITING_REVIEW:
            raise ConflictException(f"A task in '{task.status}' cannot be approved", code=ErrorCode.INVALID_TRANSITION)
        self._latest(task.id, revision.id)
        recomputed = revision_content_hash(revision)
        if recomputed != dto.content_hash or revision.content_hash != recomputed:
            raise ConflictException(
                "The content changed since you reviewed it (hash mismatch); reload and review again", code=ErrorCode.HASH_MISMATCH
            )
        blockers = [
            issue.rule
            for evaluation in self.evaluations.list_by_revision(revision.id)
            for issue in evaluation.issues
            if issue.severity == IssueSeverity.BLOCKER
        ]
        if blockers and not dto.acknowledge_blockers:
            raise ConflictException(
                f"This revision has {len(blockers)} open blocker issue(s); acknowledge them to approve anyway",
                code=ErrorCode.BLOCKERS_UNACKNOWLEDGED,
            )

        self.approvals.supersede_for_task(task.id)
        approvals = self.approvals.add_many(
            [
                ApprovalEntity(
                    task_id=task.id,
                    article_revision_id=revision.id,
                    content_hash=recomputed,
                    destination=destination,
                    options={
                        **({"devto_mode": dto.options.devto_mode} if destination == PublicationTarget.DEVTO else {}),
                        **({"acknowledged_blockers": sorted(set(blockers))} if blockers else {}),
                    },
                )
                for destination in dto.destinations
            ]
        )
        task = self.transitioner.transition(task.id, TaskStatus.APPROVED, actor=EventActor.OWNER, reason="approved")
        self.transitioner.record(
            task.id,
            "approved",
            {
                "revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "content_hash": recomputed[:12],
                "destinations": [str(d) for d in dto.destinations],
            },
            actor=EventActor.OWNER,
        )
        return task, approvals


class ListApprovalsUsecase():
    def __init__(self, tasks: ITaskRepoDep, approvals: IApprovalRepoDep):
        self.tasks = tasks
        self.approvals = approvals

    async def execute(self, task_id: uuid.UUID) -> ApprovalListResponseDto:
        if self.tasks.get(task_id) is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        return ApprovalListResponseDto(items=[ApprovalDto.from_entity(a) for a in self.approvals.list_by_task(task_id)])


CreateOwnerRevisionUsecaseDep = Annotated[CreateOwnerRevisionUsecase, Depends(CreateOwnerRevisionUsecase)]
ReviewTaskUsecaseDep = Annotated[ReviewTaskUsecase, Depends(ReviewTaskUsecase)]
ApproveRevisionUsecaseDep = Annotated[ApproveRevisionUsecase, Depends(ApproveRevisionUsecase)]
ListApprovalsUsecaseDep = Annotated[ListApprovalsUsecase, Depends(ListApprovalsUsecase)]
