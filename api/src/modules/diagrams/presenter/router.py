"""API routes for diagram assets, format switching, upload replacement, and file serving (E7-S6, E7-S7)."""

from pathlib import Path
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from src.configs.config import config
from src.libs.database import SessionDep
from src.libs.exceptions import BadRequestException, ConflictException, NotFoundException
from src.modules.agent.infrastructure.adapters.workflow_runner import LangGraphWorkflowRunner
from src.modules.articles.ports.output import IRevisionRepoDep, IRevisionRepository
from src.modules.diagrams.infrastructure.adapters.diagram_renderer_adapter import DiagramRendererDep
from src.modules.diagrams.infrastructure.persistence.diagram_asset_repository import DiagramAssetRepositoryDep
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.diagrams.presenter.dtos.diagram_dto import (
    DiagramAssetResponseDto,
    RegenerateDiagramRequestDto,
    SwitchFormatRequestDto,
)
from src.modules.diagrams.usecases.diagram_asset_usecases import DiagramAssetUsecases
from src.modules.diagrams.usecases.generate_diagram_usecase import GenerateDiagramUsecase
from src.modules.shared.domain.value_objects.task_status import TaskStatus
from src.modules.tasks.infrastructure.persistence.task_repository import ITaskRepoDep
from src.modules.tasks.ports.output.task_repository import ITaskRepository

diagram_router = APIRouter(tags=["diagrams"])


def get_diagram_usecases(
    repository: DiagramAssetRepositoryDep,
    task_repository: ITaskRepoDep,
    renderer: DiagramRendererDep,
) -> DiagramAssetUsecases:
    return DiagramAssetUsecases(repository, task_repository, renderer)


@diagram_router.get("/tasks/{task_id}/diagrams", response_model=list[DiagramAssetResponseDto])
async def list_task_diagrams(
    task_id: uuid.UUID,
    usecases: DiagramAssetUsecases = Depends(get_diagram_usecases),
):
    assets = usecases.list_diagrams(task_id)
    return [DiagramAssetResponseDto.from_entity(a) for a in assets]


@diagram_router.post(
    "/tasks/{task_id}/diagrams/{slot_id}/switch-format",
    response_model=DiagramAssetResponseDto,
)
async def switch_diagram_format(
    task_id: uuid.UUID,
    slot_id: str,
    body: SwitchFormatRequestDto,
    usecases: DiagramAssetUsecases = Depends(get_diagram_usecases),
):
    asset = await usecases.switch_format(task_id, slot_id, body.target_format)
    return DiagramAssetResponseDto.from_entity(asset)


@diagram_router.post(
    "/tasks/{task_id}/diagrams/{slot_id}/upload",
    response_model=DiagramAssetResponseDto,
)
async def upload_diagram_replacement(
    task_id: uuid.UUID,
    slot_id: str,
    file: UploadFile = File(...),
    usecases: DiagramAssetUsecases = Depends(get_diagram_usecases),
):
    content = await file.read()
    if not content:
        raise BadRequestException("Uploaded file is empty")
    asset = await usecases.replace_by_upload(task_id, slot_id, content, file.filename or "uploaded.drawio")
    return DiagramAssetResponseDto.from_entity(asset)


@diagram_router.post(
    "/tasks/{task_id}/diagrams/{slot_id}/regenerate",
    response_model=DiagramAssetResponseDto,
)
async def regenerate_diagram(
    request: Request,
    task_id: uuid.UUID,
    slot_id: str,
    body: RegenerateDiagramRequestDto,
    task_repo: ITaskRepoDep,
    revision_repo: IRevisionRepoDep,
    diagram_repo: DiagramAssetRepositoryDep,
    renderer: DiagramRendererDep,
):
    task = task_repo.get(task_id)
    if not task:
        raise NotFoundException(f"Task '{task_id}' not found")

    runner: LangGraphWorkflowRunner | None = getattr(request.app.state, "workflow_runner", None)
    revisions = revision_repo.list_by_task(task_id)
    latest_rev = revisions[-1] if revisions else None

    # If workflow is currently in review, resume graph with target="diagram" (E4-S5, E7-S7)
    if runner and task.status == TaskStatus.AWAITING_REVIEW:
        rounds = sum(1 for r in revisions if (r.metadata or {}).get("review"))
        command = {
            "action": "revise",
            "revision_id": str(latest_rev.id) if latest_rev else "",
            "feedback": body.feedback.strip() or f"Regenerate diagram for {slot_id}",
            "scope": {
                "target": "diagram",
                "diagram_slot_id": slot_id,
                "sections": [],
            },
            "round": rounds + 1,
        }
        await runner.resume(str(task_id), command)
        # Return existing asset (or latest after resume triggered)
        asset = diagram_repo.get_by_slot(task_id, slot_id)
        if asset:
            return DiagramAssetResponseDto.from_entity(asset)

    # Standalone fallback: execute GenerateDiagramUsecase directly
    outline = task.outline or {}
    sec_heading = slot_id
    sec_goal = ""
    for sec in outline.get("sections", []):
        if f"diagram_{sec.get('key')}" == slot_id or sec.get("key") == slot_id:
            sec_heading = sec.get("heading", slot_id)
            sec_goal = sec.get("goal", "")
            break

    from src.modules.agent.infrastructure.adapters import get_model_factory

    models = get_model_factory()
    uc = GenerateDiagramUsecase(models, renderer, diagram_repo)
    asset, _ = await uc.execute(
        task=task,
        slot_id=slot_id,
        section_heading=sec_heading,
        section_goal=sec_goal,
        feedback=body.feedback,
    )
    return DiagramAssetResponseDto.from_entity(asset)


@diagram_router.get("/assets/{asset_id}")
async def get_diagram_asset_file(
    asset_id: uuid.UUID,
    repository: DiagramAssetRepositoryDep,
    type: Literal["source", "svg", "png"] = Query("svg"),
    download: bool = Query(False),
):
    asset = repository.get(asset_id)
    if not asset:
        raise NotFoundException(f"Asset '{asset_id}' not found")

    clean_slot = asset.slot_id.replace("/", "_")

    if type == "source":
        if not asset.source_path or not Path(asset.source_path).is_file():
            raise NotFoundException("Source file not found on disk")
        ext = "drawio" if asset.format == "drawio" else "mmd"
        media_type = "application/xml" if asset.format == "drawio" else "text/plain"
        filename = f"{clean_slot}.{ext}"
        return FileResponse(
            asset.source_path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="attachment" if download else "inline",
        )

    if type == "png":
        if not asset.png_path or not Path(asset.png_path).is_file():
            raise NotFoundException("PNG file not found on disk")
        return FileResponse(
            asset.png_path,
            media_type="image/png",
            filename=f"{clean_slot}.png",
            content_disposition_type="attachment" if download else "inline",
        )

    # type == "svg"
    if not asset.svg_path or not Path(asset.svg_path).is_file():
        raise NotFoundException("SVG file not found on disk")
    return FileResponse(
        asset.svg_path,
        media_type="image/svg+xml",
        filename=f"{clean_slot}.svg",
        content_disposition_type="attachment" if download else "inline",
    )
