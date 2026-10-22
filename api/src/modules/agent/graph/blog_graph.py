from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.graph.state import BlogState
from src.modules.agent.nodes.research import ResearchNodes
from src.modules.agent.nodes.writing import WritingNodes

GRAPH_NAME = "blog_task"


def build_blog_graph(deps: WorkflowDeps, checkpointer: BaseCheckpointSaver | None):
    """Research: plan → (search → extract → assess → coverage)* → synthesize → [await_promotion]
    Writing:  outline → [review_outline] → draft → (validate → judge → self_revise)* → save_revision → await_review
    """
    research = ResearchNodes(deps)
    writing = WritingNodes(deps)
    builder = StateGraph(BlogState)

    builder.add_node("plan_research", research.plan_research)
    builder.add_node("search", research.search)
    builder.add_node("extract_pages", research.extract_pages)
    builder.add_node("assess_sources", research.assess_sources)
    builder.add_node("check_coverage", research.check_coverage)
    builder.add_node("synthesize_research", research.synthesize_research)
    builder.add_node("await_promotion", research.await_promotion)
    # Node names are part of persisted checkpoints: keep "outline" stable (Epic 2 threads paused there).
    builder.add_node("outline", writing.outline)
    builder.add_node("review_outline", writing.review_outline)
    builder.add_node("draft_article", writing.draft_article)
    builder.add_node("validate_draft", writing.validate_draft)
    builder.add_node("judge_draft", writing.judge_draft)
    builder.add_node("self_revise", writing.self_revise)
    builder.add_node("save_revision", writing.save_revision)
    builder.add_node("await_review", writing.await_review)

    builder.add_edge(START, "plan_research")
    builder.add_edge("plan_research", "search")
    builder.add_edge("search", "extract_pages")
    builder.add_edge("extract_pages", "assess_sources")
    builder.add_edge("assess_sources", "check_coverage")
    builder.add_conditional_edges("check_coverage", research.route_after_coverage, ["search", "synthesize_research"])
    builder.add_conditional_edges("synthesize_research", research.route_after_synthesis, ["await_promotion", "outline"])
    builder.add_edge("await_promotion", "outline")

    builder.add_conditional_edges("outline", writing.route_after_outline, ["review_outline", "draft_article"])
    builder.add_edge("review_outline", "draft_article")
    builder.add_edge("draft_article", "validate_draft")
    builder.add_edge("validate_draft", "judge_draft")
    builder.add_conditional_edges("judge_draft", writing.route_after_judge, ["self_revise", "save_revision"])
    builder.add_edge("self_revise", "validate_draft")
    builder.add_edge("save_revision", "await_review")
    builder.add_edge("await_review", END)

    return builder.compile(checkpointer=checkpointer, name=GRAPH_NAME)
