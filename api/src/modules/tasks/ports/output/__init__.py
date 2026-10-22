from .task_repository import ITaskRepository
from .task_event_repository import ITaskEventRepository
from .task_event_feed import ITaskEventFeed

# Dep bindings live in infrastructure; re-exported lazily so adapters can import these ports without a cycle.
_DEPS = {"ITaskRepoDep": "persistence", "ITaskEventRepoDep": "persistence", "ITaskEventFeedDep": "adapters"}


def __getattr__(name: str):
    if name in _DEPS:
        from importlib import import_module

        return getattr(import_module(f"src.modules.tasks.infrastructure.{_DEPS[name]}"), name)
    raise AttributeError(name)


__all__ = [
    "ITaskRepository",
    "ITaskEventRepository",
    "ITaskEventFeed",
    "ITaskRepoDep",
    "ITaskEventRepoDep",
    "ITaskEventFeedDep",
]
