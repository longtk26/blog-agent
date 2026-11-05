"""Diagram specs shared by the layout tests (E10-S5/S6). Shapes follow real diagrams the owner draws."""

from src.modules.diagrams.domain.schemas.diagram_spec import (
    DiagramEdge as E,
    DiagramGroup as G,
    DiagramNode as N,
    DiagramSpec,
)


def edge(a: str, b: str, label: str | None = None, **kw) -> E:
    return E(**{"from": a, "to": b, "label": label, **kw})


# Memory Up DevOps style: EKS in private subnets, regional services, GitOps from GitHub, external DB and ACME.
EKS_GITOPS = DiagramSpec(
    type="architecture", title="Memory Up on AWS EKS", direction="LR",
    groups=[
        G(id="cloud", label="AWS Cloud"),
        G(id="region", label="Region ap-southeast-1", parent="cloud"),
        G(id="vpc", label="VPC 10.0.0.0/16", parent="region"),
        G(id="pub", label="Public Subnet", parent="vpc"),
        G(id="priv", label="Private Subnet", parent="vpc"),
        G(id="cluster", label="EKS cluster", parent="priv"),
        G(id="ns_app", label="Namespace: memory-up", parent="cluster"),
        G(id="ns_argo", label="Namespace: argocd", parent="cluster"),
    ],
    nodes=[
        N(id="user", label="Users", kind="actor", icon="users"),
        N(id="igw", label="Internet Gateway", kind="service", icon="aws:igw", group="vpc"),
        N(id="alb", label="ALB", kind="service", icon="aws:alb", group="pub"),
        N(id="nat", label="NAT Gateway", kind="service", icon="aws:nat", group="pub"),
        N(id="ing", label="Ingress", kind="service", icon="k8s:ing", group="ns_app"),
        N(id="api", label="API pods", kind="service", icon="k8s:pod", group="ns_app"),
        N(id="worker", label="Worker pods", kind="service", icon="k8s:pod", group="ns_app"),
        N(id="argocd", label="Argo CD", kind="service", icon="k8s:deploy", group="ns_argo"),
        N(id="ecr", label="ECR", kind="service", icon="aws:ecr", group="region"),
        N(id="s3", label="S3 media", kind="datastore", icon="aws:s3", group="region"),
        N(id="ssm", label="Parameter Store", kind="service", icon="aws:parameter_store", group="region"),
        N(id="github", label="GitHub", kind="external", icon="gh:github"),
        N(id="db", label="Managed Postgres", kind="external", icon="database"),
        N(id="acme", label="ACME (Let's Encrypt)", kind="external", icon="internet"),
    ],
    edges=[
        edge("user", "igw", "HTTPS"), edge("igw", "alb"), edge("alb", "ing"), edge("ing", "api"),
        edge("api", "worker", "jobs"), edge("api", "s3", "uploads"), edge("api", "nat", "egress"),
        edge("nat", "db", "5432"), edge("nat", "acme", "HTTP-01", style="dashed"),
        edge("github", "argocd", "GitOps sync", style="dashed"), edge("argocd", "api", "deploy", style="dashed"),
        edge("api", "ecr", "pull image", style="dashed"), edge("api", "ssm", "config", style="dashed"),
    ],
)

GCP_SERVERLESS = DiagramSpec(
    type="architecture", title="Media pipeline on Google Cloud", direction="LR",
    groups=[
        G(id="gcp", label="Google Cloud"),
        G(id="proj", label="Project media-prod", parent="gcp"),
        G(id="vpc", label="VPC network", parent="proj"),
    ],
    nodes=[
        N(id="user", label="Users", kind="actor", icon="user"),
        N(id="lb", label="Load Balancer", kind="service", icon="gcp:load_balancing", group="proj"),
        N(id="run", label="API (Cloud Run)", kind="service", icon="gcp:cloud_run", group="proj"),
        N(id="gke", label="Workers (GKE)", kind="service", icon="gcp:gke", group="vpc"),
        N(id="sql", label="Cloud SQL", kind="datastore", icon="gcp:cloud_sql", group="vpc"),
        N(id="gcs", label="Cloud Storage", kind="datastore", icon="gcp:cloud_storage", group="proj"),
        N(id="ps", label="Pub/Sub", kind="service", icon="gcp:pubsub", group="proj"),
    ],
    edges=[
        edge("user", "lb", "HTTPS"), edge("lb", "run"), edge("run", "gcs", "upload"), edge("run", "ps", "job"),
        edge("ps", "gke", "subscribe"), edge("gke", "sql", "SQL"), edge("gke", "gcs", "read/write"),
    ],
)

WEBHOOK_SEQUENCE = DiagramSpec(
    type="sequence", title="Verified webhook delivery",
    participants=[
        {"id": "prov", "label": "Provider"}, {"id": "api", "label": "Webhook endpoint"},
        {"id": "q", "label": "Queue"}, {"id": "w", "label": "Worker"},
    ],
    messages=[
        {"from": "prov", "to": "api", "label": "POST event + HMAC signature"},
        {"from": "api", "to": "api", "label": "verify signature + timestamp"},
        {"from": "api", "to": "q", "label": "enqueue (idempotency key)"},
        {"from": "api", "to": "prov", "label": "202 Accepted", "return": True},
        {"from": "q", "to": "w", "label": "deliver", "async": True},
        {"from": "w", "to": "w", "label": "skip if key already processed"},
    ],
)
