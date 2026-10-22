import uuid

import psycopg

from src.libs.database import CheckpointerManager
from src.modules.agent.graph import build_ping_graph
from tests.conftest import TEST_DB_URL

SCHEMA = "langgraph_test"


async def run_ping(manager: CheckpointerManager, thread_id: str) -> int:
    graph = build_ping_graph(manager.saver)
    state = await graph.ainvoke({}, config={"configurable": {"thread_id": thread_id}})
    return state["count"]


async def test_checkpoint_survives_restart_and_lives_in_own_schema():
    thread_id = f"t-{uuid.uuid4().hex[:8]}"

    first = CheckpointerManager(TEST_DB_URL, schema=SCHEMA)
    await first.open()
    assert await first.ping() is True
    assert await run_ping(first, thread_id) == 1
    await first.close()

    # Simulated API restart: brand-new pool + saver reads the persisted thread.
    second = CheckpointerManager(TEST_DB_URL, schema=SCHEMA)
    await second.open()
    assert await run_ping(second, thread_id) == 2
    await second.close()

    with psycopg.connect(TEST_DB_URL) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (SCHEMA,)
            )
        }
        public_tables = {
            row[0]
            for row in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        }
    assert {"checkpoints", "checkpoint_writes", "checkpoint_blobs", "checkpoint_migrations"} <= tables
    assert not public_tables & tables
