from typing import TypedDict


class BlogState(TypedDict, total=False):
    """Checkpointed workflow state. Keep it small: page text, claims and drafts live in DB tables."""

    task_id: str
    mode: str
    plan: dict                  # ResearchPlanOut as dict (questions + queries)
    round: int                  # current search round (1-based)
    pending_queries: list[dict]  # PlannedQuery dicts to run in the next `search`
    done_queries: list[str]
    gaps: list[str]             # question ids without strong evidence
    brief_id: str
    promotion: dict | None      # owner input when a research-only task is promoted
