import uuid

from src.modules.articles.domain.content_hash import compute_content_hash
from src.modules.reviews.domain.approval_gate import ApprovalGate
from src.modules.shared.domain.entities import (
    ApprovalDecision,
    ApprovalEntity,
    ArticleRevisionEntity,
    PublicationTarget,
)

TASK = uuid.uuid4()
SANITY, DEVTO = PublicationTarget.SANITY, PublicationTarget.DEVTO


def make_revision(number: int, markdown: str) -> ArticleRevisionEntity:
    fields = dict(title="LoRA", slug="lora", description="About LoRA.", tags=["llm"], markdown=markdown)
    return ArticleRevisionEntity(id=uuid.uuid4(), task_id=TASK, revision_number=number, content_hash=compute_content_hash(**fields), **fields)


class FakeRevisions:
    def __init__(self, *revisions):
        self.items = list(revisions)

    def get(self, revision_id):
        return next((r for r in self.items if r.id == revision_id), None)

    def latest(self, task_id):
        return max((r for r in self.items if r.task_id == task_id), key=lambda r: r.revision_number, default=None)


class FakeApprovals:
    def __init__(self):
        self.items: list[ApprovalEntity] = []

    def approve(self, revision, destination, content_hash=None):
        self.items.append(
            ApprovalEntity(
                task_id=TASK, article_revision_id=revision.id, destination=destination,
                content_hash=content_hash or revision.content_hash,
            )
        )

    def get_live(self, revision_id, destination):
        return next(
            (a for a in self.items if a.article_revision_id == revision_id and a.destination == destination
             and a.decision == ApprovalDecision.APPROVED),
            None,
        )

    def supersede_for_task(self, task_id, keep_revision_id=None):
        for approval in self.items:
            if approval.article_revision_id != keep_revision_id:
                approval.decision = ApprovalDecision.SUPERSEDED
        return len(self.items)


def test_happy_path_passes():
    r1 = make_revision(1, "# LoRA\n\nText.\n")
    approvals = FakeApprovals()
    approvals.approve(r1, SANITY)
    result = ApprovalGate(approvals, FakeRevisions(r1)).check(r1.id, SANITY)
    assert result.passed and result.approval.destination == SANITY


def test_approve_then_edit_fails():
    r1 = make_revision(1, "# LoRA\n\nText.\n")
    approvals = FakeApprovals()
    approvals.approve(r1, SANITY)
    r2 = make_revision(2, "# LoRA\n\nEdited text.\n")
    approvals.supersede_for_task(TASK)  # what an owner edit does
    revisions = FakeRevisions(r1, r2)
    assert ApprovalGate(approvals, revisions).check(r1.id, SANITY).reason == "not_latest"
    assert ApprovalGate(approvals, revisions).check(r2.id, SANITY).reason == "not_approved"


def test_approve_r2_then_publish_r3_fails():
    r2, r3 = make_revision(2, "# LoRA\n\nTwo.\n"), make_revision(3, "# LoRA\n\nThree.\n")
    approvals = FakeApprovals()
    approvals.approve(r2, SANITY)
    gate = ApprovalGate(approvals, FakeRevisions(r2, r3))
    assert gate.check(r3.id, SANITY).reason == "not_approved"
    assert gate.check(r2.id, SANITY).reason == "not_latest"


def test_hash_tampered_in_db_fails():
    r1 = make_revision(1, "# LoRA\n\nText.\n")
    approvals = FakeApprovals()
    approvals.approve(r1, SANITY)
    tampered = r1.model_copy(update={"markdown": "# LoRA\n\nInjected.\n"})  # stored text changed, stored hash not
    assert ApprovalGate(approvals, FakeRevisions(tampered)).check(r1.id, SANITY).reason == "hash_mismatch"

    other = FakeApprovals()
    other.approve(r1, SANITY, content_hash="0" * 64)  # approval row carries a different hash
    assert ApprovalGate(other, FakeRevisions(r1)).check(r1.id, SANITY).reason == "hash_mismatch"


def test_wrong_destination_fails():
    r1 = make_revision(1, "# LoRA\n\nText.\n")
    approvals = FakeApprovals()
    approvals.approve(r1, SANITY)
    assert ApprovalGate(approvals, FakeRevisions(r1)).check(r1.id, DEVTO).reason == "not_approved"


def test_unknown_revision_fails():
    assert ApprovalGate(FakeApprovals(), FakeRevisions()).check(uuid.uuid4(), SANITY).reason == "not_found"
