import os

# Test settings must win over any developer .env file (env vars take priority over dotenv).
TEST_DB_URL = os.environ.get("TEST_DB_URL")
os.environ["DB_URL"] = TEST_DB_URL or "postgresql://unused:unused@127.0.0.1:1/unused"
os.environ.update(
    {
        "ENV": "test",
        "DEBUG": "true",
        "LOG_JSON": "false",
        "AGENT_API_KEY": "",
        "LANGSMITH_TRACING": "false",
        "LLM_DEFAULT_MODEL": "",
        "LLM_PLANNER_MODEL": "",
        "LLM_WRITER_MODEL": "",
        "LLM_FAST_MODEL": "",
        "LLM_JUDGE_MODEL": "",
        "CHECKPOINT_SCHEMA": "langgraph_test",
    }
)
