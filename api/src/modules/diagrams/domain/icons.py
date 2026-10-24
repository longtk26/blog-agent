"""Icon catalogue shared by the draw.io generator and the SVG renderer.

Icons follow the AWS Architecture Icons convention used in the owner's diagrams (assets/samples/architecture.drawio):
a square tile in the service-category colour with a white glyph, and the label underneath. In draw.io the tile is the
official `mxgraph.aws4.resourceIcon` stencil; the SVG renderer draws a simplified glyph in the same colours.
"""

import re
from dataclasses import dataclass

# AWS category colours (draw.io aws4 palette)
COMPUTE = "#ED7100"
STORAGE = "#7AA116"
DATABASE = "#C925D1"
NETWORKING = "#8C4FFF"
INTEGRATION = "#E7157B"
ML = "#01A88D"
SECURITY = "#DD344C"
MANAGEMENT = "#E7157B"
MEDIA = "#ED7100"
GENERIC = "#475569"

# Glyphs are drawn in a 24x24 box with a white stroke (see svg_renderer.py).
_SERVER = '<rect x="5" y="4" width="14" height="16" rx="1.5"/><path d="M8 8h8M8 12h8M8 16h5"/>'
_CYLINDER = '<ellipse cx="12" cy="6" rx="7" ry="2.6"/><path d="M5 6v12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6V6"/><path d="M5 12c0 1.4 3.1 2.6 7 2.6s7-1.2 7-2.6"/>'
_BUCKET = '<path d="M4.5 6.5h15l-2 13h-11z"/><ellipse cx="12" cy="6.5" rx="7.5" ry="2.2"/>'
_LAMBDA = '<path d="M6 20l5-10M9 4h3l7 16"/>'
_GLOBE = '<circle cx="12" cy="12" r="8"/><ellipse cx="12" cy="12" rx="3.5" ry="8"/><path d="M4 12h16"/>'
_BALANCER = '<circle cx="12" cy="12" r="3"/><path d="M4 12h5M15 12l5-5M15 12l5 5M15 12h5"/>'
_GATEWAY = '<path d="M5 20V10a7 7 0 0 1 14 0v10"/><path d="M9 15h6M12 12v6"/>'
_NAT = '<path d="M4 9h13l-3-3M20 15H7l3 3"/>'
_BUS = '<rect x="3" y="9" width="18" height="6" rx="3"/><path d="M7 5v4M12 5v4M17 15v4M7 15v4"/>'
_QUEUE = '<rect x="3" y="8" width="5" height="8"/><rect x="9.5" y="8" width="5" height="8"/><rect x="16" y="8" width="5" height="8"/>'
_FANOUT = '<circle cx="6" cy="12" r="2.5"/><path d="M8.5 12h4M12.5 12l6-5M12.5 12h7M12.5 12l6 5"/>'
_API = '<path d="M8 5c-2 0-3 1-3 3v2l-2 2 2 2v2c0 2 1 3 3 3M16 5c2 0 3 1 3 3v2l2 2-2 2v2c0 2-1 3-3 3"/>'
_CONTAINER = '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>'
_USER = '<circle cx="12" cy="8" r="4"/><path d="M4.5 20c0-4.2 3.4-6.5 7.5-6.5s7.5 2.3 7.5 6.5"/>'
_SHIELD = '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z"/><path d="M9 12l2 2 4-4"/>'
_DNS = '<circle cx="12" cy="12" r="8"/><path d="M8.5 14.5l2-5 2 3 2-3"/>'
_CHART = '<path d="M4 4v16h16"/><path d="M7 15l4-4 3 3 5-6"/>'
_BRAIN = '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 3 3h0V4zM15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-3 3V4z"/>'
_WAVE = '<path d="M3 12h2M7 8v8M11 5v14M15 8v8M19 10v4M21 12h0"/>'
_FILM = '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M8 5v14M16 5v14M4 9.5h4M4 14.5h4M16 9.5h4M16 14.5h4"/>'
_STEPS = '<rect x="3" y="4" width="7" height="5" rx="1"/><rect x="14" y="10" width="7" height="5" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/><path d="M10 6.5h3.5V10M14 12.5h-3.5v3.5"/>'
_STREAM = '<path d="M3 8c3-3 6 3 9 0s6 3 9 0M3 13c3-3 6 3 9 0s6 3 9 0M3 18c3-3 6 3 9 0s6 3 9 0"/>'
_BOLT = '<path d="M13 3L5 13h6l-1 8 8-10h-6z"/>'
_KEY = '<circle cx="8" cy="12" r="4"/><path d="M12 12h9M18 12v3M21 12v2"/>'
_LAPTOP = '<rect x="5" y="5" width="14" height="10" rx="1"/><path d="M3 19h18"/>'
_PHONE = '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 17.5h2"/>'
_DOC = '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>'
_SPARK = '<path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3"/>'
_CODE = '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>'
_CLOUD = '<path d="M7 18a4 4 0 0 1-.5-8 5.5 5.5 0 0 1 10.6-1.5A4.5 4.5 0 0 1 17 18z"/>'


@dataclass(frozen=True)
class IconSpec:
    key: str
    color: str
    glyph: str
    drawio_shape: str       # style fragment selecting the draw.io stencil
    aliases: tuple[str, ...] = ()


def _aws(key: str, res_icon: str, color: str, glyph: str, *aliases: str) -> IconSpec:
    return IconSpec(
        key=f"aws:{key}",
        color=color,
        glyph=glyph,
        drawio_shape=f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res_icon};",
        aliases=aliases,
    )


def _generic(key: str, shape: str, glyph: str, *aliases: str) -> IconSpec:
    # Same tile look as the service icons, with a neutral colour.
    return IconSpec(
        key=key, color=GENERIC, glyph=glyph,
        drawio_shape=f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{shape};", aliases=aliases,
    )


ICONS: dict[str, IconSpec] = {
    icon.key: icon
    for icon in (
        _aws("ec2", "ec2", COMPUTE, _SERVER, "ec2", "instance", "virtual machine"),
        _aws("lambda", "lambda", COMPUTE, _LAMBDA, "lambda"),
        _aws("ecs", "ecs", COMPUTE, _CONTAINER, "ecs", "fargate"),
        _aws("eks", "eks", COMPUTE, _CONTAINER, "eks"),
        _aws("s3", "s3", STORAGE, _BUCKET, "s3", "bucket"),
        _aws("rds", "rds", DATABASE, _CYLINDER, "rds", "aurora"),
        _aws("dynamodb", "dynamodb", DATABASE, _CYLINDER, "dynamodb", "dynamo"),
        _aws("elasticache", "elasticache", DATABASE, _BOLT, "elasticache"),
        _aws("cloudfront", "cloudfront", NETWORKING, _GLOBE, "cloudfront"),
        _aws("alb", "application_load_balancer", NETWORKING, _BALANCER, "alb", "elb", "load balancer"),
        _aws("igw", "internet_gateway", NETWORKING, _GATEWAY, "igw", "internet gateway"),
        _aws("nat", "nat_gateway", NETWORKING, _NAT, "nat gateway", "nat"),
        _aws("api_gateway", "api_gateway", NETWORKING, _API, "api gateway", "apigw"),
        _aws("route53", "route_53", NETWORKING, _DNS, "route 53", "route53"),
        _aws("eventbridge", "eventbridge", INTEGRATION, _BUS, "eventbridge", "event bridge"),
        _aws("sqs", "sqs", INTEGRATION, _QUEUE, "sqs"),
        _aws("sns", "sns", INTEGRATION, _FANOUT, "sns"),
        _aws("step_functions", "step_functions", INTEGRATION, _STEPS, "step functions"),
        _aws("kinesis", "kinesis", INTEGRATION, _STREAM, "kinesis"),
        _aws("cognito", "cognito", SECURITY, _SHIELD, "cognito"),
        _aws("secrets_manager", "secrets_manager", SECURITY, _KEY, "secrets manager"),
        _aws("cloudwatch", "cloudwatch", MANAGEMENT, _CHART, "cloudwatch"),
        _aws("sagemaker", "sagemaker", ML, _BRAIN, "sagemaker"),
        _aws("bedrock", "bedrock", ML, _SPARK, "bedrock"),
        _aws("transcribe", "transcribe", ML, _WAVE, "transcribe"),
        _aws("mediaconvert", "elemental_mediaconvert", MEDIA, _FILM, "mediaconvert", "media convert"),
        _generic("user", "user", _USER, "user", "users", "customer", "end user"),
        _generic("client", "client", _LAPTOP, "client", "browser", "web app", "frontend"),
        _generic("mobile", "mobile_client", _PHONE, "mobile"),
        _generic("server", "traditional_server", _SERVER, "server"),
        _generic("database", "generic_database", _CYLINDER, "database"),
        _generic("document", "document", _DOC, "document", "file"),
        _generic("internet", "internet_alt1", _CLOUD, "internet"),
        IconSpec("llm", ML, _SPARK, "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.bedrock;", ("llm", "model")),
        IconSpec("code", GENERIC, _CODE, "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.corretto;", ("code", "sdk")),
    )
}

_AWS_TAG = re.compile(r"^\s*\[(?:aws\s+)?([^\]]+)\]\s*", re.IGNORECASE)


def _match_alias(text: str, keys: list[str]) -> IconSpec | None:
    for key in keys:
        icon = ICONS[key]
        for alias in icon.aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                return icon
    return None


def resolve_icon(icon: str | None, label: str, kind: str, diagram_type: str) -> tuple[IconSpec | None, str]:
    """(icon, display label). Explicit keys win; "[AWS EC2] Web Server" tags are understood and stripped.

    Keyword inference only runs for architecture diagrams, so flowchart steps keep their box shapes.
    """
    if icon:
        key = icon.strip().lower()
        found = ICONS.get(key) or ICONS.get(f"aws:{key}")
        if found:
            return found, _AWS_TAG.sub("", label).strip() or label
    tag = _AWS_TAG.match(label)
    if tag:
        found = _match_alias(tag.group(1).lower(), [k for k in ICONS if k.startswith("aws:")])
        rest = label[tag.end():].strip()
        if found:
            return found, rest or tag.group(1).strip()
    if kind == "actor":
        return ICONS["user"], label
    if diagram_type == "architecture" and kind in ("service", "datastore", "external"):
        found = _match_alias(label.lower(), list(ICONS))
        if found:
            return found, label
    return None, label
