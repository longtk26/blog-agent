from enum import StrEnum

from src.libs.exceptions import BadRequestException, ErrorCode


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RESEARCHING = "researching"
    OUTLINING = "outlining"
    DRAFTING = "drafting"
    GENERATING_DIAGRAM = "generating_diagram"
    VALIDATING = "validating"
    AWAITING_REVIEW = "awaiting_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PARTIALLY_PUBLISHED = "partially_published"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


S = TaskStatus

# Server-enforced state machine (pdm/epic2_research_workflow). `rejected` doubles as "cancelled".
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    S.QUEUED: frozenset({S.RESEARCHING, S.FAILED, S.REJECTED}),
    # RESEARCHING -> DRAFTING: follow-up research requested in review goes straight to rewriting sections.
    S.RESEARCHING: frozenset({S.OUTLINING, S.DRAFTING, S.COMPLETED, S.FAILED, S.REJECTED}),
    S.OUTLINING: frozenset({S.DRAFTING, S.AWAITING_REVIEW, S.FAILED, S.REJECTED}),
    S.DRAFTING: frozenset({S.GENERATING_DIAGRAM, S.VALIDATING, S.FAILED, S.REJECTED}),
    S.GENERATING_DIAGRAM: frozenset({S.VALIDATING, S.FAILED, S.REJECTED}),
    S.VALIDATING: frozenset({S.DRAFTING, S.AWAITING_REVIEW, S.FAILED, S.REJECTED}),
    S.AWAITING_REVIEW: frozenset({S.REVISION_REQUESTED, S.APPROVED, S.REJECTED}),
    # REVISION_REQUESTED -> AWAITING_REVIEW: a revision request lost to an API restart is handed back to the owner.
    S.REVISION_REQUESTED: frozenset(
        {S.RESEARCHING, S.OUTLINING, S.DRAFTING, S.GENERATING_DIAGRAM, S.AWAITING_REVIEW, S.FAILED, S.REJECTED}
    ),
    S.APPROVED: frozenset({S.PUBLISHING, S.AWAITING_REVIEW, S.REJECTED}),
    S.PUBLISHING: frozenset({S.PUBLISHED, S.PARTIALLY_PUBLISHED, S.FAILED}),
    S.PARTIALLY_PUBLISHED: frozenset({S.PUBLISHING, S.AWAITING_REVIEW}),
    S.PUBLISHED: frozenset({S.AWAITING_REVIEW}),
    S.COMPLETED: frozenset({S.OUTLINING, S.REJECTED}),
    # From failed, a retry returns to the stage stored in `failed_stage` (checked separately).
    S.FAILED: frozenset(
        {
            S.QUEUED, S.RESEARCHING, S.OUTLINING, S.DRAFTING, S.GENERATING_DIAGRAM, S.VALIDATING,
            S.REVISION_REQUESTED, S.PUBLISHING, S.REJECTED,
        }
    ),
    S.REJECTED: frozenset(),
}

# A runner is expected to be executing the graph while a task is in one of these.
# Owner content edits are allowed here; on anything but awaiting_review they void approvals (Epic 4, E4-S7).
EDITABLE_STATUSES = frozenset({S.AWAITING_REVIEW, S.APPROVED, S.PUBLISHED, S.PARTIALLY_PUBLISHED})

ACTIVE_STATUSES = frozenset(
    {S.RESEARCHING, S.OUTLINING, S.DRAFTING, S.GENERATING_DIAGRAM, S.VALIDATING, S.REVISION_REQUESTED, S.PUBLISHING}
)
CANCELLABLE_STATUSES = frozenset(
    {S.QUEUED, S.AWAITING_REVIEW, S.APPROVED, S.COMPLETED, S.FAILED} | (ACTIVE_STATUSES - {S.PUBLISHING})
)


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return TaskStatus(target) in ALLOWED_TRANSITIONS[TaskStatus(current)]


def ensure_transition(current: TaskStatus, target: TaskStatus, failed_stage: TaskStatus | None = None) -> None:
    current, target = TaskStatus(current), TaskStatus(target)
    allowed = can_transition(current, target)
    if allowed and current == S.FAILED and target != S.REJECTED:
        allowed = failed_stage is not None and TaskStatus(failed_stage) == target
    if not allowed:
        raise BadRequestException(
            f"Task cannot move from '{current.value}' to '{target.value}'", code=ErrorCode.INVALID_TRANSITION
        )
