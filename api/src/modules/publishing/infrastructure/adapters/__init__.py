from typing import Annotated

from fastapi import Depends

from src.modules.publishing.infrastructure.adapters.devto_publisher import DevtoPublisher
from src.modules.publishing.infrastructure.adapters.google_thumbnail_generator import (
    GoogleThumbnailGenerator,
)
from src.modules.publishing.infrastructure.adapters.sanity_publisher import SanityPublisher
from src.modules.publishing.ports.output.publisher import IPublisher
from src.modules.shared.domain.entities import PublicationTarget


def get_sanity_publisher() -> SanityPublisher:
    return SanityPublisher(thumbnail_generator=GoogleThumbnailGenerator())


SanityPublisherDep = Annotated[SanityPublisher, Depends(get_sanity_publisher)]


def get_devto_publisher(sanity_publisher: SanityPublisherDep) -> DevtoPublisher:
    return DevtoPublisher(asset_uploader=sanity_publisher)


DevtoPublisherDep = Annotated[DevtoPublisher, Depends(get_devto_publisher)]


class PublisherRegistry:
    def __init__(
        self,
        sanity_publisher: SanityPublisherDep,
        devto_publisher: DevtoPublisherDep,
    ):
        self._publishers: dict[str, IPublisher] = {
            PublicationTarget.SANITY.value: sanity_publisher,
            PublicationTarget.DEVTO.value: devto_publisher,
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
    "DevtoPublisher",
    "get_devto_publisher",
    "DevtoPublisherDep",
    "PublisherRegistry",
    "PublisherRegistryDep",
]
