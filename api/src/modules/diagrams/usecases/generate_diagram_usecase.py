"""Usecase to generate, layout, validate, render, and persist diagram assets (Epic 7)."""

import hashlib
import os
from pathlib import Path
import uuid
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage

from src.configs.config import config
from src.configs.logger import get_logger
from src.modules.agent.ports.output.model_factory import IModelFactory, ModelRole
from src.modules.agent.prompts.diagram import diagram_messages
from src.modules.diagrams.domain.diagram_builder import build_diagram
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.mermaid_generator import choose_diagram_format, generate_mermaid
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from src.modules.diagrams.domain.spec_validator import validate_spec
from src.modules.diagrams.domain.svg_sanitizer import sanitize_svg_content
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity
from src.modules.shared.domain.entities.writing_task_entity import WritingTaskEntity

logger = get_logger(__name__)


class GenerateDiagramUsecase:
    def __init__(
        self,
        models: IModelFactory,
        renderer: IDiagramRenderer,
        repository: IDiagramAssetRepository,
    ):
        self.models = models
        self.renderer = renderer
        self.repository = repository

    async def execute(
        self,
        task: WritingTaskEntity,
        slot_id: str,
        section_heading: str,
        section_goal: str,
        section_text: str | None = None,
        claims_text: str | None = None,
        feedback: str | None = None,
        forced_format: str | None = None,
    ) -> tuple[DiagramAssetEntity, str]:
        """Generate diagram for a slot, return (asset_entity, markdown_snippet)."""
        # 1. Structured LLM generation with repair loop (E7-S1)
        spec = await self._generate_spec_with_repair(
            article_title=task.topic,
            section_heading=section_heading,
            section_goal=section_goal,
            section_text=section_text,
            claims_text=claims_text,
            feedback=feedback,
        )

        # 2. Format selection (E7-S5)
        format_choice = forced_format or choose_diagram_format(spec, task.diagram_format)

        # 3. Output files directory: data/assets/<task_id>/
        task_dir = Path(config.data_dir) / "assets" / str(task.id)
        task_dir.mkdir(parents=True, exist_ok=True)

        asset_id = uuid.uuid4()
        clean_slot = slot_id.replace("/", "_")

        source_path = ""
        svg_path = ""
        png_path = ""
        sha256_hash = ""
        markdown_snippet = ""

        if format_choice == "mermaid":
            mmd_code = generate_mermaid(spec)
            source_file = task_dir / f"{clean_slot}.mmd"
            source_file.write_text(mmd_code, encoding="utf-8")
            source_path = str(source_file)

            # Render to SVG & PNG
            svg_content = ""
            png_bytes = None
            try:
                render_out = await self.renderer.render_mermaid(mmd_code)
                svg_content = render_out.svg
                png_bytes = render_out.png_bytes
                sha256_hash = render_out.sha256
            except Exception as exc:
                logger.warning(f"Mermaid rendering via renderer failed: {exc}")
                # Fallback to direct SVG wrapper
                svg_content = f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"><text>{spec.title}</text></svg>'
                sha256_hash = hashlib.sha256(mmd_code.encode("utf-8")).hexdigest()

            svg_file = task_dir / f"{clean_slot}.svg"
            svg_file.write_text(svg_content, encoding="utf-8")
            svg_path = str(svg_file)

            if png_bytes:
                png_file = task_dir / f"{clean_slot}.png"
                png_file.write_bytes(png_bytes)
                png_path = str(png_file)

            markdown_snippet = f"\n```mermaid\n{mmd_code}\n```\n"

        else:  # drawio
            # Layout, routing and SVG happen in Python from one geometry; the renderer only rasterises.
            built = build_diagram(spec)
            source_file = task_dir / f"{clean_slot}.drawio"
            source_file.write_text(built.drawio_xml, encoding="utf-8")
            source_path = str(source_file)

            svg_content = sanitize_svg_content(built.svg)
            png_bytes = await self.renderer.render_png(svg_content)
            sha256_hash = hashlib.sha256(svg_content.encode("utf-8")).hexdigest()

            svg_file = task_dir / f"{clean_slot}.svg"
            svg_file.write_text(svg_content, encoding="utf-8")
            svg_path = str(svg_file)

            if png_bytes:
                png_file = task_dir / f"{clean_slot}.png"
                png_file.write_bytes(png_bytes)
                png_path = str(png_file)

            markdown_snippet = f'\n![{spec.title}](asset://{asset_id} "{spec.title}")\n'

        asset = DiagramAssetEntity(
            id=asset_id,
            task_id=task.id,
            slot_id=slot_id,
            format=format_choice,
            spec=spec.model_dump(),
            source_path=source_path,
            svg_path=svg_path,
            png_path=png_path or None,
            sha256=sha256_hash,
            validation_status="valid",
        )
        saved = self.repository.create(asset)
        return saved, markdown_snippet

    async def _generate_spec_with_repair(
        self,
        article_title: str,
        section_heading: str,
        section_goal: str,
        section_text: str | None,
        claims_text: str | None,
        feedback: str | None,
    ) -> DiagramSpec:
        model = self.models.get(ModelRole.PLANNER).with_structured_output(DiagramSpec)
        messages = diagram_messages(
            article_title=article_title,
            section_heading=section_heading,
            section_goal=section_goal,
            section_text=section_text,
            claims_text=claims_text,
            feedback=feedback,
        )

        spec = await model.ainvoke(messages)
        errors = validate_spec(spec)
        if not errors:
            return spec

        # Repair loop up to 2 retries (E7-S1)
        for attempt in range(2):
            logger.info(f"DiagramSpec validation attempt {attempt + 1} failed: {errors}. Retrying...")
            repair_messages = list(messages) + [
                AIMessage(content=spec.model_dump_json()),
                HumanMessage(
                    content=(
                        "Your DiagramSpec contained the following validation errors. Please fix them:\n"
                        + "\n".join(f"- {e}" for e in errors)
                    )
                ),
            ]
            spec = await model.ainvoke(repair_messages)
            errors = validate_spec(spec)
            if not errors:
                return spec

        logger.warning(f"DiagramSpec still had validation errors after 2 retries: {errors}. Proceeding with best-effort.")
        return spec
