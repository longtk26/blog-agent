from typing import Protocol
import uuid

from src.modules.shared.domain.entities import WritingSampleEntity


class IWritingSampleRepository(Protocol):
    """Output port for writing samples repository."""

    def create(self, sample: WritingSampleEntity) -> WritingSampleEntity:
        ...

    def update(self, sample: WritingSampleEntity) -> WritingSampleEntity:
        ...

    def get(self, sample_id: uuid.UUID) -> WritingSampleEntity | None:
        ...

    def get_by_origin_and_remote(self, origin: str, remote_id: str) -> WritingSampleEntity | None:
        ...

    def list_all(self, approved_only: bool = False) -> list[WritingSampleEntity]:
        ...

    def count(self) -> int:
        ...

    def get_sanity_post_ids(self) -> set[str]:
        ...

    def delete(self, sample_id: uuid.UUID) -> bool:
        ...
