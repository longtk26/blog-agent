import json
import os
from pathlib import Path

from src.configs.logger import get_logger
from src.modules.shared.domain.entities import ArticleRevisionEntity

logger = get_logger(__name__)


class BlogsExporter:
    """Exports published posts to local blogs/ folder and maintains .publish-meta.json (E5-S7)."""

    def __init__(self, blogs_dir: str | Path, enabled: bool = False):
        self.blogs_dir = Path(blogs_dir)
        self.enabled = enabled

    def is_available(self) -> bool:
        return self.enabled and self.blogs_dir.is_dir()

    def export(
        self,
        revision: ArticleRevisionEntity,
        sanity_id: str,
        rendered_markdown: str,
    ) -> Path | None:
        if not self.is_available():
            return None

        # Determine folder name: series name or slug
        series_info = (revision.metadata or {}).get("series") or {}
        series_name = series_info.get("name") if isinstance(series_info, dict) else None
        folder_name = self._sanitize_folder_name(series_name) if series_name else revision.slug
        folder_dir = self.blogs_dir / folder_name
        folder_dir.mkdir(parents=True, exist_ok=True)

        meta_file = self.blogs_dir / ".publish-meta.json"
        meta = self._read_meta(meta_file)
        meta_key = f"{folder_name}/{revision.slug}"

        target_file = folder_dir / f"{revision.slug}.md"

        # Check if file exists and wasn't created by this agent (not in .publish-meta.json)
        if target_file.exists() and meta_key not in meta:
            logger.warning(
                f"File '{target_file}' exists and was not created by blog-agent. Writing to .agent.md instead."
            )
            target_file = folder_dir / f"{revision.slug}.agent.md"

        # Write rendered markdown atomically
        self._write_atomic(target_file, rendered_markdown)

        # Update .publish-meta.json atomically
        current_entry = meta.get(meta_key, {})
        current_entry["sanity"] = sanity_id
        meta[meta_key] = current_entry
        self._write_meta(meta_file, meta)

        logger.info(f"Exported post to '{target_file}' and updated .publish-meta.json")
        return target_file

    def remove_meta(self, folder_name: str, slug: str) -> None:
        if not self.is_available():
            return
        meta_file = self.blogs_dir / ".publish-meta.json"
        meta = self._read_meta(meta_file)
        meta_key = f"{folder_name}/{slug}"
        if meta_key in meta:
            del meta[meta_key]
            self._write_meta(meta_file, meta)

    def _read_meta(self, meta_file: Path) -> dict[str, dict]:
        if not meta_file.exists():
            return {}
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Failed to read {meta_file}: {exc}")
            return {}

    def _write_meta(self, meta_file: Path, meta: dict[str, dict]) -> None:
        content = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
        self._write_atomic(meta_file, content)

    def _write_atomic(self, file_path: Path, content: str) -> None:
        temp_file = file_path.with_name(f".{file_path.name}.tmp.{os.getpid()}")
        try:
            temp_file.write_text(content, encoding="utf-8")
            temp_file.replace(file_path)
        except Exception:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise

    @staticmethod
    def _sanitize_folder_name(name: str) -> str:
        clean = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
        return clean.strip("_") or "default"
