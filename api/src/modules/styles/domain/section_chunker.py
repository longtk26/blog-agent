from dataclasses import dataclass
import re


@dataclass
class MarkdownChunk:
    chunk_index: int
    heading_path: str
    content: str
    chunk_type: str  # "section" | "outline"


_FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


def chunk_markdown_sections(markdown: str, title: str = "") -> list[MarkdownChunk]:
    """Splits markdown into section chunks by H2/H3 headings, preserving code blocks.

    Also generates an 'outline' chunk containing the heading tree and structure.
    """
    lines = markdown.split("\n")
    chunks: list[MarkdownChunk] = []

    # 1. First extract the full outline tree
    heading_tree: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_PATTERN.match(line)
        if m:
            level = len(m.group(1))
            h_text = m.group(2).strip()
            indent = "  " * (level - 1)
            heading_tree.append(f"{indent}- {h_text}")

    outline_text = f"Title: {title}\nHeading Outline:\n" + "\n".join(heading_tree)
    chunks.append(
        MarkdownChunk(
            chunk_index=0,
            heading_path="Outline",
            content=outline_text,
            chunk_type="outline",
        )
    )

    # 2. Section chunking
    current_h2 = ""
    current_h3 = ""
    current_lines: list[str] = []
    in_fence = False
    chunk_idx = 1

    def flush_section():
        nonlocal chunk_idx, current_lines
        content = "\n".join(current_lines).strip()
        if content:
            path_parts = [p for p in (current_h2, current_h3) if p]
            heading_path = " > ".join(path_parts) if path_parts else (title or "Introduction")
            chunks.append(
                MarkdownChunk(
                    chunk_index=chunk_idx,
                    heading_path=heading_path,
                    content=content,
                    chunk_type="section",
                )
            )
            chunk_idx += 1
        current_lines = []

    for line in lines:
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence
            current_lines.append(line)
            continue

        if not in_fence:
            m = _HEADING_PATTERN.match(line)
            if m:
                level = len(m.group(1))
                h_text = m.group(2).strip()

                if level == 2:
                    flush_section()
                    current_h2 = h_text
                    current_h3 = ""
                    current_lines.append(line)
                    continue
                elif level == 3:
                    flush_section()
                    current_h3 = h_text
                    current_lines.append(line)
                    continue

        current_lines.append(line)

    flush_section()
    return chunks
