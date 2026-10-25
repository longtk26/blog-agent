import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from src.configs import config
from src.configs.logger import Redactor
from src.libs.database.session import SessionDep
from src.modules.agent.infrastructure.adapters import get_tracing
from src.modules.agent.ports.output import ITracing, ITracingDep
from src.modules.diagrams.infrastructure.persistence.diagram_asset_repository import DiagramAssetRepository
from src.modules.publishing.infrastructure.persistence.publication_repository import PublicationRepository
from src.modules.research.infrastructure.persistence.source_repository import SourceRepository
from src.modules.shared.domain.entities import SourceStatus
from src.modules.shared.infrastructure.models import (
    PublicationModel,
    ResearchSourceModel,
    RunUsageModel,
    TaskEventModel,
    WritingTaskModel,
)
from src.modules.shared.domain.value_objects import TaskStatus

stats_router = APIRouter(prefix="/stats", tags=["stats"])


class StageDurationDto(BaseModel):
    stage: str
    avg_duration_s: float
    p90_duration_s: float
    samples: int


class ToolErrorRateDto(BaseModel):
    tool: str
    calls: int
    errors: int
    error_rate: float


class RecentFailureDto(BaseModel):
    task_id: uuid.UUID
    topic: str
    failed_stage: str | None
    error: str | None
    created_at: datetime
    trace_url: str | None = None


class OpsStatsResponseDto(BaseModel):
    period_days: int
    tasks_by_status: dict[str, int]
    stage_durations: list[StageDurationDto]
    avg_cost_per_task: float
    total_cost_period: float
    tool_error_rates: list[ToolErrorRateDto]
    recent_failures: list[RecentFailureDto]


@stats_router.get("", response_model=OpsStatsResponseDto)
async def get_ops_stats(
    session: SessionDep,
    tracing: ITracingDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    redactor = Redactor(config.secret_values())

    # 1. Tasks by status
    stmt_status = (
        select(WritingTaskModel.status, func.count(WritingTaskModel.id))
        .where(WritingTaskModel.created_at >= since)
        .group_by(WritingTaskModel.status)
    )
    status_counts = {str(k.value if hasattr(k, "value") else k): int(v) for k, v in session.exec(stmt_status).all()}

    # 2. Stage durations from task_events (type == 'node_finished')
    stmt_events = select(TaskEventModel.payload).where(
        TaskEventModel.type == "node_finished",
        TaskEventModel.created_at >= since,
    )
    finished_events = session.exec(stmt_events).all()

    durations_by_node: dict[str, list[float]] = {}
    for payload in finished_events:
        if isinstance(payload, dict):
            node = payload.get("node")
            ms = payload.get("duration_ms")
            if node and ms is not None and isinstance(ms, (int, float)):
                durations_by_node.setdefault(str(node), []).append(float(ms) / 1000.0)

    stage_durations: list[StageDurationDto] = []
    for node, durs in durations_by_node.items():
        if durs:
            sorted_durs = sorted(durs)
            p90_idx = int(0.9 * (len(sorted_durs) - 1))
            avg_s = round(sum(sorted_durs) / len(sorted_durs), 2)
            p90_s = round(sorted_durs[p90_idx], 2)
            stage_durations.append(
                StageDurationDto(
                    stage=node,
                    avg_duration_s=avg_s,
                    p90_duration_s=p90_s,
                    samples=len(durs),
                )
            )
    stage_durations.sort(key=lambda x: x.avg_duration_s, reverse=True)

    # 3. Usage & Cost
    stmt_cost = select(func.sum(RunUsageModel.cost_usd)).where(RunUsageModel.created_at >= since)
    total_cost = float(session.exec(stmt_cost).one_or_none() or 0.0)

    stmt_task_count = select(func.count(func.distinct(RunUsageModel.task_id))).where(
        RunUsageModel.created_at >= since
    )
    tasks_with_cost = int(session.exec(stmt_task_count).one_or_none() or 0)
    avg_cost = round(total_cost / max(tasks_with_cost, 1), 4)

    # 4. Tool error rates
    # Search tool
    total_sources = session.exec(
        select(func.count(ResearchSourceModel.id)).where(ResearchSourceModel.created_at >= since)
    ).one() or 0
    failed_sources = session.exec(
        select(func.count(ResearchSourceModel.id)).where(
            ResearchSourceModel.created_at >= since,
            ResearchSourceModel.status == SourceStatus.FAILED,
        )
    ).one() or 0
    search_rate = round(failed_sources / max(total_sources, 1), 4) if total_sources else 0.0

    # Extract tool: sources extracted vs failed
    extracted_sources = session.exec(
        select(func.count(ResearchSourceModel.id)).where(
            ResearchSourceModel.created_at >= since,
            ResearchSourceModel.status.in_([SourceStatus.EXTRACTED, SourceStatus.ASSESSED, SourceStatus.FAILED]),
        )
    ).one() or 0
    extract_rate = round(failed_sources / max(extracted_sources, 1), 4) if extracted_sources else 0.0

    # Diagram renderer
    from src.modules.shared.infrastructure.models import DiagramAssetModel
    total_diagrams = session.exec(
        select(func.count(DiagramAssetModel.id)).where(DiagramAssetModel.created_at >= since)
    ).one() or 0
    failed_diagrams = session.exec(
        select(func.count(DiagramAssetModel.id)).where(
            DiagramAssetModel.created_at >= since,
            DiagramAssetModel.validation_status == "failed",
        )
    ).one() or 0
    renderer_rate = round(failed_diagrams / max(total_diagrams, 1), 4) if total_diagrams else 0.0

    # Publishers (PublicationModel tracks updated_at / published_at)
    pub_time = func.coalesce(PublicationModel.updated_at, PublicationModel.published_at)
    total_pubs = session.exec(
        select(func.count(PublicationModel.id)).where(pub_time.is_not(None), pub_time >= since)
    ).one() or 0
    failed_pubs = session.exec(
        select(func.count(PublicationModel.id)).where(
            pub_time.is_not(None),
            pub_time >= since,
            PublicationModel.status == "failed",
        )
    ).one() or 0
    pub_rate = round(failed_pubs / max(total_pubs, 1), 4) if total_pubs else 0.0

    tool_error_rates = [
        ToolErrorRateDto(tool="search", calls=total_sources, errors=failed_sources, error_rate=search_rate),
        ToolErrorRateDto(tool="extract", calls=extracted_sources, errors=failed_sources, error_rate=extract_rate),
        ToolErrorRateDto(tool="renderer", calls=total_diagrams, errors=failed_diagrams, error_rate=renderer_rate),
        ToolErrorRateDto(tool="publishers", calls=total_pubs, errors=failed_pubs, error_rate=pub_rate),
    ]

    # 5. Recent failures
    stmt_failures = (
        select(WritingTaskModel)
        .where(WritingTaskModel.status == TaskStatus.FAILED)
        .order_by(WritingTaskModel.updated_at.desc())
        .limit(10)
    )
    failed_tasks = session.exec(stmt_failures).all()

    recent_failures: list[RecentFailureDto] = []
    for ft in failed_tasks:
        trace_url = await tracing.run_url(ft.last_run_id) if ft.last_run_id else None
        sanitized_error = redactor(ft.last_error) if ft.last_error else None
        recent_failures.append(
            RecentFailureDto(
                task_id=ft.id,
                topic=ft.topic,
                failed_stage=ft.failed_stage,
                error=sanitized_error,
                created_at=ft.updated_at,
                trace_url=trace_url,
            )
        )

    return OpsStatsResponseDto(
        period_days=days,
        tasks_by_status=status_counts,
        stage_durations=stage_durations,
        avg_cost_per_task=avg_cost,
        total_cost_period=round(total_cost, 4),
        tool_error_rates=tool_error_rates,
        recent_failures=recent_failures,
    )
