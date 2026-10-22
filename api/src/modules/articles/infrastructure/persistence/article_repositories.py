import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import func
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.articles.ports.output.repositories import IDraftRepository, IEvaluationRepository, IRevisionRepository
from src.modules.shared.domain.entities import (
    ArticleDraftEntity,
    ArticleMetadata,
    ArticleRevisionEntity,
    DraftSection,
    EvaluationResultEntity,
    ValidationIssue,
)
from src.modules.shared.infrastructure.models import ArticleDraftModel, ArticleRevisionModel, EvaluationResultModel
from src.modules.shared.infrastructure.models._columns import utcnow


class DraftRepository(IDraftRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def get(self, task_id: uuid.UUID) -> ArticleDraftEntity | None:
        model = self.session.get(ArticleDraftModel, task_id)
        if model is None:
            return None
        return ArticleDraftEntity(
            task_id=model.task_id,
            sections=[DraftSection.model_validate(s) for s in model.sections],
            metadata=ArticleMetadata.model_validate(model.article_metadata) if model.article_metadata else None,
            markdown=model.markdown,
            issues=[ValidationIssue.model_validate(i) for i in model.issues],
            judge=model.judge,
            self_revisions=model.self_revisions,
            history=model.history,
            updated_at=model.updated_at,
        )

    def save(self, draft: ArticleDraftEntity) -> ArticleDraftEntity:
        model = self.session.get(ArticleDraftModel, draft.task_id) or ArticleDraftModel(task_id=draft.task_id)
        data = draft.model_dump(mode="json")
        model.sections = data["sections"]
        model.article_metadata = data["metadata"]
        model.markdown = draft.markdown
        model.issues = data["issues"]
        model.judge = data["judge"]
        model.self_revisions = draft.self_revisions
        model.history = data["history"]
        model.updated_at = utcnow()
        self.session.add(model)
        self.session.flush()
        return draft


class RevisionRepository(IRevisionRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def create(self, revision: ArticleRevisionEntity) -> ArticleRevisionEntity:
        data = revision.model_dump(mode="json", exclude={"id", "created_at", "metadata", "task_id", "parent_revision_id"})
        model = ArticleRevisionModel(
            **data,
            task_id=revision.task_id,
            parent_revision_id=revision.parent_revision_id,
            revision_metadata=revision.model_dump(mode="json")["metadata"],
        )
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def get(self, revision_id: uuid.UUID) -> ArticleRevisionEntity | None:
        model = self.session.get(ArticleRevisionModel, revision_id)
        return self.__to_entity(model) if model else None

    def list_by_task(self, task_id: uuid.UUID) -> list[ArticleRevisionEntity]:
        statement = (
            select(ArticleRevisionModel)
            .where(ArticleRevisionModel.task_id == task_id)
            .order_by(col(ArticleRevisionModel.revision_number).desc())
        )
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def latest(self, task_id: uuid.UUID) -> ArticleRevisionEntity | None:
        statement = (
            select(ArticleRevisionModel)
            .where(ArticleRevisionModel.task_id == task_id)
            .order_by(col(ArticleRevisionModel.revision_number).desc())
            .limit(1)
        )
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def slug_taken(self, slug: str, exclude_task_id: uuid.UUID) -> bool:
        statement = (
            select(func.count())
            .select_from(ArticleRevisionModel)
            .where(ArticleRevisionModel.slug == slug, ArticleRevisionModel.task_id != exclude_task_id)
        )
        return self.session.exec(statement).one() > 0

    def __to_entity(self, model: ArticleRevisionModel) -> ArticleRevisionEntity:
        return ArticleRevisionEntity(
            id=model.id,
            task_id=model.task_id,
            revision_number=model.revision_number,
            parent_revision_id=model.parent_revision_id,
            title=model.title,
            slug=model.slug,
            description=model.description,
            tags=model.tags or [],
            markdown=model.markdown,
            metadata=model.revision_metadata or {},
            created_by=model.created_by,
            content_hash=model.content_hash,
            created_at=model.created_at,
        )


class EvaluationRepository(IEvaluationRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def add_many(self, results: list[EvaluationResultEntity]) -> list[EvaluationResultEntity]:
        models = []
        for result in results:
            data = result.model_dump(mode="json", exclude={"id", "created_at", "revision_id"})
            models.append(EvaluationResultModel(**data, revision_id=result.revision_id))
        self.session.add_all(models)
        self.session.flush()
        return [self.__to_entity(m) for m in models]

    def list_by_revision(self, revision_id: uuid.UUID) -> list[EvaluationResultEntity]:
        statement = select(EvaluationResultModel).where(EvaluationResultModel.revision_id == revision_id)
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def __to_entity(self, model: EvaluationResultModel) -> EvaluationResultEntity:
        return EvaluationResultEntity(
            id=model.id,
            revision_id=model.revision_id,
            kind=model.kind,
            passed=model.passed,
            scores=model.scores or {},
            issues=[ValidationIssue.model_validate(i) for i in model.issues or []],
            model=model.model,
            prompt_version=model.prompt_version,
            created_at=model.created_at,
        )


IDraftRepoDep = Annotated[IDraftRepository, Depends(DraftRepository)]
IRevisionRepoDep = Annotated[IRevisionRepository, Depends(RevisionRepository)]
IEvaluationRepoDep = Annotated[IEvaluationRepository, Depends(EvaluationRepository)]
