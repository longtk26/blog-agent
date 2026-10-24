"""Usecases for diagram asset retrieval, format switching, and upload replacement (E7-S6, E7-S7)."""

import base64
import hashlib
from pathlib import Path
import re
import uuid

from src.configs.config import config
from src.libs.exceptions import BadRequestException, NotFoundException
from src.modules.diagrams.domain.drawio_generator import generate_drawio_xml
from src.modules.diagrams.domain.drawio_validator import validate_drawio_xml
from src.modules.diagrams.domain.layout import compute_layout
from src.modules.diagrams.domain.mermaid_generator import generate_mermaid
from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec
from src.modules.diagrams.domain.svg_sanitizer import sanitize_svg_content
from src.modules.diagrams.ports.output.diagram_renderer import IDiagramRenderer
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.shared.domain.entities.diagram_entity import DiagramAssetEntity
from src.modules.tasks.ports.output.task_repository import ITaskRepository


class DiagramAssetUsecases:
    def __init__(
        self,
        repository: IDiagramAssetRepository,
        task_repository: ITaskRepository,
        renderer: IDiagramRenderer,
    ):
        self.repository = repository
        self.task_repository = task_repository
        self.renderer = renderer

    def get_diagram(self, asset_id: uuid.UUID) -> DiagramAssetEntity:
        asset = self.repository.get(asset_id)
        if not asset:
            raise NotFoundException(f"Diagram asset '{asset_id}' not found")
        return asset

    def list_diagrams(self, task_id: uuid.UUID) -> list[DiagramAssetEntity]:
        return self.repository.list_by_task(task_id)

    async def switch_format(self, task_id: uuid.UUID, slot_id: str, target_format: str) -> DiagramAssetEntity:
        """Switch diagram format (drawio <-> mermaid) and re-render."""
        if target_format not in ("drawio", "mermaid"):
            raise BadRequestException("target_format must be 'drawio' or 'mermaid'")

        asset = self.repository.get_by_slot(task_id, slot_id)
        if not asset:
            raise NotFoundException(f"Diagram slot '{slot_id}' not found for task '{task_id}'")

        if asset.format == target_format:
            return asset

        spec = DiagramSpec.model_validate(asset.spec)
        task_dir = Path(config.data_dir) / "assets" / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        clean_slot = slot_id.replace("/", "_")

        if target_format == "mermaid":
            mmd_code = generate_mermaid(spec)
            source_file = task_dir / f"{clean_slot}.mmd"
            source_file.write_text(mmd_code, encoding="utf-8")
            asset.source_path = str(source_file)
            asset.format = "mermaid"

            try:
                render_out = await self.renderer.render_mermaid(mmd_code)
                svg_file = task_dir / f"{clean_slot}.svg"
                svg_file.write_text(render_out.svg, encoding="utf-8")
                asset.svg_path = str(svg_file)
                asset.sha256 = render_out.sha256

                if render_out.png_bytes:
                    png_file = task_dir / f"{clean_slot}.png"
                    png_file.write_bytes(render_out.png_bytes)
                    asset.png_path = str(png_file)
            except Exception:
                pass
        else:  # drawio
            layout = compute_layout(spec)
            xml_content = generate_drawio_xml(spec, layout)
            source_file = task_dir / f"{clean_slot}.drawio"
            source_file.write_text(xml_content, encoding="utf-8")
            asset.source_path = str(source_file)
            asset.format = "drawio"

            render_out = await self.renderer.render_drawio(xml_content, embed_diagram=True)
            svg_file = task_dir / f"{clean_slot}.svg"
            svg_file.write_text(render_out.svg, encoding="utf-8")
            asset.svg_path = str(svg_file)
            asset.sha256 = render_out.sha256 or hashlib.sha256(render_out.svg.encode("utf-8")).hexdigest()

            if render_out.png_bytes:
                png_file = task_dir / f"{clean_slot}.png"
                png_file.write_bytes(render_out.png_bytes)
                asset.png_path = str(png_file)

        return self.repository.update(asset)

    async def replace_by_upload(
        self,
        task_id: uuid.UUID,
        slot_id: str,
        content_bytes: bytes,
        filename: str,
    ) -> DiagramAssetEntity:
        """Replace diagram by owner upload (.drawio or .svg with embedded diagram) (E7-S7)."""
        asset = self.repository.get_by_slot(task_id, slot_id)
        if not asset:
            raise NotFoundException(f"Diagram slot '{slot_id}' not found for task '{task_id}'")

        task_dir = Path(config.data_dir) / "assets" / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        clean_slot = slot_id.replace("/", "_")

        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

        if ext == "drawio" or filename.endswith(".xml"):
            xml_str = content_bytes.decode("utf-8", errors="replace")
            res = validate_drawio_xml(xml_str)
            if not res.is_valid:
                raise BadRequestException(f"Invalid draw.io XML: {', '.join(res.errors)}")

            source_file = task_dir / f"{clean_slot}.drawio"
            source_file.write_text(xml_str, encoding="utf-8")
            asset.source_path = str(source_file)
            asset.format = "drawio"

            render_out = await self.renderer.render_drawio(xml_str, embed_diagram=True)
            svg_file = task_dir / f"{clean_slot}.svg"
            svg_file.write_text(render_out.svg, encoding="utf-8")
            asset.svg_path = str(svg_file)
            asset.sha256 = render_out.sha256 or hashlib.sha256(render_out.svg.encode("utf-8")).hexdigest()

        elif ext == "svg":
            svg_str = content_bytes.decode("utf-8", errors="replace")
            cleaned_svg = sanitize_svg_content(svg_str)
            svg_file = task_dir / f"{clean_slot}.svg"
            svg_file.write_text(cleaned_svg, encoding="utf-8")
            asset.svg_path = str(svg_file)
            asset.sha256 = hashlib.sha256(cleaned_svg.encode("utf-8")).hexdigest()

        else:
            raise BadRequestException("Uploaded file must be .drawio, .xml, or .svg")

        return self.repository.update(asset)
