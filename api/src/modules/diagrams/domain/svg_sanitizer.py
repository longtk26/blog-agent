"""SVG sanitization and validation functions (E7-S4)."""

import re

MAX_SVG_BYTES = 2 * 1024 * 1024  # 2 MB ceiling


def sanitize_svg_content(svg_str: str) -> str:
    """Sanitize SVG content by stripping dangerous elements, attributes and URIs.
    
    Raises ValueError if SVG exceeds 2MB or contains unrecoverable safety issues.
    """
    if len(svg_str.encode("utf-8")) > MAX_SVG_BYTES:
        raise ValueError(f"SVG payload exceeds 2 MB limit ({len(svg_str)} bytes)")

    # 1. Remove <script> tags and everything inside them
    cleaned = re.sub(r"(?is)<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", svg_str)
    cleaned = re.sub(r"(?is)<\s*script[^>]*/>", "", cleaned)

    # 2. Remove event handlers: onclick, onload, onerror, onmouseover, etc.
    cleaned = re.sub(r'(?i)\s+on[a-z]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', "", cleaned)

    # 3. Disallow javascript: pseudo-protocols in href or xlink:href
    cleaned = re.sub(r'(?i)(href|xlink:href)\s*=\s*(?:"javascript:[^"]*"|\'javascript:[^\']*\'|javascript:[^\s>]+)', "", cleaned)

    # 4. Strip external href references (keep only local fragment identifiers #...)
    # Replace href="http..." or href="//..." with empty or '#'
    def _strip_external_href(match):
        attr_name = match.group(1)
        url = match.group(2)
        if url.startswith("#") or url.startswith("data:image/"):
            return f'{attr_name}="{url}"'
        return f'{attr_name}="#"'

    cleaned = re.sub(r'(?i)(href|xlink:href)\s*=\s*["\']([^"\']+)["\']', _strip_external_href, cleaned)

    return cleaned
