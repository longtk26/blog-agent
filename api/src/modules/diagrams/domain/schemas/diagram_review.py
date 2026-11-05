"""Structured output of the diagram visual review (E10-S7). Model output is untrusted: always validated here."""

from typing import Literal

from pydantic import BaseModel, Field

# The checklist the reviewer answers (note §2.4). Numbers are stable: evals and the UI refer to them.
CHECKLIST: dict[int, str] = {
    1: "Any text overlapping another text, icon or edge?",
    2: "Any edge passing through a box/icon it doesn't connect to?",
    3: "Any edge drawn along a container border, or two edges sharing one line?",
    4: "Any text cut off or overflowing its shape?",
    5: "Any edge label far from its edge, or ambiguous about which edge it belongs to?",
    6: "Any icon rendered blank or as a grey box?",
}


class ReviewIssue(BaseModel):
    check: int = Field(..., ge=1, le=6, description="Checklist item number (1-6)")
    severity: Literal["minor", "major"] = Field(
        ..., description="major = a reader would misread or not be able to read the diagram; minor = cosmetic"
    )
    description: str = Field(..., max_length=400, description="What is wrong and where, in one sentence")
    labels_involved: list[str] = Field(default_factory=list, max_length=8, description="Visible labels involved")


class DiagramReview(BaseModel):
    passed: bool = Field(..., description="True when there is no major issue")
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=20)

    @property
    def major(self) -> int:
        return sum(1 for i in self.issues if i.severity == "major")

    @property
    def minor(self) -> int:
        return sum(1 for i in self.issues if i.severity == "minor")


def review_score(major: int, minor: int) -> float:
    """E10-S8 diagram_visual_quality: 1 - (0.25 x major + 0.05 x minor), floored at 0."""
    return max(0.0, 1.0 - 0.25 * major - 0.05 * minor)
