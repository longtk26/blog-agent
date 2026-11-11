from typing import Annotated

from fastapi import Depends

from src.modules.diagrams.infrastructure.adapters.diagram_renderer_adapter import (
    DiagramRendererDep,
)
from src.modules.diagrams.infrastructure.persistence.diagram_asset_repository import (
    DiagramAssetRepository,
)
from src.modules.diagrams.ports.output.diagram_repository import IDiagramAssetRepository
from src.modules.publishing.infrastructure.adapters.devto_publisher import DevtoPublisher
from src.modules.publishing.infrastructure.adapters.google_thumbnail_generator import (
    GoogleThumbnailGenerator,
)
from src.configs import config
from src.modules.publishing.infrastructure.adapters.s3_asset_uploader import S3AssetUploader
from src.modules.publishing.infrastructure.adapters.sanity_publisher import SanityPublisher
from src.modules.publishing.ports.output.publisher import IPublisher
from src.modules.shared.domain.entities import PublicationTarget

DiagramAssetRepoDep = Annotated[IDiagramAssetRepository, Depends(DiagramAssetRepository)]


def get_sanity_publisher() -> SanityPublisher:
    return SanityPublisher(thumbnail_generator=GoogleThumbnailGenerator())


SanityPublisherDep = Annotated[SanityPublisher, Depends(get_sanity_publisher)]


def get_devto_publisher(
    sanity_publisher: SanityPublisherDep,
    diagram_renderer: DiagramRendererDep,
    diagram_repo: DiagramAssetRepoDep,
) -> DevtoPublisher:
    # Epic 12: diagrams/images in the Dev.to body go to S3 (permanent public URLs) when it is configured.
    uploader = S3AssetUploader() if config.resolved_image_host == "s3" else sanity_publisher
    return DevtoPublisher(
        asset_uploader=uploader,
        diagram_renderer=diagram_renderer,
        diagram_repo=diagram_repo,
    )


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
    "S3AssetUploader",
    "SanityPublisher",
    "get_sanity_publisher",
    "SanityPublisherDep",
    "DevtoPublisher",
    "get_devto_publisher",
    "DevtoPublisherDep",
    "PublisherRegistry",
    "PublisherRegistryDep",
]
