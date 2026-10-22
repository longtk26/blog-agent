import pytest

from src.libs.exceptions import BadRequestException
from src.modules.shared.domain.value_objects import ALLOWED_TRANSITIONS, TaskStatus, can_transition, ensure_transition

S = TaskStatus


@pytest.mark.parametrize(("current", "target"), [(c, t) for c, targets in ALLOWED_TRANSITIONS.items() for t in targets if c != S.FAILED])
def test_every_allowed_transition_passes(current, target):
    ensure_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.QUEUED, S.PUBLISHED),
        (S.RESEARCHING, S.APPROVED),
        (S.AWAITING_REVIEW, S.PUBLISHING),  # never publish without approval
        (S.DRAFTING, S.PUBLISHED),
        (S.REJECTED, S.RESEARCHING),
        (S.PUBLISHED, S.PUBLISHING),
        (S.COMPLETED, S.DRAFTING),
    ],
)
def test_forbidden_transitions_raise(current, target):
    assert not can_transition(current, target)
    with pytest.raises(BadRequestException) as exc:
        ensure_transition(current, target)
    assert exc.value.code == "INVALID_TRANSITION"


def test_failed_only_returns_to_its_failed_stage():
    ensure_transition(S.FAILED, S.RESEARCHING, failed_stage=S.RESEARCHING)
    ensure_transition(S.FAILED, S.REJECTED, failed_stage=S.RESEARCHING)
    with pytest.raises(BadRequestException):
        ensure_transition(S.FAILED, S.DRAFTING, failed_stage=S.RESEARCHING)
    with pytest.raises(BadRequestException):
        ensure_transition(S.FAILED, S.RESEARCHING, failed_stage=None)
