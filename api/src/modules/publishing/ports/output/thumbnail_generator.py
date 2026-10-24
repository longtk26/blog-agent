from typing import Protocol


class IThumbnailGenerator(Protocol):
    async def generate_thumbnail(
        self,
        title: str,
        description: str,
        table_of_contents: list[str],
        slug: str = "blog",
    ) -> tuple[bytes, str, str] | None:
        """Generate 16:9 thumbnail image based on title, description, and table of contents.

        Args:
            title: The blog article title.
            description: The blog article description.
            table_of_contents: Key section headings / outline topics.
            slug: Deterministic slug for naming the image file.

        Returns:
            Tuple of (image_bytes, filename, content_type) or None if disabled or failed.
        """
        ...
