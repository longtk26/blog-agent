import pytest
from pydantic import ValidationError

from src.modules.tasks.presenter.dtos import CreateTaskRequestDto


def test_defaults_and_entity_mapping():
    dto = CreateTaskRequestDto(topic="  Explain LoRA  ", budgets={"max_queries": 3})
    entity = dto.to_entity()
    assert entity.topic == "Explain LoRA"
    assert entity.mode == "article" and entity.status == "queued"
    assert entity.budgets.max_queries == 3 and entity.budgets.max_sources == 15


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "abc"},
        {"topic": "valid topic", "language": "english"},
        {"topic": "valid topic", "mode": "publish_now"},
        {"topic": "valid topic", "budgets": {"max_queries": 0}},
        {"topic": "valid topic", "budgets": {"max_queries": 999}},
        {"topic": "valid topic", "publication_targets": ["medium"]},
        {"topic": "valid topic", "extra": True},
    ],
)
def test_invalid_payloads_rejected(payload):
    with pytest.raises(ValidationError):
        CreateTaskRequestDto(**payload)
