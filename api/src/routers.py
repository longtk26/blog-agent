from src.modules.health.presenter import health_router
from src.modules.research.presenter import research_router
from src.modules.tasks.presenter import task_router

all_router = [health_router, task_router, research_router]
