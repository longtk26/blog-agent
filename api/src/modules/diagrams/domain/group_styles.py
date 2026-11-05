"""Group frame styles.

AWS boundaries use the aws4 group stencils. draw.io's index has no GCP boundary stencils (its GCP "zones" are filled
light-theme boxes), so GCP boundaries are plain containers in Google's colours (E10-S4). Kubernetes clusters and
namespaces get their own frames. One diagram uses one cloud's styles: `family` comes from its dominant icon family.
"""

from dataclasses import dataclass



@dataclass(frozen=True)
class GroupStyle:
    color: str
    text: str
    dashed: bool
    drawio: str                # draw.io style for the container


def _aws_group(gr_icon: str, color: str, dashed: bool = False) -> str:
    return (
        f"points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=1;"
        f"container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
        f"grIcon=mxgraph.aws4.{gr_icon};strokeColor={color};fillColor=none;verticalAlign=top;align=left;"
        f"spacingLeft=30;fontColor={color};dashed={1 if dashed else 0};"
    )


def _plain(color: str, text: str, dashed: bool) -> GroupStyle:
    return GroupStyle(
        color, text, dashed,
        f"rounded=1;arcSize=2;absoluteArcSize=1;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;"
        f"fillColor=none;strokeColor={color};fontColor={text};fontStyle=1;fontSize=12;verticalAlign=top;align=left;"
        f"spacingLeft=10;dashed={1 if dashed else 0};",
    )


def _k8s_group(text: str) -> GroupStyle | None:
    if "namespace" in text or text.startswith("ns ") or text.startswith("ns:"):
        return _plain("#326CE5", "#93C5FD", True)
    if "cluster" in text and ("k8s" in text or "kubernetes" in text or "eks" in text or "gke" in text or "cluster" == text.strip()):
        return _plain("#326CE5", "#93C5FD", False)
    return None


def _gcp_group(text: str) -> GroupStyle | None:
    if "google cloud" in text or text.strip() in ("gcp", "cloud") or text.startswith("gcp "):
        return _plain("#4285F4", "#8AB4F8", False)
    if "project" in text:
        return _plain("#9AA0A6", "#E8EAED", True)
    if "region" in text:
        return _plain("#4285F4", "#8AB4F8", True)
    if "zone" in text:
        return _plain("#FBBC04", "#FDE68A", True)
    if "vpc" in text or "network" in text:
        return _plain("#34A853", "#86EFAC", False)
    if "subnet" in text:
        return _plain("#34A853", "#86EFAC", True)
    return None


def group_style(label: str, family: str = "aws") -> GroupStyle:
    text = (label or "").lower()
    k8s = _k8s_group(text)
    if k8s:
        return k8s
    if family == "gcp":
        gcp = _gcp_group(text)
        if gcp:
            return gcp
        return _plain("#64748B", "#CBD5E1", False)
    if "aws cloud" in text or text.strip() in ("aws", "cloud"):
        return GroupStyle("#CBD5E1", "#E2E8F0", False, _aws_group("group_aws_cloud_alt", "#CBD5E1"))
    if "region" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", True, _aws_group("group_region", "#00A4A6", dashed=True))
    if "availability zone" in text or text.startswith("az ") or text == "az":
        return GroupStyle("#00A4A6", "#5EEAD4", True,
                          "fillColor=none;strokeColor=#00A4A6;dashed=1;verticalAlign=top;fontStyle=1;fontColor=#5EEAD4;"
                          "whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;")
    if "vpc" in text:
        return GroupStyle("#8C4FFF", "#C4B5FD", False, _aws_group("group_vpc2", "#8C4FFF"))
    if "public" in text and "subnet" in text:
        return GroupStyle("#7AA116", "#BEF264", False, _aws_group("group_security_group", "#7AA116"))
    if "private" in text and "subnet" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", False, _aws_group("group_security_group", "#00A4A6"))
    if "subnet" in text:
        return GroupStyle("#00A4A6", "#5EEAD4", False, _aws_group("group_security_group", "#00A4A6"))
    return GroupStyle(
        "#64748B", "#CBD5E1", False,
        "rounded=1;arcSize=3;whiteSpace=wrap;html=1;container=1;collapsible=0;recursiveResize=0;fillColor=none;"
        "strokeColor=#64748B;fontColor=#CBD5E1;fontStyle=1;fontSize=12;verticalAlign=top;align=left;spacingLeft=10;",
    )
