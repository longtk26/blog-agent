import uuid
from dataclasses import dataclass

from src.modules.articles.domain.content_hash import revision_content_hash
from src.modules.articles.ports.output import IRevisionRepository
from src.modules.reviews.ports.output import IApprovalRepository
from src.modules.shared.domain.entities import ApprovalEntity, PublicationTarget


@dataclass
class GateResult:
    passed: bool
    reason: str | None = None          # not_found | not_latest | not_approved | hash_mismatch
    approval: ApprovalEntity | None = None


class ApprovalGate:
    """The only check that unlocks publishing (Epic 5): this exact content, approved for this destination."""

    def __init__(self, approvals: IApprovalRepository, revisions: IRevisionRepository):
        self.approvals = approvals
        self.revisions = revisions

    def check(self, revision_id: uuid.UUID, destination: PublicationTarget) -> GateResult:
        revision = self.revisions.get(revision_id)
        if revision is None:
            return GateResult(False, "not_found")
        latest = self.revisions.latest(revision.task_id)
        if latest is None or latest.id != revision.id:
            return GateResult(False, "not_latest")
        approval = self.approvals.get_live(revision_id, destination)
        if approval is None:
            return GateResult(False, "not_approved")
        recomputed = revision_content_hash(revision)
        if approval.content_hash != recomputed or revision.content_hash != recomputed:
            return GateResult(False, "hash_mismatch", approval)
        return GateResult(True, None, approval)
