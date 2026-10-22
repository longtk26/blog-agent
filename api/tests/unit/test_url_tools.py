import pytest

from src.modules.research.infrastructure.adapters.url_tools import canonicalize_url, domain_matches, is_http_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://Example.COM/Path/?utm_source=x&b=2&a=1#section", "https://example.com/Path?a=1&b=2"),
        ("https://example.com:443/", "https://example.com/"),
        ("http://example.com:8080/x/", "http://example.com:8080/x"),
        ("https://example.com/a?fbclid=123&gclid=4", "https://example.com/a"),
        ("https://arxiv.org/abs/2106.09685?utm_source=x", "https://arxiv.org/abs/2106.09685"),
    ],
)
def test_canonicalize(raw, expected):
    assert canonicalize_url(raw) == expected


def test_domain_matching_covers_subdomains_only():
    assert domain_matches("www.pinterest.com", ["pinterest.com"])
    assert domain_matches("in.pinterest.com", ["pinterest.com"])
    assert not domain_matches("notpinterest.com", ["pinterest.com"])


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "ftp://x.org/a", "https://", "not a url"])
def test_non_http_urls_rejected(url):
    assert not is_http_url(url)
