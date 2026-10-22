from .style_guide_repository import IStyleGuideRepository

# Dep binding lives in infrastructure; re-exported lazily so the adapter can import this port without a cycle.
_DEPS = {"IStyleGuideRepoDep"}


def __getattr__(name: str):
    if name in _DEPS:
        from src.modules.styles.infrastructure import persistence

        return getattr(persistence, name)
    raise AttributeError(name)


__all__ = ["IStyleGuideRepository", "IStyleGuideRepoDep"]
