from typing import Any
import uuid

from fastapi import APIRouter

from src.modules.styles.presenter.dtos import (
    GenerateStyleProfileRequestDto,
    ImportSamplesRequestDto,
    ImportSamplesResponseDto,
    OwnerNoteRequestDto,
    OwnerNoteResponseDto,
    StyleGuideResponseDto,
    StyleProfileResponseDto,
    ToggleApprovalRequestDto,
    UpdateStyleGuideRequestDto,
    UpdateStyleProfileRequestDto,
    WritingSampleResponseDto,
)
from src.modules.styles.usecases import (
    ActivateStyleProfileUsecaseDep,
    CreateOwnerNoteUsecaseDep,
    DeleteOwnerNoteUsecaseDep,
    DeleteSampleUsecaseDep,
    GenerateStyleProfileUsecaseDep,
    GetOwnerNoteUsecaseDep,
    GetStyleGuideUsecaseDep,
    GetStyleProfileUsecaseDep,
    ImportSamplesUsecaseDep,
    ListOwnerNotesUsecaseDep,
    ListSamplesUsecaseDep,
    ListStyleProfilesUsecaseDep,
    ToggleSampleApprovalUsecaseDep,
    UpdateOwnerNoteUsecaseDep,
    UpdateStyleGuideUsecaseDep,
    UpdateStyleProfileUsecaseDep,
)

style_router = APIRouter(tags=["style"])


# --- Writing Samples (E6-S2) --------------------------------------------------

@style_router.post("/samples/import", response_model=ImportSamplesResponseDto)
async def import_samples(body: ImportSamplesRequestDto, usecase: ImportSamplesUsecaseDep):
    result = await usecase.execute(sources=body.sources)
    return ImportSamplesResponseDto(
        imported=result.imported,
        updated=result.updated,
        skipped=result.skipped,
        total_chunks=result.total_chunks,
    )


@style_router.get("/samples", response_model=list[WritingSampleResponseDto])
async def list_samples(usecase: ListSamplesUsecaseDep, approved_only: bool = False):
    samples = await usecase.execute(approved_only=approved_only)
    return [
        WritingSampleResponseDto(
            id=s.id,
            origin=s.origin,
            remote_id=s.remote_id,
            title=s.title,
            tags=s.tags,
            published_at=s.published_at,
            approved_as_style_example=s.approved_as_style_example,
            content_hash=s.content_hash,
            chunk_count=s.chunk_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in samples
    ]


@style_router.patch("/samples/{sample_id}", response_model=WritingSampleResponseDto)
async def toggle_sample_approval(
    sample_id: uuid.UUID,
    body: ToggleApprovalRequestDto,
    usecase: ToggleSampleApprovalUsecaseDep,
):
    sample = await usecase.execute(sample_id, body.approved)
    return WritingSampleResponseDto(
        id=sample.id,
        origin=sample.origin,
        remote_id=sample.remote_id,
        title=sample.title,
        tags=sample.tags,
        published_at=sample.published_at,
        approved_as_style_example=sample.approved_as_style_example,
        content_hash=sample.content_hash,
        chunk_count=0,
        created_at=sample.created_at,
        updated_at=sample.updated_at,
    )


@style_router.delete("/samples/{sample_id}")
async def delete_sample(sample_id: uuid.UUID, usecase: DeleteSampleUsecaseDep):
    success = await usecase.execute(sample_id)
    return {"deleted": success, "id": str(sample_id)}


# --- Style Profiles (E6-S3) ---------------------------------------------------

@style_router.post("/style-profile/generate", response_model=StyleProfileResponseDto)
async def generate_style_profile(
    body: GenerateStyleProfileRequestDto,
    usecase: GenerateStyleProfileUsecaseDep,
):
    profile = await usecase.execute(name=body.name)
    return StyleProfileResponseDto(
        id=profile.id,
        version=profile.version,
        is_active=profile.is_active,
        name=profile.name,
        source="learned_profile",
        profile_data=profile.profile_data,
        markdown_content=profile.markdown_content,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@style_router.get("/style-profile", response_model=StyleProfileResponseDto)
async def get_active_style_profile(usecase: GetStyleProfileUsecaseDep):
    data = await usecase.execute()
    return StyleProfileResponseDto(
        id=uuid.UUID(data["id"]) if data.get("id") else None,
        version=data.get("version", 0),
        is_active=data.get("is_active", True),
        name=data.get("name", "Active Style Profile"),
        source=data.get("source", "learned_profile"),
        profile_data=data.get("profile_data", {}),
        markdown_content=data.get("markdown_content"),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


@style_router.get("/style-profiles", response_model=list[StyleProfileResponseDto])
async def list_style_profiles(usecase: ListStyleProfilesUsecaseDep):
    profiles = await usecase.execute()
    return [
        StyleProfileResponseDto(
            id=p.id,
            version=p.version,
            is_active=p.is_active,
            name=p.name,
            source="learned_profile",
            profile_data=p.profile_data,
            markdown_content=p.markdown_content,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in profiles
    ]


@style_router.put("/style-profile", response_model=StyleProfileResponseDto)
async def update_style_profile(
    body: UpdateStyleProfileRequestDto,
    usecase: UpdateStyleProfileUsecaseDep,
):
    profile = await usecase.execute(
        profile_data=body.profile_data,
        markdown_content=body.markdown_content,
        name=body.name,
    )
    return StyleProfileResponseDto(
        id=profile.id,
        version=profile.version,
        is_active=profile.is_active,
        name=profile.name,
        source="learned_profile",
        profile_data=profile.profile_data,
        markdown_content=profile.markdown_content,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@style_router.post("/style-profile/{profile_id}/activate", response_model=StyleProfileResponseDto)
async def activate_style_profile(profile_id: uuid.UUID, usecase: ActivateStyleProfileUsecaseDep):
    profile = await usecase.execute(profile_id)
    return StyleProfileResponseDto(
        id=profile.id,
        version=profile.version,
        is_active=profile.is_active,
        name=profile.name,
        source="learned_profile",
        profile_data=profile.profile_data,
        markdown_content=profile.markdown_content,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


# --- Owner Notes (E6-S7) ------------------------------------------------------

@style_router.post("/notes", response_model=OwnerNoteResponseDto)
async def create_note(body: OwnerNoteRequestDto, usecase: CreateOwnerNoteUsecaseDep):
    note = await usecase.execute(
        title=body.title,
        content=body.content,
        citable_url=body.citable_url,
        quality_score=body.quality_score,
    )
    return OwnerNoteResponseDto(
        id=note.id,
        title=note.title,
        content=note.content,
        citable_url=note.citable_url,
        quality_score=note.quality_score,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@style_router.get("/notes", response_model=list[OwnerNoteResponseDto])
async def list_notes(usecase: ListOwnerNotesUsecaseDep):
    notes = await usecase.execute()
    return [
        OwnerNoteResponseDto(
            id=n.id,
            title=n.title,
            content=n.content,
            citable_url=n.citable_url,
            quality_score=n.quality_score,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]


@style_router.get("/notes/{note_id}", response_model=OwnerNoteResponseDto)
async def get_note(note_id: uuid.UUID, usecase: GetOwnerNoteUsecaseDep):
    note = await usecase.execute(note_id)
    return OwnerNoteResponseDto(
        id=note.id,
        title=note.title,
        content=note.content,
        citable_url=note.citable_url,
        quality_score=note.quality_score,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@style_router.put("/notes/{note_id}", response_model=OwnerNoteResponseDto)
async def update_note(note_id: uuid.UUID, body: OwnerNoteRequestDto, usecase: UpdateOwnerNoteUsecaseDep):
    note = await usecase.execute(
        note_id=note_id,
        title=body.title,
        content=body.content,
        citable_url=body.citable_url,
        quality_score=body.quality_score,
    )
    return OwnerNoteResponseDto(
        id=note.id,
        title=note.title,
        content=note.content,
        citable_url=note.citable_url,
        quality_score=note.quality_score,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@style_router.delete("/notes/{note_id}")
async def delete_note(note_id: uuid.UUID, usecase: DeleteOwnerNoteUsecaseDep):
    success = await usecase.execute(note_id)
    return {"deleted": success, "id": str(note_id)}


# --- Static Style Guide (Epic 3 fallback / seed) -----------------------------

@style_router.get("/settings/style-guide", response_model=StyleGuideResponseDto)
async def get_style_guide(usecase: GetStyleGuideUsecaseDep):
    guide = await usecase.execute()
    return StyleGuideResponseDto(
        version=guide.version,
        content=guide.content,
        source=guide.source,
        updated_at=guide.updated_at,
    )


@style_router.put("/settings/style-guide", response_model=StyleGuideResponseDto)
async def update_style_guide(body: UpdateStyleGuideRequestDto, usecase: UpdateStyleGuideUsecaseDep):
    guide = await usecase.execute(body.content)
    return StyleGuideResponseDto(
        version=guide.version,
        content=guide.content,
        source=guide.source,
        updated_at=guide.updated_at,
    )
