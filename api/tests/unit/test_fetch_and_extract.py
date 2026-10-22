import httpx
import pytest
import respx

from src.modules.research.infrastructure.adapters import safe_fetch as safe_fetch_module
from src.modules.research.infrastructure.adapters.http_extractor import HttpPageExtractor
from src.modules.research.infrastructure.adapters.safe_fetch import ensure_public_url
from src.modules.research.infrastructure.adapters.tavily import TavilyPageExtractor, TavilySearchProvider
from src.modules.research.ports.output import ExtractionError, SearchError

ARTICLE_HTML = """<html><head><title>LoRA explained</title>
<link rel="canonical" href="https://docs.example.org/lora">
<meta property="og:site_name" content="Example Docs"></head>
<body><nav>menu menu</nav><article><h1>LoRA explained</h1>
<p>LoRA freezes the pretrained weights and trains low-rank adapter matrices instead of the full model.</p>
<p>This reduces the number of trainable parameters dramatically, which saves GPU memory during fine-tuning.</p>
<p>Adapters can be merged back into the base weights after training, so inference has no extra latency.</p>
</article></body></html>"""


@pytest.fixture
def fake_dns(monkeypatch):
    table = {"docs.example.org": ["93.184.216.34"], "evil.example.org": ["127.0.0.1"], "meta.example.org": ["169.254.169.254"]}

    async def resolve(host, port):
        return table.get(host, ["93.184.216.35"])

    monkeypatch.setattr(safe_fetch_module, "resolve_host", resolve)
    return table


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/admin", "http://10.0.0.5/", "http://[::1]/", "http://169.254.169.254/latest/meta-data", "ftp://x.org/"],
)
async def test_private_and_non_http_targets_are_blocked(url):
    with pytest.raises(ExtractionError):
        await ensure_public_url(url)


async def test_private_dns_answers_are_blocked(fake_dns):
    with pytest.raises(ExtractionError, match="non-public"):
        await ensure_public_url("https://evil.example.org/x")
    await ensure_public_url("https://docs.example.org/x")


@respx.mock
async def test_http_extractor_extracts_text_and_metadata(fake_dns):
    respx.get("https://docs.example.org/lora").mock(
        return_value=httpx.Response(200, html=ARTICLE_HTML)
    )
    page = await HttpPageExtractor(5, 1_000_000).extract("https://docs.example.org/lora")
    assert "low-rank adapter matrices" in page.text
    assert "menu menu" not in page.text
    assert page.title == "LoRA explained"
    assert page.canonical_url == "https://docs.example.org/lora"


@respx.mock
async def test_redirect_to_private_host_is_blocked(fake_dns):
    respx.get("https://docs.example.org/go").mock(
        return_value=httpx.Response(302, headers={"location": "http://meta.example.org/latest/meta-data"})
    )
    with pytest.raises(ExtractionError, match="non-public"):
        await HttpPageExtractor(5, 1_000_000).extract("https://docs.example.org/go")


@respx.mock
async def test_unsupported_and_oversized_pages_are_rejected(fake_dns):
    respx.get("https://docs.example.org/paper.pdf").mock(
        return_value=httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
    )
    respx.get("https://docs.example.org/huge").mock(return_value=httpx.Response(200, html="x" * 5000))
    extractor = HttpPageExtractor(5, max_bytes=1000)
    with pytest.raises(ExtractionError, match="Unsupported content type"):
        await extractor.extract("https://docs.example.org/paper.pdf")
    with pytest.raises(ExtractionError, match="larger than|too large"):
        await extractor.extract("https://docs.example.org/huge")


@respx.mock
async def test_tavily_search_and_extract():
    search_route = respx.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(
            200, json={"results": [{"url": "https://arxiv.org/abs/2106.09685", "title": "LoRA", "content": "We propose", "score": 0.9}]}
        )
    )
    respx.post("https://api.tavily.com/extract").mock(
        return_value=httpx.Response(200, json={"results": [{"url": "https://arxiv.org/abs/2106.09685", "raw_content": "LoRA text"}]})
    )
    results = await TavilySearchProvider("tvly-secret", 5).search("lora", max_results=3, exclude_domains=["pinterest.com"])
    assert results[0].title == "LoRA" and results[0].score == 0.9
    sent = search_route.calls[0].request
    assert sent.headers["authorization"] == "Bearer tvly-secret"
    assert b'"exclude_domains":["pinterest.com"]' in sent.content.replace(b" ", b"")

    page = await TavilyPageExtractor("tvly-secret", 5, allow_private=True).extract("https://arxiv.org/abs/2106.09685")
    assert page.text == "LoRA text"


@respx.mock
async def test_tavily_errors_are_wrapped():
    respx.post("https://api.tavily.com/search").mock(return_value=httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(SearchError):
        await TavilySearchProvider("bad", 5).search("lora")
    respx.post("https://api.tavily.com/extract").mock(
        return_value=httpx.Response(200, json={"results": [], "failed_results": [{"url": "u", "error": "blocked"}]})
    )
    with pytest.raises(ExtractionError, match="blocked"):
        await TavilyPageExtractor("k", 5, allow_private=True).extract("https://arxiv.org/abs/1")
