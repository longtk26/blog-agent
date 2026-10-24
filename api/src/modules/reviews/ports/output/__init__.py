from .approval_repository import IApprovalRepository

# Dep binding lives in infrastructure; re-exported lazily so the adapter can import this port without a cycle.
_DEPS = {"IApprovalRepoDep"}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.reviews.infrastructure import persistence

        return getattr(persistence, name)
    raise AttributeError(name)


__all__ = ["IApprovalRepository", "IApprovalRepoDep"]
