from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid", "_hsenc", "_hsmi"}
DEFAULT_PORTS = {"http": 80, "https": 443}


def is_http_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def canonicalize_url(url: str) -> str:
    """Stable key for de-duplication: lowercase scheme/host, no fragment, no tracking params, sorted query."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if port in (None, DEFAULT_PORTS.get(scheme)) else f"{host}:{port}"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    )
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def domain_matches(host: str, domains: list[str]) -> bool:
    host = host.lower().removeprefix("www.")
    for domain in domains:
        domain = domain.lower().strip().removeprefix("www.")
        if domain and (host == domain or host.endswith(f".{domain}")):
            return True
    return False
