from .system_probe import ISystemProbe

# Dep binding lives in infrastructure; re-exported lazily so the adapter can import this port without a cycle.
_DEPS = {"ISystemProbeDep"}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.health.infrastructure import adapters

        return getattr(adapters, name)
    raise AttributeError(name)


__all__ = ["ISystemProbe", "ISystemProbeDep"]
