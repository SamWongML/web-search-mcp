"""Unit tests for Jina Reader scraper."""

from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from web_search_mcp.models.common import Link, Metadata
from web_search_mcp.models.scrape import ScrapeOptions, ScrapeResult
from web_search_mcp.scrapers.jina_reader import JinaReaderScraper


@pytest.mark.asyncio
async def test_jina_name_and_shared_client():
    shared = SimpleNamespace()
    scraper = JinaReaderScraper(http_client=shared)  # type: ignore[arg-type]
    assert scraper.name == "jina_reader"

    client = await scraper._get_client()
    assert client is shared


@pytest.mark.asyncio
@respx.mock
async def test_jina_scrape_success():
    url = "https://example.com"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=Response(
            200,
            json={
                "code": 200,
                "data": {
                    "content": "# Title\n\nBody",
                    "title": "Title",
                    "description": "Desc",
                },
            },
        )
    )

    scraper = JinaReaderScraper()
    options = ScrapeOptions(formats=["markdown", "text"], max_length=50)
    result = await scraper.scrape(url, options)

    assert result.success is True
    assert result.markdown.startswith("# Title")
    assert result.text is not None
    assert result.metadata.title == "Title"


@pytest.mark.asyncio
@respx.mock
async def test_jina_scrape_with_api_key_and_headers():
    url = "https://example.com"
    route = respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=Response(
            200,
            json={
                "code": 200,
                "data": {"content": "Content", "title": "Title", "description": "Desc"},
            },
        )
    )

    scraper = JinaReaderScraper(api_key="token")
    options = ScrapeOptions(include_links=True, include_images=True, formats=["markdown"])
    result = await scraper.scrape(url, options)

    assert result.success is True
    request = route.calls[0].request
    assert request.headers.get("Authorization") == "Bearer token"
    assert request.headers.get("X-With-Links-Summary") == "true"
    assert request.headers.get("X-With-Images-Summary") == "true"


@pytest.mark.asyncio
@respx.mock
async def test_jina_scrape_error_status():
    url = "https://example.com/error"
    respx.get(f"https://r.jina.ai/{url}").mock(return_value=Response(500, text="Error"))

    scraper = JinaReaderScraper()
    result = await scraper.scrape(url)

    assert result.success is False
    assert "error" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_jina_scrape_request_error(monkeypatch):
    import httpx

    scraper = JinaReaderScraper()

    class DummyClient:
        async def get(self, *args, **kwargs):  # noqa: ARG002
            raise httpx.RequestError("boom", request=httpx.Request("GET", "https://x"))

        async def aclose(self):
            return None

    async def fake_get_client():
        return DummyClient()

    monkeypatch.setattr(scraper, "_get_client", fake_get_client)

    result = await scraper.scrape("https://example.com")
    assert result.success is False


@pytest.mark.asyncio
@respx.mock
async def test_jina_scrape_no_optional_headers():
    url = "https://example.com"
    route = respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=Response(200, json={"code": 200, "data": {"content": "Content"}})
    )

    scraper = JinaReaderScraper()
    options = ScrapeOptions(include_links=False, include_images=False, formats=["markdown"])
    result = await scraper.scrape(url, options)

    assert result.success is True
    request = route.calls[0].request
    assert "X-With-Links-Summary" not in request.headers
    assert "X-With-Images-Summary" not in request.headers


@pytest.mark.asyncio
async def test_jina_discover_urls_error():
    scraper = JinaReaderScraper()

    async def fake_scrape(url, options):  # noqa: ARG001
        return ScrapeResult.from_error(url, "fail", 1.0)

    scraper.scrape = fake_scrape  # type: ignore[assignment]

    result = await scraper.discover_urls("https://example.com", max_urls=10)
    assert result.success is False


@pytest.mark.asyncio
@respx.mock
async def test_jina_scrape_error_code():
    url = "https://example.com/bad"
    respx.get(f"https://r.jina.ai/{url}").mock(
        return_value=Response(200, json={"code": 500, "message": "Bad"}))

    scraper = JinaReaderScraper()
    result = await scraper.scrape(url)

    assert result.success is False
    assert "Bad" in (result.error_message or "")


@pytest.mark.asyncio
async def test_jina_discover_urls_filters():
    scraper = JinaReaderScraper()

    links = [
        Link(url="https://example.com/page"),
        Link(url="https://sub.example.com/page"),
        Link(url="https://other.com/page"),
    ]
    fake_result = ScrapeResult(
        url="https://example.com",
        markdown="",
        metadata=Metadata(),
        links=links,
        scrape_time_ms=10.0,
        success=True,
    )

    async def fake_scrape(url, options):  # noqa: ARG001
        return fake_result

    scraper.scrape = fake_scrape  # type: ignore[assignment]

    result = await scraper.discover_urls(
        "https://example.com",
        max_urls=10,
        same_domain_only=True,
        include_subdomains=False,
    )
    assert all("example.com" in url for url in result.urls)
    assert all("sub.example.com" not in url for url in result.urls)

    result_sub = await scraper.discover_urls(
        "https://example.com",
        max_urls=10,
        same_domain_only=True,
        include_subdomains=True,
    )
    assert any("sub.example.com" in url for url in result_sub.urls)


@pytest.mark.asyncio
async def test_jina_discover_urls_all_domains():
    scraper = JinaReaderScraper()

    links = [
        Link(url="https://example.com/page"),
        Link(url="https://other.com/page"),
    ]
    fake_result = ScrapeResult(
        url="https://example.com",
        markdown="",
        metadata=Metadata(),
        links=links,
        scrape_time_ms=10.0,
        success=True,
    )

    async def fake_scrape(url, options):  # noqa: ARG001
        return fake_result

    scraper.scrape = fake_scrape  # type: ignore[assignment]

    result = await scraper.discover_urls(
        "https://example.com",
        max_urls=10,
        same_domain_only=False,
    )
    assert "https://other.com/page" in result.urls


@pytest.mark.asyncio
async def test_jina_scrape_general_exception(monkeypatch):
    scraper = JinaReaderScraper()

    class DummyClient:
        async def get(self, *args, **kwargs):  # noqa: ARG002
            raise RuntimeError("boom")

        async def aclose(self):
            return None

    async def fake_get_client():
        return DummyClient()

    monkeypatch.setattr(scraper, "_get_client", fake_get_client)

    result = await scraper.scrape("https://example.com")
    assert result.success is False


@pytest.mark.asyncio
async def test_jina_scrape_batch():
    scraper = JinaReaderScraper()

    async def fake_scrape(url, options):  # noqa: ARG001
        return ScrapeResult(
            url=url,
            markdown="",
            metadata=Metadata(),
            scrape_time_ms=1.0,
            success=True,
        )

    scraper.scrape = fake_scrape  # type: ignore[assignment]
    results = await scraper.scrape_batch(["https://example.com/1", "https://example.com/2"])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_jina_close_noop():
    scraper = JinaReaderScraper()
    await scraper.close()
