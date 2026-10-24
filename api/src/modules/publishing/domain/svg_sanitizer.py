import re


_SCRIPT_PATTERN = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_FOREIGN_OBJECT_PATTERN = re.compile(r"<foreignObject[\s\S]*?</foreignObject>", re.IGNORECASE)
_EVENT_HANDLER_PATTERN = re.compile(r"\bon[a-zA-Z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
_JS_HREF_PATTERN = re.compile(r"(?:href|xlink:href)\s*=\s*(?:\"[^\"]*javascript:[^\"]*\"|'[^']*javascript:[^']*')", re.IGNORECASE)
_DOCTYPE_PATTERN = re.compile(r"<!DOCTYPE[\s\S]*?>", re.IGNORECASE)
_ENTITY_PATTERN = re.compile(r"<!ENTITY[\s\S]*?>", re.IGNORECASE)
_EMBED_PATTERN = re.compile(r"<(?:iframe|object|embed|applet)[\s\S]*?(?:/>|</(?:iframe|object|embed|applet)>)", re.IGNORECASE)


def sanitize_svg(content: str | bytes) -> bytes:
    """Strip script tags, event handlers, javascript URIs, and dangerous elements from SVG content."""
    is_bytes = isinstance(content, bytes)
    text = content.decode("utf-8", errors="replace") if is_bytes else content

    text = _DOCTYPE_PATTERN.sub("", text)
    text = _ENTITY_PATTERN.sub("", text)
    text = _SCRIPT_PATTERN.sub("", text)
    text = _FOREIGN_OBJECT_PATTERN.sub("", text)
    text = _EMBED_PATTERN.sub("", text)
    text = _EVENT_HANDLER_PATTERN.sub("", text)
    text = _JS_HREF_PATTERN.sub("", text)

    return text.strip().encode("utf-8")
