from src.modules.publishing.domain.svg_sanitizer import sanitize_svg


def test_sanitize_svg_removes_scripts_and_event_handlers():
    dirty_svg = """
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" onload="alert(1)">
        <script>alert("hacked");</script>
        <circle cx="50" cy="50" r="40" onclick="evil()" fill="red" />
        <a href="javascript:void(0)"><text x="10" y="20">Click me</text></a>
        <foreignObject width="100" height="100">
            <body xmlns="http://www.w3.org/1999/xhtml">
                <input type="text"/>
            </body>
        </foreignObject>
    </svg>
    """
    clean_bytes = sanitize_svg(dirty_svg)
    clean_str = clean_bytes.decode("utf-8")

    assert "<script" not in clean_str.lower()
    assert "alert" not in clean_str.lower()
    assert "onload=" not in clean_str.lower()
    assert "onclick=" not in clean_str.lower()
    assert "javascript:" not in clean_str.lower()
    assert "foreignobject" not in clean_str.lower()
    assert '<circle cx="50" cy="50" r="40"' in clean_str
    assert 'fill="red"' in clean_str


def test_sanitize_svg_preserves_valid_svg_and_styles():
    valid_svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
        <style>
            .cls-1 { fill: #ff0000; }
        </style>
        <rect class="cls-1" width="100" height="100" />
    </svg>
    """
    clean_bytes = sanitize_svg(valid_svg.encode("utf-8"))
    clean_str = clean_bytes.decode("utf-8")

    assert ".cls-1 { fill: #ff0000; }" in clean_str
    assert '<rect class="cls-1" width="100" height="100"' in clean_str
