import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.modules.shared.domain.entities import (
    WritingSampleEntity,
    StyleProfileEntity,
    StyleProfileData,
)
from src.modules.styles.usecases.style_profile_usecases import (
    GenerateStyleProfileUsecase,
    ActivateStyleProfileUsecase,
    UpdateStyleProfileUsecase,
    GetStyleProfileUsecase,
    ListStyleProfilesUsecase,
)


@pytest.fixture
def sample_repo():
    repo = MagicMock()
    repo.list_all.return_value = [
        WritingSampleEntity(
            id=uuid.uuid4(),
            origin="sanity",
            remote_id="post_1",
            title="Post 1",
            content="# Section 1\n\nDeep dive into architectures with diagrams and benchmarks.",
            approved_as_style_example=True,
        )
    ]
    return repo


@pytest.fixture
def profile_repo():
    repo = MagicMock()
    repo.get_active.return_value = None
    repo.list_all.return_value = []
    repo.get_next_version.return_value = 1
    return repo


@pytest.mark.asyncio
async def test_generate_style_profile_usecase(sample_repo, profile_repo):
    generated_data = StyleProfileData(
        tone="authoritative yet accessible",
        voice="first-person plural",
        heading_conventions="numbered sections",
        do=["Use concrete code examples"],
        dont=["Avoid buzzwords"],
    )

    saved_entity = StyleProfileEntity(
        id=uuid.uuid4(),
        version=1,
        is_active=True,
        name="Auto-generated Profile v1",
        profile_data=generated_data.__dict__,
        markdown_content=generated_data.to_markdown(),
    )
    profile_repo.create.return_value = saved_entity
    model_factory = MagicMock()

    usecase = GenerateStyleProfileUsecase(
        sample_repo=sample_repo,
        profile_repo=profile_repo,
        model_factory=model_factory,
    )

    from unittest.mock import patch
    with patch("src.modules.styles.usecases.style_profile_usecases.generate_style_profile_from_samples", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = generated_data
        result = await usecase.execute(name="Auto-generated Profile v1")

        assert result.version == 1
        assert result.is_active is True
        profile_repo.create.assert_called_once()
        mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_activate_profile_usecase(profile_repo):
    profile_id = uuid.uuid4()
    active_profile = StyleProfileEntity(
        id=profile_id,
        version=2,
        is_active=True,
        name="Profile 2",
    )
    profile_repo.activate.return_value = active_profile

    usecase = ActivateStyleProfileUsecase(profile_repo=profile_repo)
    result = await usecase.execute(profile_id)

    assert result.id == profile_id
    assert result.is_active is True
    profile_repo.activate.assert_called_once_with(profile_id)
