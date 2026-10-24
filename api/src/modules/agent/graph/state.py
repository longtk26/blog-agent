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
    outline: dict               # sections + requirement coverage (also stored on the task)
    review_outline: bool
    needs_revision: bool        # judge verdict for the bounded self-revision loop
    revision_id: str            # latest saved ArticleRevision
    review: dict | None         # owner decision on resume from awaiting_review (Epic 4)
    review_target: str          # research | outline | draft | diagram | metadata, for the current review round
    review_feedback: str
    revise_keys: list[str]      # draft section keys the review round may rewrite
    research_window: dict       # follow-up research budget: base counters + limits (see ResearchNodes._limits)
    focus_questions: list[str]  # question ids follow-up research must cover
    publish: dict | None        # owner input on resume from awaiting_publish (Epic 5)
