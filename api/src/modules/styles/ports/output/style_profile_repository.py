from typing import Protocol
import uuid

from src.modules.shared.domain.entities import StyleProfileEntity


class IStyleProfileRepository(Protocol):
    """Output port for style profile repository."""

    def get_active(self) -> StyleProfileEntity | None:
        ...

    def get_by_version(self, version: int) -> StyleProfileEntity | None:
        ...

    def get_by_id(self, profile_id: uuid.UUID) -> StyleProfileEntity | None:
        ...

    def list_all(self) -> list[StyleProfileEntity]:
        ...

    def create(self, profile: StyleProfileEntity) -> StyleProfileEntity:
        ...

    def activate(self, profile_id: uuid.UUID) -> StyleProfileEntity | None:
        ...

    def latest_version(self) -> int:
        ...
