from src.configs.logger import get_logger
from src.modules.research.ports.output import ExtractedPage, ExtractionError, IPageExtractor

logger = get_logger(__name__)


class ChainedPageExtractor(IPageExtractor):
    def __init__(self, extractors: list[IPageExtractor]):
        self.extractors = extractors
        self.name = "+".join(e.name for e in extractors)

    async def extract(self, url: str) -> ExtractedPage:
        errors = []
        for extractor in self.extractors:
            try:
                return await extractor.extract(url)
            except ExtractionError as exc:
                errors.append(f"{extractor.name}: {exc}")
                logger.info("Extractor failed, trying next", extra={"context": {"extractor": extractor.name, "error": str(exc)}})
        raise ExtractionError("; ".join(errors) or "No extractor configured")
