from src.modules.articles.presenter import article_router
from src.modules.health.presenter import health_router
from src.modules.publishing.presenter import publishing_router
from src.modules.research.presenter import research_router
from src.modules.reviews.presenter import review_router
from src.modules.styles.presenter import style_router
from src.modules.tasks.presenter import task_router

all_router = [health_router, task_router, research_router, article_router, review_router, style_router, publishing_router]
