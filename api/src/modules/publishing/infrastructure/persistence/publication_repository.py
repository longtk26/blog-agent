import uuid
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, col, select

from src.libs.database.session import SessionDep
from src.modules.publishing.ports.output.publication_repository import IPublicationRepository
from src.modules.shared.domain.entities import PublicationEntity, PublicationTarget
from src.modules.shared.infrastructure.models import PublicationModel
from src.modules.shared.infrastructure.models._columns import utcnow


class PublicationRepository(IPublicationRepository):
    def __init__(self, session: SessionDep):
        self.session: Session = session

    def get(self, publication_id: uuid.UUID) -> PublicationEntity | None:
        statement = select(PublicationModel).where(PublicationModel.id == publication_id)
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def get_by_task_and_destination(
        self, task_id: uuid.UUID, destination: PublicationTarget | str
    ) -> PublicationEntity | None:
        statement = select(PublicationModel).where(
            PublicationModel.task_id == task_id,
            PublicationModel.destination == str(destination),
        )
        model = self.session.exec(statement).first()
        return self.__to_entity(model) if model else None

    def list_by_task(self, task_id: uuid.UUID) -> list[PublicationEntity]:
        statement = (
            select(PublicationModel)
            .where(PublicationModel.task_id == task_id)
            .order_by(col(PublicationModel.published_at).desc().nullslast())
        )
        return [self.__to_entity(m) for m in self.session.exec(statement).all()]

    def save(self, publication: PublicationEntity) -> PublicationEntity:
        model: PublicationModel | None = None
        if publication.id is not None:
            model = self.session.exec(select(PublicationModel).where(PublicationModel.id == publication.id)).first()
        if model is None:
            model = self.session.exec(
                select(PublicationModel).where(
                    PublicationModel.task_id == publication.task_id,
                    PublicationModel.destination == str(publication.destination),
                )
            ).first()

        now = utcnow()
        if model is None:
            model = PublicationModel(
                id=publication.id or uuid.uuid4(),
                task_id=publication.task_id,
                article_revision_id=publication.article_revision_id,
                destination=str(publication.destination),
                remote_document_id=publication.remote_document_id,
                remote_url=publication.remote_url,
                status=str(publication.status),
                attempt_count=publication.attempt_count,
                rendered_content_hash=publication.rendered_content_hash,
                last_error=publication.last_error,
                published_at=publication.published_at,
                updated_at=publication.updated_at or now,
            )
            self.session.add(model)
        else:
            model.article_revision_id = publication.article_revision_id
            model.destination = str(publication.destination)
            model.remote_document_id = publication.remote_document_id
            model.remote_url = publication.remote_url
            model.status = str(publication.status)
            model.attempt_count = publication.attempt_count
            model.rendered_content_hash = publication.rendered_content_hash
            model.last_error = publication.last_error
            model.published_at = publication.published_at
            model.updated_at = publication.updated_at or now
            self.session.add(model)

        self.session.flush()
        return self.__to_entity(model)

    def delete(self, publication_id: uuid.UUID) -> None:
        statement = select(PublicationModel).where(PublicationModel.id == publication_id)
        model = self.session.exec(statement).first()
        if model:
            self.session.delete(model)
            self.session.flush()

    def __to_entity(self, model: PublicationModel) -> PublicationEntity:
        return PublicationEntity(
            id=model.id,
            task_id=model.task_id,
            article_revision_id=model.article_revision_id,
            destination=model.destination,
            remote_document_id=model.remote_document_id,
            remote_url=model.remote_url,
            status=model.status,
            attempt_count=model.attempt_count,
            rendered_content_hash=model.rendered_content_hash,
            last_error=model.last_error,
            published_at=model.published_at,
            updated_at=model.updated_at,
        )


IPublicationRepoDep = Annotated[IPublicationRepository, Depends(PublicationRepository)]
