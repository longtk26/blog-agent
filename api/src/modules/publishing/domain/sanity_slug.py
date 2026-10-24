import re

from src.libs.exceptions import BadRequestException, ErrorCode

SANITY_SLUG_REGEX = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")


def validate_sanity_slug(slug: str) -> str:
    """Sanity _id validation: ^[a-z0-9][a-z0-9-]{2,79}$ with no dots."""
    if not slug or not SANITY_SLUG_REGEX.match(slug) or "." in slug:
        raise BadRequestException(
            f"Slug '{slug}' is not valid for Sanity document ID. It must be 3-80 chars, lowercase alphanumeric and hyphens only, with no dots.",
            code=ErrorCode.VALIDATION_ERROR,
        )
    return slug
