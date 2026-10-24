from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid


@dataclass
class WritingSampleEntity:
    id: uuid.UUID
    origin: str  # "sanity" | "local"
    remote_id: str
    title: str
    tags: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    approved_as_style_example: bool = True
    content: str = ""
    content_hash: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class SampleChunkEntity:
    id: uuid.UUID
    sample_id: uuid.UUID
    chunk_index: int
    heading_path: str
    content: str
    chunk_type: str = "section"  # "section" | "outline"
    embedding: list[float] | None = None
    created_at: datetime | None = None


@dataclass
class StyleProfileData:
    tone: str = ""
    voice: str = ""
    structure_patterns: dict[str, str] = field(default_factory=dict)
    heading_conventions: str = ""
    intro_pattern: str = ""
    explanation_devices: list[str] = field(default_factory=list)
    code_example_style: str = ""
    diagram_usage: str = ""
    typical_length: dict[str, str] = field(default_factory=dict)
    do: list[str] = field(default_factory=list)
    dont: list[str] = field(default_factory=list)
    signature_phrases: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Style Profile",
            "",
            f"**Tone:** {self.tone}",
            f"**Voice:** {self.voice}",
            "",
            "## Structure Patterns",
        ]
        for fmt, pattern in self.structure_patterns.items():
            lines.append(f"- **{fmt}:** {pattern}")
        lines.extend([
            "",
            f"**Heading Conventions:** {self.heading_conventions}",
            f"**Intro Pattern:** {self.intro_pattern}",
            "",
            "## Explanation Devices",
        ])
        for dev in self.explanation_devices:
            lines.append(f"- {dev}")
        lines.extend([
            "",
            f"**Code Example Style:** {self.code_example_style}",
            f"**Diagram Usage:** {self.diagram_usage}",
            "",
            "## Typical Lengths",
        ])
        for fmt, length in self.typical_length.items():
            lines.append(f"- **{fmt}:** {length}")
        lines.extend(["", "## Guidelines (Do)"])
        for d in self.do:
            lines.append(f"- [x] {d}")
        lines.extend(["", "## Anti-Patterns (Don't)"])
        for d in self.dont:
            lines.append(f"- [ ] {d}")
        if self.signature_phrases:
            lines.extend(["", "## Signature Phrases"])
            for phrase in self.signature_phrases:
                lines.append(f"- \"{phrase}\"")
        return "\n".join(lines)


@dataclass
class StyleProfileEntity:
    id: uuid.UUID
    version: int
    is_active: bool
    name: str = "Default Profile"
    profile_data: dict[str, Any] = field(default_factory=dict)
    markdown_content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OwnerNoteEntity:
    id: uuid.UUID
    title: str
    content: str
    citable_url: str | None = None
    quality_score: float = 1.0
    created_at: datetime | None = None
    updated_at: datetime | None = None
