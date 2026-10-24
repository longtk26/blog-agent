"""Pydantic schemas for editable diagrams (E7-S1)."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

DiagramType = Literal["flowchart", "architecture", "sequence"]
DiagramDirection = Literal["LR", "TB"]
NodeKind = Literal["process", "decision", "datastore", "service", "actor", "external", "note"]
EdgeStyle = Literal["solid", "dashed"]
EdgeArrow = Literal["one", "both", "none"]


class DiagramNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    kind: NodeKind = "process"
    group: str | None = None


class DiagramGroup(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    parent: str | None = None


class DiagramEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    label: str | None = None
    style: EdgeStyle = "solid"
    arrow: EdgeArrow = "one"


class DiagramParticipant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    label: str
    actor: bool = False


class DiagramMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(..., alias="from")
    to_node: str = Field(..., alias="to")
    label: str = ""
    return_msg: bool = Field(default=False, alias="return")
    async_msg: bool = Field(default=False, alias="async")
    note: str | None = None
    over: str | None = None


class DiagramSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: DiagramType = "flowchart"
    title: str = "Technical Diagram"
    direction: DiagramDirection = "LR"
    nodes: list[DiagramNode] = Field(default_factory=list)
    groups: list[DiagramGroup] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)
    participants: list[DiagramParticipant] = Field(default_factory=list)
    messages: list[DiagramMessage] = Field(default_factory=list)
    style_preset: str = "owner_dark"
