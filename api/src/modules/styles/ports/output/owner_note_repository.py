from typing import Protocol
import uuid

from src.modules.shared.domain.entities import OwnerNoteEntity


class IOwnerNoteRepository(Protocol):
    """Output port for owner notes repository."""

    def create(self, note: OwnerNoteEntity) -> OwnerNoteEntity:
        ...

    def update(self, note: OwnerNoteEntity) -> OwnerNoteEntity:
        ...

    def get(self, note_id: uuid.UUID) -> OwnerNoteEntity | None:
        ...

    def list_all(self) -> list[OwnerNoteEntity]:
        ...

    def delete(self, note_id: uuid.UUID) -> bool:
        ...
