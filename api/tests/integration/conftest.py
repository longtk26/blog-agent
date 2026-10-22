import pytest
import pytest_asyncio

from tests.conftest import TEST_DB_URL


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            if not TEST_DB_URL:
                item.add_marker(pytest.mark.skip(reason="set TEST_DB_URL to run integration tests"))


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    if not TEST_DB_URL:
        yield
        return
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(migrated_db):
    if TEST_DB_URL:
        import psycopg

        with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
            conn.execute("TRUNCATE writing_tasks, style_guides CASCADE")
    yield


@pytest_asyncio.fixture
async def checkpointer():
    from src.libs.database import CheckpointerManager

    manager = CheckpointerManager(TEST_DB_URL, schema="langgraph_test")
    await manager.open()
    yield manager
    await manager.close()
