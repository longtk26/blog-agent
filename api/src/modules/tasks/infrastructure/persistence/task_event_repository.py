import uuid
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import TaskEventEntity
from src.modules.shared.infrastructure.models import TaskEventModel
from src.modules.tasks.ports.output.task_event_repository import ITaskEventRepository


class TaskEventRepository(ITaskEventRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def add(self, event: TaskEventEntity) -> TaskEventEntity:
        model = TaskEventModel(**event.model_dump(mode="json", exclude={"id", "created_at"}))
        model.task_id = event.task_id
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def list_after(self, task_id: uuid.UUID, after_id: int = 0, limit: int = 500) -> list[TaskEventEntity]:
        statement = (
            select(TaskEventModel)
            .where(TaskEventModel.task_id == task_id, col(TaskEventModel.id) > after_id)
            .order_by(col(TaskEventModel.id))
            .limit(limit)
        )
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def __to_entity(self, model: TaskEventModel) -> TaskEventEntity:
        return TaskEventEntity(
            id=model.id,
            task_id=model.task_id,
            type=model.type,
            from_status=model.from_status,
            to_status=model.to_status,
            actor=model.actor,
            payload=model.payload or {},
            created_at=model.created_at,
        )


ITaskEventRepoDep = Annotated[ITaskEventRepository, Depends(TaskEventRepository)]
