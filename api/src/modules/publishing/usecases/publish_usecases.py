import threading
import uuid
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlmodel import Session

from src.configs import config
from src.configs.logger import get_logger
from src.libs.database.session import SessionDep
from src.libs.events import EventBrokerDep
from src.libs.exceptions import (
    BadRequestException,
    ConflictException,
    ErrorCode,
    ForbiddenException,
    NotFoundException,
)
from src.modules.agent.ports.output import IWorkflowRunnerDep
from src.modules.articles.ports.output import IRevisionRepoDep
from src.modules.publishing.domain import BlogsExporter
from src.modules.publishing.infrastructure.adapters import PublisherRegistryDep
from src.modules.publishing.infrastructure.persistence import IPublicationRepoDep
from src.modules.publishing.presenter.dtos import (
    PublicationDto,
    PublicationListResponseDto,
    PublishRequestDto,
    UnpublishRequestDto,
)
from src.modules.reviews.domain.approval_gate import ApprovalGate
from src.modules.reviews.ports.output import IApprovalRepoDep
from src.modules.shared.domain.entities import (
    EventActor,
    PublicationEntity,
    PublicationStatus,
    PublicationTarget,
)
from src.modules.shared.domain.value_objects import TaskStatus
from src.modules.shared.infrastructure.models._columns import utcnow
from src.modules.tasks.domain.task_transitions import TaskTransitioner
from src.modules.tasks.ports.output import ITaskEventRepoDep, ITaskRepoDep

logger = get_logger(__name__)

_ACTIVE_TASK_LOCKS: set[uuid.UUID] = set()
_LOCK = threading.Lock()


@contextmanager
def task_publish_lock(session: Session, task_id: uuid.UUID):
    with _LOCK:
        if task_id in _ACTIVE_TASK_LOCKS:
            raise ConflictException(
                f"Publishing is already in progress for task '{task_id}'", code=ErrorCode.TASK_RUNNING
            )
        _ACTIVE_TASK_LOCKS.add(task_id)

    engine = session.get_bind() if hasattr(session, "get_bind") else session.bind
    is_pg = engine is not None and getattr(engine.dialect, "name", "") == "postgresql"
    lock_conn = None
    lock_id = int.from_bytes(task_id.bytes[:8], byteorder="big", signed=True) if is_pg else 0

    if is_pg and engine is not None:
        lock_conn = engine.connect()
        try:
            res = lock_conn.execute(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": lock_id}).scalar()
            if not res:
                lock_conn.close()
                lock_conn = None
                with _LOCK:
                    _ACTIVE_TASK_LOCKS.discard(task_id)
                raise ConflictException(
                    f"Publishing is already in progress for task '{task_id}'", code=ErrorCode.TASK_RUNNING
                )
        except Exception:
            if lock_conn is not None:
                lock_conn.close()
                lock_conn = None
            with _LOCK:
                _ACTIVE_TASK_LOCKS.discard(task_id)
            raise

    try:
        yield
    finally:
        if lock_conn is not None:
            try:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": lock_id})
            except Exception:
                pass
            finally:
                lock_conn.close()
        with _LOCK:
            _ACTIVE_TASK_LOCKS.discard(task_id)


class PublishRevisionUsecase:
    """E5-S1: Publish an approved revision enforcing the approval gate and idempotency."""

    def __init__(
        self,
        tasks: ITaskRepoDep,
        events: ITaskEventRepoDep,
        revisions: IRevisionRepoDep,
        approvals: IApprovalRepoDep,
        publications: IPublicationRepoDep,
        publishers: PublisherRegistryDep,
        runner: IWorkflowRunnerDep,
        broker: EventBrokerDep,
        session: SessionDep,
    ):
        self.tasks = tasks
        self.events = events
        self.revisions = revisions
        self.approvals = approvals
        self.publications = publications
        self.publishers = publishers
        self.runner = runner
        self.broker = broker
        self.session = session
        self.transitioner = TaskTransitioner(tasks, events)
        self.gate = ApprovalGate(approvals, revisions)
        self.blogs_exporter = BlogsExporter(config.blogs_dir, enabled=config.blogs_export_enabled)

    async def execute(self, revision_id: uuid.UUID, dto: PublishRequestDto) -> PublicationListResponseDto:
        revision = self.revisions.get(revision_id)
        if revision is None:
            raise NotFoundException(f"Revision '{revision_id}' not found")
        task_id = revision.task_id

        # 1. Gate check for every requested destination before touching task or publications
        destination_approvals: dict[PublicationTarget, Any] = {}
        for destination in dto.destinations:
            gate_res = self.gate.check(revision_id, destination)
            if not gate_res.passed:
                if gate_res.reason == "not_approved":
                    raise ForbiddenException(
                        f"Revision r{revision.revision_number} is not approved for '{destination}'",
                        code=ErrorCode.APPROVAL_REQUIRED,
                    )
                elif gate_res.reason == "not_latest":
                    raise ForbiddenException(
                        f"Revision r{revision.revision_number} is stale. Only the latest approved revision can be published.",
                        code=ErrorCode.APPROVAL_STALE,
                    )
                elif gate_res.reason == "hash_mismatch":
                    raise ForbiddenException(
                        "The content changed since approval (hash mismatch). Please review and approve again.",
                        code=ErrorCode.HASH_MISMATCH,
                    )
                elif gate_res.reason == "not_found":
                    raise NotFoundException(f"Revision '{revision_id}' not found")
                else:
                    raise ForbiddenException(f"Approval gate failed: {gate_res.reason}", code=ErrorCode.FORBIDDEN)

            destination_approvals[destination] = gate_res.approval

            # E8-S4: Dev.to draft vs live mode bound to approval
            if destination == PublicationTarget.DEVTO and gate_res.approval:
                approved_mode = (
                    gate_res.approval.options.get("mode")
                    or gate_res.approval.options.get("devto_mode")
                    or "draft"
                )
                requested_mode = (
                    dto.options.get("mode")
                    or dto.options.get("devto_mode")
                )
                if requested_mode and requested_mode != approved_mode:
                    raise ForbiddenException(
                        f"Revision r{revision.revision_number} was approved for Dev.to with mode '{approved_mode}', not '{requested_mode}'. Please review and approve with mode '{requested_mode}'.",
                        code=ErrorCode.FORBIDDEN,
                    )

        # Idempotency: If all requested destinations already succeeded for this revision, return existing results
        existing_pubs = [self.publications.get_by_task_and_destination(task_id, d) for d in dto.destinations]
        if all(p and p.status == PublicationStatus.SUCCEEDED and p.article_revision_id == revision.id for p in existing_pubs):
            return PublicationListResponseDto(items=[PublicationDto.from_entity(p) for p in existing_pubs if p])

        # 2. Prevent concurrent publishes via advisory lock
        with task_publish_lock(self.session, task_id):
            task = self.tasks.get(task_id, for_update=True)
            if task is None:
                raise NotFoundException(f"Task '{task_id}' not found")

            if task.status == TaskStatus.PUBLISHING:
                raise ConflictException("Publishing is already in progress for this task", code=ErrorCode.TASK_RUNNING)

            # Move task to PUBLISHING
            self.transitioner.transition(
                task_id, TaskStatus.PUBLISHING, actor=EventActor.OWNER, reason="publishing_started"
            )
            self.transitioner.record(
                task_id,
                "publishing_started",
                {"revision_id": str(revision.id), "destinations": [str(d) for d in dto.destinations]},
                actor=EventActor.OWNER,
            )
            self.broker.notify(task_id)

            results: list[PublicationEntity] = []

            for destination in dto.destinations:
                pub = self.publications.get_by_task_and_destination(task_id, destination)

                # Idempotency: Retrying a destination that already succeeded for the same revision is a no-op
                if pub and pub.status == PublicationStatus.SUCCEEDED and pub.article_revision_id == revision.id:
                    results.append(pub)
                    continue

                if pub is None:
                    pub = PublicationEntity(
                        task_id=task_id,
                        article_revision_id=revision.id,
                        destination=destination,
                        status=PublicationStatus.PENDING,
                        attempt_count=1,
                    )
                else:
                    pub.article_revision_id = revision.id
                    pub.status = PublicationStatus.PENDING
                    pub.attempt_count += 1

                pub = self.publications.save(pub)
                self.session.commit()
                self.broker.notify(task_id)

                publisher = self.publishers.get(destination)
                if publisher is None:
                    pub.status = PublicationStatus.FAILED
                    pub.last_error = f"No publisher registered for destination '{destination}'"
                    pub.updated_at = utcnow()
                    self.publications.save(pub)
                    self.session.commit()
                    results.append(pub)
                    continue

                existing_remote_id = pub.remote_document_id

                def on_asset(original_src: str, asset_ref: str, url: str):
                    self.transitioner.record(
                        task_id,
                        "asset_uploaded",
                        {"original_src": original_src, "asset_ref": asset_ref, "url": url},
                        actor=EventActor.AGENT,
                    )
                    self.session.commit()
                    self.broker.notify(task_id)

                pub_options = dict(dto.options or {})
                appr = destination_approvals.get(destination)
                if appr and appr.options:
                    appr_mode = appr.options.get("mode") or appr.options.get("devto_mode")
                    if appr_mode:
                        pub_options["mode"] = appr_mode
                        pub_options["devto_mode"] = appr_mode

                try:
                    outcome = await publisher.publish(
                        task_id=task_id,
                        revision=revision,
                        existing_remote_id=existing_remote_id,
                        on_asset_uploaded=on_asset,
                        options=pub_options,
                    )

                    pub.status = PublicationStatus.SUCCEEDED
                    pub.remote_document_id = outcome.remote_document_id
                    pub.remote_url = outcome.remote_url
                    pub.rendered_content_hash = outcome.rendered_content_hash
                    pub.published_at = pub.published_at or utcnow()
                    pub.updated_at = utcnow()
                    pub.last_error = None
                    self.publications.save(pub)

                    if destination == PublicationTarget.SANITY and outcome.rendered_markdown:
                        self.blogs_exporter.export(
                            revision, outcome.remote_document_id, outcome.rendered_markdown
                        )

                    self.transitioner.record(
                        task_id,
                        "publish_succeeded",
                        {
                            "destination": str(destination),
                            "remote_document_id": outcome.remote_document_id,
                            "remote_url": outcome.remote_url,
                            "rendered_content_hash": outcome.rendered_content_hash[:12] if outcome.rendered_content_hash else None,
                        },
                        actor=EventActor.AGENT,
                    )
                    self.session.commit()
                    self.broker.notify(task_id)
                    results.append(pub)

                except Exception as exc:
                    err_msg = str(exc)
                    logger.exception(f"Publish failed for task {task_id} {destination}: {err_msg}")
                    pub.status = PublicationStatus.FAILED
                    pub.last_error = err_msg
                    pub.updated_at = utcnow()
                    self.publications.save(pub)

                    self.transitioner.record(
                        task_id,
                        "publish_failed",
                        {"destination": str(destination), "error": err_msg},
                        actor=EventActor.AGENT,
                    )
                    self.session.commit()
                    self.broker.notify(task_id)
                    results.append(pub)

            # Determine final task status
            succeeded = [r for r in results if r.status == PublicationStatus.SUCCEEDED]
            failed = [r for r in results if r.status == PublicationStatus.FAILED]

            if len(succeeded) == len(results):
                self.transitioner.transition(
                    task_id, TaskStatus.PUBLISHED, actor=EventActor.AGENT, reason="publish_succeeded"
                )
            elif len(succeeded) > 0:
                self.transitioner.transition(
                    task_id, TaskStatus.PARTIALLY_PUBLISHED, actor=EventActor.AGENT, reason="partially_published"
                )
            else:
                first_err = failed[0].last_error if failed else "Publishing failed"
                self.transitioner.transition(
                    task_id,
                    TaskStatus.FAILED,
                    actor=EventActor.AGENT,
                    failed_stage=TaskStatus.PUBLISHING,
                    error=first_err,
                    resumable=True,
                )
            self.session.commit()
            self.broker.notify(task_id)

            # If workflow runner is paused at await_publish, resume it so it completes cleanly to END
            try:
                pending = await self.runner.pending_interrupt(str(task_id))
                if pending and pending.get("type") == "awaiting_publish":
                    await self.runner.resume(
                        str(task_id), {"action": "publish", "destinations": [str(d) for d in dto.destinations]}
                    )
            except Exception as resume_err:
                logger.warning(f"Failed to resume workflow runner after publish: {resume_err}")

            return PublicationListResponseDto(items=[PublicationDto.from_entity(p) for p in results])


class RetryPublicationUsecase:
    """E5-S5: Retry a failed publication destination."""

    def __init__(
        self,
        tasks: ITaskRepoDep,
        revisions: IRevisionRepoDep,
        publish_usecase: Annotated[PublishRevisionUsecase, Depends(PublishRevisionUsecase)],
    ):
        self.tasks = tasks
        self.revisions = revisions
        self.publish_usecase = publish_usecase

    async def execute(self, task_id: uuid.UUID, destination: PublicationTarget) -> PublicationListResponseDto:
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        latest = self.revisions.latest(task_id)
        if latest is None:
            raise NotFoundException(f"No revision found for task '{task_id}'")
        return await self.publish_usecase.execute(latest.id, PublishRequestDto(destinations=[destination]))


class ListPublicationsUsecase:
    """E5-S5: List all publication records for a task."""

    def __init__(self, tasks: ITaskRepoDep, publications: IPublicationRepoDep):
        self.tasks = tasks
        self.publications = publications

    async def execute(self, task_id: uuid.UUID) -> PublicationListResponseDto:
        if self.tasks.get(task_id) is None:
            raise NotFoundException(f"Task '{task_id}' not found")
        records = self.publications.list_by_task(task_id)
        return PublicationListResponseDto(items=[PublicationDto.from_entity(p) for p in records])


class UnpublishUsecase:
    """E5-S6: Destructive action to delete post from remote destination."""

    def __init__(
        self,
        tasks: ITaskRepoDep,
        events: ITaskEventRepoDep,
        revisions: IRevisionRepoDep,
        publications: IPublicationRepoDep,
        publishers: PublisherRegistryDep,
        broker: EventBrokerDep,
        session: SessionDep,
    ):
        self.tasks = tasks
        self.events = events
        self.revisions = revisions
        self.publications = publications
        self.publishers = publishers
        self.broker = broker
        self.session = session
        self.transitioner = TaskTransitioner(tasks, events)
        self.blogs_exporter = BlogsExporter(config.blogs_dir, enabled=config.blogs_export_enabled)

    async def execute(self, task_id: uuid.UUID, dto: UnpublishRequestDto) -> PublicationListResponseDto:
        task = self.tasks.get(task_id)
        if task is None:
            raise NotFoundException(f"Task '{task_id}' not found")

        latest = self.revisions.latest(task_id)
        expected_slug = latest.slug if latest else None

        # Verify confirmation slug
        if dto.slug != expected_slug:
            raise BadRequestException(
                f"Slug confirmation mismatch: expected '{expected_slug}', got '{dto.slug}'",
                code=ErrorCode.VALIDATION_ERROR,
            )

        for destination in dto.destinations:
            pub = self.publications.get_by_task_and_destination(task_id, destination)
            if pub and pub.remote_document_id:
                publisher = self.publishers.get(destination)
                if publisher:
                    try:
                        await publisher.unpublish(pub.remote_document_id)
                    except Exception as err:
                        logger.error(f"Failed to unpublish {pub.remote_document_id} from {destination}: {err}")
                        raise

                if destination == PublicationTarget.SANITY and latest:
                    series_name = (
                        (latest.metadata or {}).get("series", {}).get("name")
                        if isinstance((latest.metadata or {}).get("series"), dict)
                        else None
                    )
                    folder_name = series_name or latest.slug
                    self.blogs_exporter.remove_meta(folder_name, latest.slug)

                self.publications.delete(pub.id)
                self.transitioner.record(
                    task_id,
                    "unpublished",
                    {"destination": str(destination), "remote_document_id": pub.remote_document_id, "slug": dto.slug},
                    actor=EventActor.OWNER,
                )

        self.session.commit()
        self.broker.notify(task_id)

        remaining = self.publications.list_by_task(task_id)
        return PublicationListResponseDto(items=[PublicationDto.from_entity(p) for p in remaining])


PublishRevisionUsecaseDep = Annotated[PublishRevisionUsecase, Depends(PublishRevisionUsecase)]
RetryPublicationUsecaseDep = Annotated[RetryPublicationUsecase, Depends(RetryPublicationUsecase)]
ListPublicationsUsecaseDep = Annotated[ListPublicationsUsecase, Depends(ListPublicationsUsecase)]
UnpublishUsecaseDep = Annotated[UnpublishUsecase, Depends(UnpublishUsecase)]
