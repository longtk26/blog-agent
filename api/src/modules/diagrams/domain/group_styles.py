"""Group frame styles: AWS boundaries follow the AWS Architecture Icons group conventions, others stay neutral."""

from dataclasses import dataclass

_CLOUD = '<path d="M7 18a4 4 0 0 1-.5-8 5.5 5.5 0 0 1 10.6-1.5A4.5 4.5 0 0 1 17 18z"/>'
_VPC = '<path d="M7 17a3.5 3.5 0 0 1-.5-7 5 5 0 0 1 9.6-1.3A4 4 0 0 1 17 17z"/><path d="M10 13h4"/>'
_LOCK = '<rect x="6" y="11" width="12" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 6 0v3"/>'
_UNLOCK = '<rect x="6" y="11" width="12" height="9" rx="1.5"/><path d="M9 11V8a3 3 0 0 1 6 0"/>'
_PIN = '<path d="M12 21s-6-6-6-11a6 6 0 0 1 12 0c0 5-6 11-6 11z"/><circle cx="12" cy="10" r="2"/>'


@dataclass(frozen=True)
class GroupStyle:
    color: str
    text: str
    dashed: bool
    badge: str | None          # small glyph in the top-left corner (SVG)
    drawio: str                # draw.io style for the container


def _aws_group(gr_icon: str, color: str, dashed: bool = False) -> str:
    return (
        f"points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=1;"
        f"container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
        f"grIcon=mxgraph.aws4.{gr_icon};strokeColor={color};fillColor=none;verticalAlign=top;align=left;"
        f"spacingLeft=30;fontColor={color};dashed={1 if dashed else 0};"
    )


def group_style(label: str) -> GroupStyle:
    text = (label or "").lower()
    if "aws cloud" in text or text.strip() in ("aws", "cloud"):
        return GroupStyle("#CBD5E1", "#E2E8F0", False, _CLOUD, _aws_group("group_aws_cloud_alt", "#CBD5E1"))
    if "region" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", True, _PIN, _aws_group("group_region", "#00A4A6", dashed=True))
    if "availability zone" in text or text.startswith("az ") or text == "az":
        return GroupStyle("#00A4A6", "#5EEAD4", True, None,
                          "fillColor=none;strokeColor=#00A4A6;dashed=1;verticalAlign=top;fontStyle=1;fontColor=#5EEAD4;"
                          "whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;")
    if "vpc" in text:
        return GroupStyle("#8C4FFF", "#C4B5FD", False, _VPC, _aws_group("group_vpc2", "#8C4FFF"))
    if "public" in text and "subnet" in text:
        return GroupStyle("#7AA116", "#BEF264", False, _UNLOCK, _aws_group("group_security_group", "#7AA116"))
    if "private" in text and "subnet" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", False, _LOCK, _aws_group("group_security_group", "#00A4A6"))
    if "subnet" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", False, _LOCK, _aws_group("group_security_group", "#00A4A6"))
    return GroupStyle(
        "#64748B", "#CBD5E1", False, None,
        "rounded=1;arcSize=3;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;fillColor=none;"
        "strokeColor=#64748B;fontColor=#CBD5E1;fontStyle=1;fontSize=12;verticalAlign=top;align=left;spacingLeft=10;",
    )
