"""Prompts for DiagramSpec structured generation (E7-S1)."""

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.modules.diagrams.domain.schemas.diagram_spec import DiagramSpec


DIAGRAM_SPEC_SYSTEM = """You are an expert technical diagram designer.
Your task is to design a clear, readable, production-grade technical diagram for a technical blog post.
The diagram must be modeled as a DiagramSpec structured object.

Rules and Guidelines:
1. Diagram Type:
   - "flowchart": step-by-step lifecycles, pipelines, decision trees.
   - "architecture": system architectures, service topologies, multi-tier data flows.
   - "sequence": protocol interactions, API calls, client-server turn-taking.
2. Direction:
   - Use "LR" (left-to-right) for data pipelines and multi-stage architectures.
   - Use "TB" (top-to-bottom) for hierarchical breakdowns and trees.
3. Groups:
   - Use groups/clusters for logical tiers (e.g. "Data Preparation", "Model Backbone", "Storage Tier").
   - Each group must have a unique ID and descriptive label.
   - Do NOT create cyclic group hierarchies.
4. Nodes:
   - Concise labels with line breaks where appropriate. Max 60 chars per line.
   - Use node kinds accurately:
     * process: general computation or action
     * decision: branch point or evaluation
     * datastore: database, dataset, cache, GGUF/model weights
     * service: external or backend service/daemon (e.g. Ollama, FastAPI)
     * actor: human user or client
     * external: third-party system
     * note: informative note (can be standalone)
   - Every node (except 'note') MUST be connected to at least one edge.
   - IDs must be unique strings (e.g. "raw_data", "sft_step", "ollama_srv"). IDs "0" and "1" are reserved.
   - At most 20 nodes for optimal readability.
5. Edges:
   - from and to must reference existing node IDs.
   - Short edge labels describing data flow or protocol (e.g. "HTTP", "Token IDs", "merge").
6. Sequence diagrams (if type == "sequence"):
   - Define participants with IDs and labels.
   - Define ordered messages with from, to, and label. Set return=True for return messages.
7. Style preset:
   - Always "owner_dark".
"""


def diagram_messages(
    article_title: str,
    section_heading: str,
    section_goal: str,
    section_text: str | None = None,
    claims_text: str | None = None,
    feedback: str | None = None,
) -> list[BaseMessage]:
    context_parts = [
        f"Article Title: {article_title}",
        f"Section Heading: {section_heading}",
        f"Section Goal: {section_goal}",
    ]
    if section_text:
        context_parts.append(f"Section Text:\n{section_text[:2000]}")
    if claims_text:
        context_parts.append(f"Key Claims / Evidence:\n{claims_text[:1000]}")
    if feedback:
        context_parts.append(f"Owner Feedback for Regeneration:\n{feedback}")

    prompt = (
        "Design a DiagramSpec for the following technical section that best illustrates its core mechanism:\n\n"
        + "\n\n".join(context_parts)
    )
    return [SystemMessage(content=DIAGRAM_SPEC_SYSTEM), HumanMessage(content=prompt)]
