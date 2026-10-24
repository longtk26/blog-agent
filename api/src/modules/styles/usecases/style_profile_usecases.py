from dataclasses import asdict
from typing import Annotated, Any
import uuid

from fastapi import Depends

from src.libs.exceptions import BadRequestException, NotFoundException
from src.modules.agent.infrastructure.adapters import IModelFactoryDep
from src.modules.agent.ports.output.model_factory import IModelFactory, ModelRole
from src.modules.shared.domain.entities import StyleProfileData, StyleProfileEntity
from src.modules.styles.domain.active_style import resolve_active_style
from src.modules.styles.domain.profile_generator import generate_style_profile_from_samples
from src.modules.styles.ports.output import (
    IStyleGuideRepoDep,
    IStyleGuideRepository,
    IStyleProfileRepoDep,
    IStyleProfileRepository,
    IWritingSampleRepoDep,
    IWritingSampleRepository,
)


class GenerateStyleProfileUsecase:
    def __init__(
        self,
        sample_repo: IWritingSampleRepoDep,
        profile_repo: IStyleProfileRepoDep,
        model_factory: IModelFactoryDep,
    ):
        self.sample_repo: IWritingSampleRepository = sample_repo
        self.profile_repo: IStyleProfileRepository = profile_repo
        self.model_factory: IModelFactory = model_factory

    async def execute(self, name: str | None = None) -> StyleProfileEntity:
        samples = self.sample_repo.list_all(approved_only=True)
        if not samples:
            raise BadRequestException("No approved writing samples available to analyze. Import samples first.")

        model = self.model_factory.get(ModelRole.PLANNER)
        profile_data = await generate_style_profile_from_samples(samples, model)

        new_version = self.profile_repo.latest_version() + 1
        profile_name = name or f"Learned Profile v{new_version}"
        markdown_text = profile_data.to_markdown()

        entity = StyleProfileEntity(
            id=uuid.uuid4(),
            version=new_version,
            is_active=True,
            name=profile_name,
            profile_data=asdict(profile_data),
            markdown_content=markdown_text,
        )
        return self.profile_repo.create(entity)


class GetStyleProfileUsecase:
    def __init__(
        self,
        profile_repo: IStyleProfileRepoDep,
        style_guide_repo: IStyleGuideRepoDep,
    ):
        self.profile_repo: IStyleProfileRepository = profile_repo
        self.style_guide_repo: IStyleGuideRepository = style_guide_repo

    async def execute(self) -> dict[str, Any]:
        active = self.profile_repo.get_active()
        if active is not None:
            return {
                "id": str(active.id),
                "version": active.version,
                "is_active": True,
                "name": active.name,
                "source": "learned_profile",
                "profile_data": active.profile_data,
                "markdown_content": active.markdown_content,
                "created_at": active.created_at.isoformat() if active.created_at else None,
                "updated_at": active.updated_at.isoformat() if active.updated_at else None,
            }

        # Fallback to Epic 3 static / seed style guide
        guide = resolve_active_style(self.style_guide_repo.latest())
        return {
            "id": None,
            "version": 0,
            "is_active": True,
            "name": f"Static Style Guide ({guide.version})",
            "source": guide.source,
            "profile_data": {},
            "markdown_content": guide.content,
            "created_at": guide.updated_at.isoformat() if guide.updated_at else None,
            "updated_at": guide.updated_at.isoformat() if guide.updated_at else None,
        }


class ListStyleProfilesUsecase:
    def __init__(self, profile_repo: IStyleProfileRepoDep):
        self.profile_repo: IStyleProfileRepository = profile_repo

    async def execute(self) -> list[StyleProfileEntity]:
        return self.profile_repo.list_all()


class UpdateStyleProfileUsecase:
    def __init__(self, profile_repo: IStyleProfileRepoDep):
        self.profile_repo: IStyleProfileRepository = profile_repo

    async def execute(
        self,
        profile_data: dict[str, Any] | None = None,
        markdown_content: str | None = None,
        name: str | None = None,
    ) -> StyleProfileEntity:
        new_version = self.profile_repo.latest_version() + 1
        profile_name = name or f"Custom Profile v{new_version}"

        parsed_data = profile_data or {}
        # If markdown content is passed without profile_data, generate markdown directly
        if profile_data and not markdown_content:
            try:
                data_obj = StyleProfileData(**profile_data)
                markdown_content = data_obj.to_markdown()
            except Exception:
                pass

        entity = StyleProfileEntity(
            id=uuid.uuid4(),
            version=new_version,
            is_active=True,
            name=profile_name,
            profile_data=parsed_data,
            markdown_content=markdown_content,
        )
        return self.profile_repo.create(entity)


class ActivateStyleProfileUsecase:
    def __init__(self, profile_repo: IStyleProfileRepoDep):
        self.profile_repo: IStyleProfileRepository = profile_repo

    async def execute(self, profile_id: uuid.UUID) -> StyleProfileEntity:
        activated = self.profile_repo.activate(profile_id)
        if not activated:
            raise NotFoundException(f"Style profile {profile_id} not found")
        return activated


GenerateStyleProfileUsecaseDep = Annotated[GenerateStyleProfileUsecase, Depends(GenerateStyleProfileUsecase)]
GetStyleProfileUsecaseDep = Annotated[GetStyleProfileUsecase, Depends(GetStyleProfileUsecase)]
ListStyleProfilesUsecaseDep = Annotated[ListStyleProfilesUsecase, Depends(ListStyleProfilesUsecase)]
UpdateStyleProfileUsecaseDep = Annotated[UpdateStyleProfileUsecase, Depends(UpdateStyleProfileUsecase)]
ActivateStyleProfileUsecaseDep = Annotated[ActivateStyleProfileUsecase, Depends(ActivateStyleProfileUsecase)]
