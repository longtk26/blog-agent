"""Prompts for DiagramSpec structured generation (E7-S1). Bump PROMPT_VERSION on any wording change."""

PROMPT_VERSION = "diagram-v2"

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.modules.diagrams.domain.icons import ICONS
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
   - For cloud architectures, use groups for real boundaries and nest them with 'parent':
     AWS: "AWS Cloud" > "Region" > "VPC (10.0.0.0/16)" > "Public Subnet" / "Private Subnet".
     An Internet Gateway belongs to the VPC (not a subnet); ALB and NAT Gateway to the public subnet; app servers and
     databases to the private subnet. Regional services (S3, ECR, Route 53, IAM, Parameter Store) sit in the Region,
     outside the VPC.
     Google Cloud: "Google Cloud" > "Project" > "Region" > "VPC network" > "Subnet". Managed services (Cloud Run,
     Cloud SQL, Cloud Storage, Pub/Sub, BigQuery) sit in the Project or Region, outside the VPC.
     Kubernetes: "EKS cluster"/"GKE cluster" > "Namespace: <name>" for pods, deployments, services, ingresses.
     Users and external systems (GitHub, third-party APIs, an external DB) stay outside every boundary.
     Do not create groups with a single node unless they are such a boundary. Use one cloud per diagram.
   - Each group must have a unique ID and descriptive label.
   - Do NOT create cyclic group hierarchies.
4. Nodes (REQUIRED, MUST NOT BE EMPTY):
   - For flowchart and architecture, you MUST define 3 to 15 DiagramNode objects in 'nodes'.
   - Concise labels with line breaks where appropriate. Max 60 chars per line.
   - Icons: set 'icon' for architecture components so they render as the official draw.io service icons.
     Allowed keys (write the family prefix, e.g. "aws:eks", "gcp:cloud_run", "k8s:pod", "gh:github"):
{icon_keys}
     Any other key is rejected.
     Leave 'icon' empty for flowchart steps and decisions (they render as boxes/diamonds).
     Labels then name the role, not the service: icon "aws:lambda" + label "media-convert"; icon "aws:s3" +
     label "S3 (video-inputs/)"; icon "aws:ec2" + label "App Server".
     * Set node kind accurately: 'service' for compute/networking services, 'datastore' for S3/RDS/DynamoDB,
       'actor' for users/clients, 'external' for third-party APIs.
   - Keep labels short (2-4 words); the layout wraps long labels.
   - Use node kinds accurately:
     * process: general computation or action
     * decision: branch point or evaluation
     * datastore: database, dataset, cache, S3, RDS, model weights
     * service: external or cloud service/daemon (e.g. EC2, Lambda, API Gateway)
     * actor: human user or client
     * external: third-party system
     * note: informative note (can be standalone)
   - Every node (except 'note') MUST be connected to at least one edge.
   - IDs must be unique strings (e.g. "igw", "pub_sub", "ec2_inst"). IDs "0" and "1" are reserved.
   - At most 20 nodes for optimal readability.
5. Edges (REQUIRED, MUST NOT BE EMPTY):
   - For flowchart and architecture, you MUST define DiagramEdge objects in 'edges'.
   - from and to must reference existing node IDs.
   - Short edge labels (1-3 words) describing data flow or protocol (e.g. "HTTPS", "0.0.0.0/0", "SQL", "S3 event").
     Leave the label empty when the arrow is self-explanatory.
   - Order edges along the main flow (the first edge's source is where the diagram starts on the left/top).
   - style "solid" = data path (requests, data moving); style "dashed" = control/automation (deploys, syncs, IAM,
     config, monitoring). A legend is added automatically when both appear.
6. Sequence diagrams (if type == "sequence"):
   - Define participants with IDs and labels.
   - Define ordered messages with from, to, and label. Set return=True for return messages.
7. Style preset:
   - Always "owner_dark" exactly (do NOT append or repeat characters).
"""


def icon_key_list() -> str:
    """Keys only, grouped by family ("aws: ec2, eks, ..."); styles are resolved in code (E10-S4)."""
    groups: dict[str, list[str]] = {}
    for key in sorted(ICONS):
        family, _, name = key.partition(":") if ":" in key else ("generic", "", key)
        groups.setdefault(family, []).append(name)
    order = ["aws", "gcp", "k8s", "gh", "generic"]
    lines = []
    for family in order:
        if family in groups:
            prefix = "no prefix" if family == "generic" else f"{family}:"
            lines.append(f"       {family} ({prefix}): {', '.join(groups[family])}")
    return "\n".join(lines)


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
    system = DIAGRAM_SPEC_SYSTEM.replace("{icon_keys}", icon_key_list())
    return [SystemMessage(content=system), HumanMessage(content=prompt)]
