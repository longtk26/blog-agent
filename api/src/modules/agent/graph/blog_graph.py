from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from src.modules.agent.graph.deps import WorkflowDeps
from src.modules.agent.graph.state import BlogState
from src.modules.agent.nodes.research import ResearchNodes

GRAPH_NAME = "blog_task"


def build_blog_graph(deps: WorkflowDeps, checkpointer: BaseCheckpointSaver | None):
    """plan → (search → extract → assess → coverage)* → synthesize → [await_promotion] → outline (Epic 3)."""
    research = ResearchNodes(deps)
    builder = StateGraph(BlogState)

    builder.add_node("plan_research", research.plan_research)
    builder.add_node("search", research.search)
    builder.add_node("extract_pages", research.extract_pages)
    builder.add_node("assess_sources", research.assess_sources)
    builder.add_node("check_coverage", research.check_coverage)
    builder.add_node("synthesize_research", research.synthesize_research)
    builder.add_node("await_promotion", research.await_promotion)
    builder.add_node("outline", research.outline)

    builder.add_edge(START, "plan_research")
    builder.add_edge("plan_research", "search")
    builder.add_edge("search", "extract_pages")
    builder.add_edge("extract_pages", "assess_sources")
    builder.add_edge("assess_sources", "check_coverage")
    builder.add_conditional_edges(
        "check_coverage", research.route_after_coverage, ["search", "synthesize_research"]
    )
    builder.add_conditional_edges(
        "synthesize_research", research.route_after_synthesis, ["await_promotion", "outline"]
    )
    builder.add_edge("await_promotion", "outline")
    builder.add_edge("outline", END)

    return builder.compile(checkpointer=checkpointer, name=GRAPH_NAME)
