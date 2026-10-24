from typing import Annotated
import uuid

from fastapi import Depends
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import OwnerNoteEntity
from src.modules.shared.infrastructure.models import OwnerNoteModel
from src.modules.shared.infrastructure.models._columns import utcnow
from src.modules.styles.ports.output.owner_note_repository import IOwnerNoteRepository


class OwnerNoteRepository(IOwnerNoteRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def create(self, note: OwnerNoteEntity) -> OwnerNoteEntity:
        model = OwnerNoteModel(
            id=note.id,
            title=note.title,
            content=note.content,
            citable_url=note.citable_url,
            quality_score=note.quality_score,
            created_at=note.created_at or utcnow(),
            updated_at=note.updated_at or utcnow(),
        )
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def update(self, note: OwnerNoteEntity) -> OwnerNoteEntity:
        model = self.session.get(OwnerNoteModel, note.id)
        if not model:
            raise KeyError(f"Owner note not found: {note.id}")
        model.title = note.title
        model.content = note.content
        model.citable_url = note.citable_url
        model.quality_score = note.quality_score
        model.updated_at = utcnow()
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def get(self, note_id: uuid.UUID) -> OwnerNoteEntity | None:
        model = self.session.get(OwnerNoteModel, note_id)
        return self._to_entity(model) if model else None

    def list_all(self) -> list[OwnerNoteEntity]:
        statement = select(OwnerNoteModel).order_by(col(OwnerNoteModel.created_at).desc())
        models = self.session.exec(statement).all()
        return [self._to_entity(m) for m in models]

    def delete(self, note_id: uuid.UUID) -> bool:
        model = self.session.get(OwnerNoteModel, note_id)
        if not model:
            return False
        self.session.delete(model)
        self.session.flush()
        return True

    @staticmethod
    def _to_entity(model: OwnerNoteModel) -> OwnerNoteEntity:
        return OwnerNoteEntity(
            id=model.id,
            title=model.title,
            content=model.content,
            citable_url=model.citable_url,
            quality_score=model.quality_score,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


IOwnerNoteRepoDep = Annotated[IOwnerNoteRepository, Depends(OwnerNoteRepository)]
