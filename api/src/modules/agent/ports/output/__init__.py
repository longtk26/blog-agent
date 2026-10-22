from .model_factory import IModelFactory, ModelRole, ModelSpec
from .tracing import ITracing
from .workflow_runner import IWorkflowRunner

# Dep bindings live in infrastructure; re-exported lazily so adapters can import these ports without a cycle.
_DEPS = {"IModelFactoryDep", "ITracingDep"}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.agent.infrastructure import adapters

        return getattr(adapters, name)
    raise AttributeError(name)


__all__ = [
    "IModelFactory",
    "ModelRole",
    "ModelSpec",
    "ITracing",
    "IWorkflowRunner",
    "IModelFactoryDep",
    "ITracingDep",
]
