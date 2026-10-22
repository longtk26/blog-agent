from .repositories import IDraftRepository, IRevisionRepository, IEvaluationRepository

# Dep bindings live in infrastructure; re-exported lazily so adapters can import these ports without a cycle.
_DEPS = {"IDraftRepoDep", "IRevisionRepoDep", "IEvaluationRepoDep"}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.articles.infrastructure import persistence

        return getattr(persistence, name)
    raise AttributeError(name)


__all__ = [
    "IDraftRepository",
    "IRevisionRepository",
    "IEvaluationRepository",
    "IDraftRepoDep",
    "IRevisionRepoDep",
    "IEvaluationRepoDep",
]
