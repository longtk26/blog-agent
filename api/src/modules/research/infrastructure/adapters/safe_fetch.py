import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from src.modules.research.ports.output import ExtractionError

ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (compatible; blog-agent/0.1; personal research assistant)"


@dataclass
class FetchedPage:
    url: str
    final_url: str
    content_type: str
    body: bytes


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def resolve_host(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def ensure_public_url(url: str, allow_private: bool = False) -> None:
    """SSRF guard: only http(s) to hosts that resolve exclusively to public IPs."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ExtractionError("Only http(s) URLs are allowed")
    if allow_private:
        return
    try:
        addresses = await resolve_host(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except OSError as exc:
        raise ExtractionError(f"DNS resolution failed for {parts.hostname}") from exc
    if not addresses or not all(_is_public_ip(address) for address in addresses):
        raise ExtractionError(f"Blocked non-public host: {parts.hostname}")


async def safe_fetch(
    client: httpx.AsyncClient, url: str, *, max_bytes: int, allow_private: bool = False
) -> FetchedPage:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        await ensure_public_url(current, allow_private)
        async with client.stream("GET", current, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"}) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ExtractionError("Redirect without location")
                current = urljoin(current, location)
                continue
            if response.status_code >= 400:
                raise ExtractionError(f"HTTP {response.status_code}")

            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith(ALLOWED_CONTENT_TYPES):
                raise ExtractionError(f"Unsupported content type: {content_type}")

            declared = int(response.headers.get("content-length") or 0)
            if declared > max_bytes:
                raise ExtractionError(f"Page too large ({declared} bytes)")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ExtractionError(f"Page larger than {max_bytes} bytes")
            return FetchedPage(url=url, final_url=str(response.url), content_type=content_type, body=bytes(body))
    raise ExtractionError("Too many redirects")
