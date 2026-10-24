import pytest

from src.libs.exceptions import BadRequestException
from src.modules.publishing.domain.sanity_slug import validate_sanity_slug


def test_valid_sanity_slugs():
    assert validate_sanity_slug("lora-fine-tuning") == "lora-fine-tuning"
    assert validate_sanity_slug("abc") == "abc"
    assert validate_sanity_slug("a-b-c") == "a-b-c"
    assert validate_sanity_slug("peft-tutorial-2026") == "peft-tutorial-2026"
    assert validate_sanity_slug("a" * 80) == "a" * 80


@pytest.mark.parametrize(
    "slug",
    [
        "with.dot",
        "has_underscore",
        "UPPERCASE",
        "ab",  # too short (min 3 chars)
        "a" * 81,  # too long (max 80 chars)
        "-starts-with-dash",
        "",
        "spaces in slug",
    ],
)
def test_invalid_sanity_slugs_raise(slug):
    with pytest.raises(BadRequestException):
        validate_sanity_slug(slug)
