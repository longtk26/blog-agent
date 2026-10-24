from typing import Annotated

from fastapi import Depends

from src.modules.publishing.infrastructure.adapters.google_thumbnail_generator import (
    GoogleThumbnailGenerator,
)
from src.modules.publishing.infrastructure.adapters.sanity_publisher import SanityPublisher
from src.modules.publishing.ports.output.publisher import IPublisher
from src.modules.shared.domain.entities import PublicationTarget


def get_sanity_publisher() -> SanityPublisher:
    return SanityPublisher(thumbnail_generator=GoogleThumbnailGenerator())


SanityPublisherDep = Annotated[SanityPublisher, Depends(get_sanity_publisher)]


class PublisherRegistry:
    def __init__(self, sanity_publisher: SanityPublisherDep):
        self._publishers: dict[str, IPublisher] = {
            PublicationTarget.SANITY.value: sanity_publisher,
        }

    def get(self, destination: PublicationTarget | str) -> IPublisher | None:
        target = str(destination).lower()
        return self._publishers.get(target)


PublisherRegistryDep = Annotated[PublisherRegistry, Depends(PublisherRegistry)]

__all__ = [
    "GoogleThumbnailGenerator",
    "SanityPublisher",
    "get_sanity_publisher",
    "SanityPublisherDep",
    "PublisherRegistry",
    "PublisherRegistryDep",
]
