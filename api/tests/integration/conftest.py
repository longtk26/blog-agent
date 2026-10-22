import pytest

from tests.conftest import TEST_DB_URL


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            if not TEST_DB_URL:
                item.add_marker(pytest.mark.skip(reason="set TEST_DB_URL to run integration tests"))
