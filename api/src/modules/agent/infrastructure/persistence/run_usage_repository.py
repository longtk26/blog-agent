import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from src.modules.shared.domain.entities import RunUsageEntity
from src.modules.shared.infrastructure.models import RunUsageModel


class RunUsageRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, entity: RunUsageEntity) -> RunUsageEntity:
        model = RunUsageModel(
            id=entity.id,
            task_id=entity.task_id,
            run_id=entity.run_id,
            node=entity.node,
            model=entity.model,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
            cached_tokens=entity.cached_tokens,
            total_tokens=entity.total_tokens,
            latency_ms=entity.latency_ms,
            cost_usd=entity.cost_usd,
        )
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)

    def list_by_task(self, task_id: uuid.UUID) -> list[RunUsageEntity]:
        stmt = (
            select(RunUsageModel)
            .where(RunUsageModel.task_id == task_id)
            .order_by(RunUsageModel.created_at.asc())
        )
        return [self._to_entity(m) for m in self.session.exec(stmt).all()]

    def total_cost_for_task(self, task_id: uuid.UUID) -> float:
        stmt = select(func.sum(RunUsageModel.cost_usd)).where(RunUsageModel.task_id == task_id)
        result = self.session.exec(stmt).one_or_none()
        return round(float(result or 0.0), 6)

    def total_cost_by_tasks(self, task_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
        if not task_ids:
            return {}
        stmt = (
            select(RunUsageModel.task_id, func.sum(RunUsageModel.cost_usd))
            .where(RunUsageModel.task_id.in_(task_ids))
            .group_by(RunUsageModel.task_id)
        )
        results = self.session.exec(stmt).all()
        costs = {row[0]: round(float(row[1] or 0.0), 6) for row in results}
        return {tid: costs.get(tid, 0.0) for tid in task_ids}

    def usage_breakdown(self, task_id: uuid.UUID) -> dict[str, Any]:
        """Returns per-stage / node breakdown of tokens, latency, cost, and LLM calls."""
        records = self.list_by_task(task_id)
        by_stage: dict[str, dict[str, Any]] = {}
        total_input = 0
        total_output = 0
        total_cached = 0
        total_tokens = 0
        total_latency_ms = 0
        total_cost = 0.0

        for r in records:
            stage = r.node or "other"
            if stage not in by_stage:
                by_stage[stage] = {
                    "stage": stage,
                    "calls": 0,
                    "models": set(),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cached_tokens": 0,
                    "total_tokens": 0,
                    "latency_ms": 0,
                    "cost_usd": 0.0,
                }
            by_stage[stage]["calls"] += 1
            by_stage[stage]["models"].add(r.model)
            by_stage[stage]["input_tokens"] += r.input_tokens
            by_stage[stage]["output_tokens"] += r.output_tokens
            by_stage[stage]["cached_tokens"] += r.cached_tokens
            by_stage[stage]["total_tokens"] += r.total_tokens
            by_stage[stage]["latency_ms"] += r.latency_ms
            by_stage[stage]["cost_usd"] += r.cost_usd

            total_input += r.input_tokens
            total_output += r.output_tokens
            total_cached += r.cached_tokens
            total_tokens += r.total_tokens
            total_latency_ms += r.latency_ms
            total_cost += r.cost_usd

        # format list
        stages_list = []
        for s in by_stage.values():
            stages_list.append(
                {
                    "stage": s["stage"],
                    "calls": s["calls"],
                    "models": sorted(list(s["models"])),
                    "input_tokens": s["input_tokens"],
                    "output_tokens": s["output_tokens"],
                    "cached_tokens": s["cached_tokens"],
                    "total_tokens": s["total_tokens"],
                    "latency_ms": s["latency_ms"],
                    "cost_usd": round(s["cost_usd"], 6),
                }
            )

        return {
            "task_id": str(task_id),
            "stages": stages_list,
            "total_calls": len(records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cached_tokens": total_cached,
            "total_tokens": total_tokens,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": round(total_cost, 6),
            "is_estimate": True,
        }

    @staticmethod
    def _to_entity(model: RunUsageModel) -> RunUsageEntity:
        return RunUsageEntity(
            id=model.id,
            task_id=model.task_id,
            run_id=model.run_id,
            node=model.node,
            model=model.model,
            input_tokens=model.input_tokens,
            output_tokens=model.output_tokens,
            cached_tokens=model.cached_tokens,
            total_tokens=model.total_tokens,
            latency_ms=model.latency_ms,
            cost_usd=round(model.cost_usd, 6),
            created_at=model.created_at,
        )
