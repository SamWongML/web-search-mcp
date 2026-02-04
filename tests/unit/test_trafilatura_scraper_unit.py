"""Unit tests for Trafilatura scraper internals."""

import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
import respx
from httpx import Response

from web_search_mcp.models.scrape import ScrapeOptions
from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper


@pytest.mark.asyncio
async def test_extract_content_with_stub(monkeypatch):
    @dataclass
    class Meta:
        title: str = "Title"
        description: str = "Desc"
        author: str = "Author"
        sitename: str = "Site"
        language: str = "en"

    class DummyTrafilatura:
        @staticmethod
        def extract(*args, **kwargs):  # noqa: ARG001
            return "md content"

        @staticmethod
        def extract_metadata(*args, **kwargs):  # noqa: ARG001
            return Meta()

    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)

    scraper = TrafilaturaScraper()
    options = ScrapeOptions()
    markdown, metadata = await scraper._extract_content("<html></html>", "https://example.com", options)

    assert "md content" in markdown
    assert metadata.title == "Title"


@pytest.mark.asyncio
async def test_get_client_returns_shared():
    shared = SimpleNamespace()
    scraper = TrafilaturaScraper(http_client=shared)  # type: ignore[arg-type]
    client = await scraper._get_client()
    assert client is shared


@pytest.mark.asyncio
async def test_extract_content_import_error(monkeypatch):
    import builtins
    from web_search_mcp.exceptions import ScraperContentError

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "trafilatura":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    scraper = TrafilaturaScraper()
    with pytest.raises(ScraperContentError):
        await scraper._extract_content("<html></html>", "https://example.com", ScrapeOptions())


@pytest.mark.asyncio
@respx.mock
async def test_scrape_http_status_error():
    respx.get("https://example.com/404").mock(return_value=Response(404, text="Not found"))

    scraper = TrafilaturaScraper()
    result = await scraper.scrape("https://example.com/404")

    assert result.success is False
    assert "HTTP 404" in (result.error_message or "")


@pytest.mark.asyncio
async def test_scrape_request_error(monkeypatch):
    import httpx

    class DummyClient:
        async def get(self, *args, **kwargs):  # noqa: ARG002
            raise httpx.RequestError("boom", request=httpx.Request("GET", "https://x"))

        async def aclose(self):
            return None

    scraper = TrafilaturaScraper(http_client=DummyClient())  # type: ignore[arg-type]
    result = await scraper.scrape("https://example.com")

    assert result.success is False


@pytest.mark.asyncio
@respx.mock
async def test_scrape_formats(monkeypatch):
    html = "<html><body><main>Hi</main><a href='/a'>A</a><img src='/i.png'></body></html>"
    respx.get("https://example.com/page").mock(return_value=Response(200, text=html))

    def fake_extract(html, **kwargs):  # noqa: ARG001
        output_format = kwargs.get("output_format")
        if output_format == "markdown":
            return "md"
        if output_format == "text":
            return "text"
        if output_format == "html":
            return "<main>html</main>"
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.trafilatura_scraper.extract_main_content",
        fake_extract,
    )

    scraper = TrafilaturaScraper()
    options = ScrapeOptions(
        include_links=True,
        include_images=True,
        formats=["markdown", "text", "html", "raw_html"],
        max_length=100,
    )

    result = await scraper.scrape("https://example.com/page", options)
    assert result.success is True
    assert result.markdown == "md"
    assert result.text == "md"
    assert result.html == "<main>html</main>"
    assert result.raw_html is not None


def test_build_content_text_only(monkeypatch):
    def fake_extract(html, **kwargs):  # noqa: ARG001
        if kwargs.get("output_format") == "text":
            return "Text content"
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.trafilatura_scraper.extract_main_content",
        fake_extract,
    )

    scraper = TrafilaturaScraper()
    options = ScrapeOptions(formats=["text"], only_main_content=True)
    markdown, text, html_out = scraper._build_content("<html></html>", "https://example.com", options)

    assert markdown == ""
    assert text == "Text content"
    assert html_out is None


@pytest.mark.asyncio
async def test_extract_links_and_images():
    html = "<a href='https://example.com/a'>A</a><img src='https://example.com/i.png' alt='i'>"
    scraper = TrafilaturaScraper()

    links = await scraper._extract_links(html, "https://example.com")
    images = await scraper._extract_images(html, "https://example.com")

    assert len(links) == 1
    assert links[0].url == "https://example.com/a"
    assert len(images) == 1
    assert images[0].url == "https://example.com/i.png"


@pytest.mark.asyncio
async def test_extract_content_metadata_fallback(monkeypatch):
    class DummyMeta:
        def __init__(self):
            self.title = "Title"
            self.description = "Desc"
            self.author = "Author"
            self.sitename = "Site"
            self.language = "en"

        def _asdict(self):
            return {
                "title": self.title,
                "description": self.description,
                "author": self.author,
                "sitename": self.sitename,
                "language": self.language,
            }

    class DummyTrafilatura:
        @staticmethod
        def extract(*args, **kwargs):  # noqa: ARG001
            return "md content"

        @staticmethod
        def extract_metadata(*args, **kwargs):  # noqa: ARG001
            return DummyMeta()

    monkeypatch.setitem(sys.modules, "trafilatura", DummyTrafilatura)

    scraper = TrafilaturaScraper()
    markdown, metadata = await scraper._extract_content("<html></html>", "https://example.com", ScrapeOptions())

    assert "md content" in markdown
    assert metadata.title == "Title"


@pytest.mark.asyncio
async def test_extract_links_filters():
    html = (
        "<a href='https://example.com/a'>A</a>"
        "<a href='https://example.com/a'>Dup</a>"
        "<a href='mailto:test@example.com'>Mail</a>"
    )
    scraper = TrafilaturaScraper()
    links = await scraper._extract_links(html, "https://example.com")
    assert len(links) == 1


@pytest.mark.asyncio
async def test_extract_images_filters():
    html = (
        "<img src='https://example.com/i.png' alt='i'>"
        "<img src='https://example.com/i.png' alt='dup'>"
        "<img src='data:image/png;base64,abc'>"
    )
    scraper = TrafilaturaScraper()
    images = await scraper._extract_images(html, "https://example.com")
    assert len(images) == 1


@pytest.mark.asyncio
async def test_discover_urls_subdomains(monkeypatch):
    scraper = TrafilaturaScraper()

    async def fake_scrape(url, options):  # noqa: ARG001
        from web_search_mcp.models.common import Link, Metadata
        from web_search_mcp.models.scrape import ScrapeResult

        links = [
            Link(url="https://example.com/a"),
            Link(url="https://sub.example.com/b"),
            Link(url="https://other.com/c"),
        ]
        return ScrapeResult(
            url="https://example.com",
            markdown="",
            metadata=Metadata(),
            links=links,
            scrape_time_ms=1.0,
            success=True,
        )

    scraper.scrape = fake_scrape  # type: ignore[assignment]

    result = await scraper.discover_urls(
        "https://example.com",
        max_urls=10,
        same_domain_only=True,
        include_subdomains=False,
    )
    assert all("sub.example.com" not in url for url in result.urls)

    result_sub = await scraper.discover_urls(
        "https://example.com",
        max_urls=10,
        same_domain_only=True,
        include_subdomains=True,
    )
    assert any("sub.example.com" in url for url in result_sub.urls)


@pytest.mark.asyncio
async def test_discover_urls_error(monkeypatch):
    scraper = TrafilaturaScraper()

    async def fake_scrape(url, options):  # noqa: ARG001
        from web_search_mcp.models.scrape import ScrapeResult

        return ScrapeResult.from_error(url, "fail", 1.0)

    scraper.scrape = fake_scrape  # type: ignore[assignment]
    result = await scraper.discover_urls("https://example.com")
    assert result.success is False
