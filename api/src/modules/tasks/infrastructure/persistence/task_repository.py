import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.shared.domain.entities import (
    SeriesInfo,
    TaskBudgets,
    TaskProgress,
    WritingTaskEntity,
)
from src.modules.shared.domain.value_objects import TaskStatus
from src.modules.shared.infrastructure.models import WritingTaskModel
from src.modules.shared.infrastructure.models._columns import utcnow
from src.modules.tasks.ports.output.task_repository import ITaskRepository


class TaskRepository(ITaskRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def create(self, task: WritingTaskEntity) -> WritingTaskEntity:
        model = self.__to_model(task)
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def get(self, task_id: uuid.UUID, for_update: bool = False) -> WritingTaskEntity | None:
        statement = select(WritingTaskModel).where(WritingTaskModel.id == task_id)
        if for_update:
            statement = statement.with_for_update()
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def update(self, task: WritingTaskEntity) -> WritingTaskEntity:
        model = self.session.get(WritingTaskModel, task.id)
        fresh = self.__to_model(task)
        for field in WritingTaskModel.model_fields:
            if field not in ("id", "created_at"):
                setattr(model, field, getattr(fresh, field))
        model.updated_at = utcnow()
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def list_page(
        self,
        statuses: list[TaskStatus] | None = None,
        mode: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[WritingTaskEntity], int]:
        statement = select(WritingTaskModel)
        count = select(func.count()).select_from(WritingTaskModel)
        if statuses:
            values = [str(s) for s in statuses]
            statement = statement.where(col(WritingTaskModel.status).in_(values))
            count = count.where(col(WritingTaskModel.status).in_(values))
        if mode:
            statement = statement.where(WritingTaskModel.mode == mode)
            count = count.where(WritingTaskModel.mode == mode)
        statement = statement.order_by(col(WritingTaskModel.updated_at).desc()).offset(offset).limit(limit)
        items = [self.__to_entity(m) for m in self.session.exec(statement).all()]
        return items, self.session.exec(count).one()

    def list_by_statuses(self, statuses: list[TaskStatus]) -> list[WritingTaskEntity]:
        statement = select(WritingTaskModel).where(col(WritingTaskModel.status).in_([str(s) for s in statuses]))
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def __to_entity(self, model: WritingTaskModel) -> WritingTaskEntity:
        return WritingTaskEntity(
            id=model.id,
            topic=model.topic,
            mode=model.mode,
            audience=model.audience,
            depth=model.depth,
            language=model.language,
            format=model.format,
            series=SeriesInfo.model_validate(model.series) if model.series else None,
            requirements=model.requirements,
            angle=model.angle,
            include_diagram=model.include_diagram,
            review_outline=model.review_outline,
            publication_targets=model.publication_targets or [],
            budgets=TaskBudgets.model_validate(model.budgets or {}),
            status=model.status,
            failed_stage=model.failed_stage,
            last_error=model.last_error,
            resumable=model.resumable,
            research_plan=model.research_plan,
            outline=model.outline,
            open_questions=model.open_questions or [],
            progress=TaskProgress.model_validate(model.progress or {}),
            last_run_id=model.last_run_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def __to_model(self, entity: WritingTaskEntity) -> WritingTaskModel:
        data = entity.model_dump(mode="json", exclude={"id", "created_at", "updated_at", "last_run_id"})
        model = WritingTaskModel(**data, last_run_id=entity.last_run_id)
        if entity.id is not None:
            model.id = entity.id
        return model


ITaskRepoDep = Annotated[ITaskRepository, Depends(TaskRepository)]
