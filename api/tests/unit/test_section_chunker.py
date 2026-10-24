from src.modules.styles.domain.section_chunker import chunk_markdown_sections


def test_chunk_markdown_sections_basic():
    md = """# My Post

Introduction paragraph.

## 1. Background
Background details.

```python
## This is a comment inside code, not a heading!
def test():
    pass
```

### 1.1 Deep Dive
More technical details here.

## 2. Conclusion
Wrap up here.
"""

    chunks = chunk_markdown_sections(md, title="My Post")
    assert len(chunks) == 5

    # 1. Outline chunk
    assert chunks[0].chunk_type == "outline"
    assert "My Post" in chunks[0].content
    assert "- 1. Background" in chunks[0].content

    # 2. Intro section
    assert chunks[1].chunk_type == "section"
    assert "Introduction paragraph" in chunks[1].content

    # 3. Background section with code block intact
    assert chunks[2].heading_path == "1. Background"
    assert "## This is a comment inside code" in chunks[2].content
    assert "def test():" in chunks[2].content

    # 4. Nested H3 section
    assert chunks[3].heading_path == "1. Background > 1.1 Deep Dive"
    assert "More technical details here" in chunks[3].content

    # 5. Conclusion section
    assert chunks[4].heading_path == "2. Conclusion"
    assert "Wrap up here" in chunks[4].content
