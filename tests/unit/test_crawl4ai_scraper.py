"""Unit tests for Crawl4AI scraper using stubs."""

import sys
from types import SimpleNamespace

import pytest

from web_search_mcp.models.scrape import ScrapeOptions
from web_search_mcp.scrapers.crawl4ai_scraper import Crawl4AIScraper


class DummyMarkdown:
    raw_markdown = "raw markdown"
    fit_markdown = "fit markdown"


class DummyResult:
    def __init__(self, url: str, success: bool = True) -> None:
        self.url = url
        self.success = success
        self.html = "<html><body><main>Hi</main></body></html>"
        self.error_message = None if success else "failed"
        self.metadata = {
            "title": "Title",
            "description": "Desc",
            "author": "Author",
            "language": "en",
        }
        self.links = {
            "internal": [
                {"href": "https://example.com/page", "text": "Page"},
                {"href": "https://sub.example.com/page", "text": "Sub"},
            ],
            "external": [{"href": "https://other.com/page", "text": "Other"}],
        }
        self.media = {"images": [{"src": "https://example.com/image.png", "alt": "Alt"}]}
        self.markdown = DummyMarkdown()


class DummyCrawler:
    def __init__(self, config):  # noqa: ARG002
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
        return None

    async def arun(self, url, config):  # noqa: ARG002
        if "fail" in url:
            return DummyResult(url, success=False)
        return DummyResult(url, success=True)

    async def arun_many(self, urls, config, dispatcher):  # noqa: ARG002
        return [DummyResult(url, success="fail" not in url) for url in urls]


class DummyConfig:
    def __init__(self, **kwargs):  # noqa: ARG002
        pass


class DummyCacheMode:
    BYPASS = "BYPASS"


def install_crawl4ai_stub(monkeypatch):
    stub = SimpleNamespace(
        AsyncWebCrawler=DummyCrawler,
        BrowserConfig=DummyConfig,
        CacheMode=DummyCacheMode,
        CrawlerRunConfig=DummyConfig,
        MemoryAdaptiveDispatcher=DummyConfig,
    )
    monkeypatch.setitem(sys.modules, "crawl4ai", stub)


def install_custom_crawl4ai_stub(monkeypatch, crawler_cls):
    stub = SimpleNamespace(
        AsyncWebCrawler=crawler_cls,
        BrowserConfig=DummyConfig,
        CacheMode=DummyCacheMode,
        CrawlerRunConfig=DummyConfig,
        MemoryAdaptiveDispatcher=DummyConfig,
    )
    monkeypatch.setitem(sys.modules, "crawl4ai", stub)


@pytest.mark.asyncio
async def test_scrape_success_formats(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    def fake_extract(html, **kwargs):  # noqa: ARG001
        output_format = kwargs.get("output_format", "markdown")
        if output_format == "markdown":
            return ""
        if output_format == "text":
            return "text content"
        if output_format == "html":
            return "<main>html</main>"
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(
        include_links=True,
        include_images=True,
        formats=["markdown", "text", "html", "raw_html"],
    )
    result = await scraper.scrape("https://example.com", options)

    assert result.success is True
    assert result.markdown == "raw markdown"
    assert result.text == "raw markdown"
    assert result.html == "<main>html</main>"
    assert result.raw_html is not None
    assert len(result.links) > 0
    assert len(result.images) > 0


@pytest.mark.asyncio
async def test_scrape_failure(monkeypatch):
    install_crawl4ai_stub(monkeypatch)
    scraper = Crawl4AIScraper()
    result = await scraper.scrape("https://example.com/fail")

    assert result.success is False
    assert result.error_message is not None


@pytest.mark.asyncio
async def test_scrape_batch(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    def fake_extract(html, **kwargs):  # noqa: ARG001
        return "md"

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(formats=["markdown"])
    results = await scraper.scrape_batch(
        ["https://example.com/1", "https://example.com/fail"],
        options=options,
        max_concurrent=2,
    )

    assert len(results) == 2
    assert any(r.success for r in results)
    assert any(not r.success for r in results)


@pytest.mark.asyncio
async def test_discover_urls_subdomains(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    def fake_extract(html, **kwargs):  # noqa: ARG001
        return "md"

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
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
async def test_scrape_with_wait_for_and_truncate(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    long_text = "A" * 200

    def fake_extract(html, **kwargs):  # noqa: ARG001
        return long_text

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(
        include_links=False,
        include_images=False,
        include_metadata=False,
        wait_for_selector="#main",
        formats=["markdown"],
        max_length=50,
    )

    result = await scraper.scrape("https://example.com", options)
    assert result.success is True
    assert len(result.markdown) < len(long_text)
    assert result.links == []
    assert result.images == []
    assert result.metadata.title is None

    await scraper.close()
    assert scraper._initialized is False


@pytest.mark.asyncio
async def test_ensure_initialized_import_error(monkeypatch):
    import builtins

    scraper = Crawl4AIScraper()
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "crawl4ai":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError):
        await scraper._ensure_initialized()


def test_scraper_name():
    scraper = Crawl4AIScraper()
    assert scraper.name == "crawl4ai"


@pytest.mark.asyncio
async def test_ensure_initialized_exception(monkeypatch):
    class BadCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            raise RuntimeError("boom")

    install_custom_crawl4ai_stub(monkeypatch, BadCrawler)

    scraper = Crawl4AIScraper()
    with pytest.raises(RuntimeError):
        await scraper._ensure_initialized()


def test_build_content_text_only(monkeypatch):
    def fake_extract(html, **kwargs):  # noqa: ARG001
        if kwargs.get("output_format") == "text":
            return "Text content"
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(formats=["text"], only_main_content=True)
    markdown, text, html_out = scraper._build_content("<html></html>", "https://example.com", options)

    assert markdown == ""
    assert text == "Text content"
    assert html_out is None


def test_build_content_fallback_and_truncate(monkeypatch):
    def fake_extract(html, **kwargs):  # noqa: ARG001
        output_format = kwargs.get("output_format")
        if output_format == "html":
            return "<main>html</main>"
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(formats=["markdown", "text", "html"], max_length=20)
    long_fallback = "A" * 200
    markdown, text, html_out = scraper._build_content(
        "<html></html>",
        "https://example.com",
        options,
        fallback_markdown=long_fallback,
    )

    assert "[Content truncated...]" in markdown
    assert len(markdown) < len(long_fallback)
    assert text is not None
    assert html_out == "<main>html</main>"


@pytest.mark.asyncio
async def test_scrape_string_markdown_and_links(monkeypatch):
    class PlainResult:
        def __init__(self, url: str) -> None:
            self.url = url
            self.success = True
            self.html = "<html><body><main>Hi</main></body></html>"
            self.error_message = None
            self.metadata = {"title": "Title"}
            self.links = {"internal": ["https://example.com/str"]}
            self.media = {"images": [{"src": "https://example.com/i.png", "alt": "i"}]}
            self.markdown = "plain markdown"

    class PlainCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def arun(self, url, config):  # noqa: ARG002
            return PlainResult(url)

    install_custom_crawl4ai_stub(monkeypatch, PlainCrawler)

    def fake_extract(html, **kwargs):  # noqa: ARG001
        return ""

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(formats=["markdown", "text", "raw_html"])
    result = await scraper.scrape("https://example.com", options)

    assert result.success is True
    assert result.markdown == "plain markdown"
    assert result.text is not None
    assert result.raw_html is not None
    assert any(link.url == "https://example.com/str" for link in result.links)


@pytest.mark.asyncio
async def test_scrape_exception(monkeypatch):
    class ErrorCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def arun(self, url, config):  # noqa: ARG002
            raise RuntimeError("boom")

    install_custom_crawl4ai_stub(monkeypatch, ErrorCrawler)
    scraper = Crawl4AIScraper()
    result = await scraper.scrape("https://example.com")
    assert result.success is False


@pytest.mark.asyncio
async def test_scrape_batch_metadata_and_fallback(monkeypatch):
    class RawMarkdown:
        raw_markdown = "raw"

    class BatchResult:
        def __init__(self, url: str, success: bool = True) -> None:
            self.url = url
            self.success = success
            self.html = "<html><body><main>Hi</main></body></html>"
            self.error_message = None if success else "failed"
            self.metadata = {"title": "Title", "description": "Desc"}
            self.markdown = RawMarkdown() if "raw" in url else "plain"

    class BatchCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def arun_many(self, urls, config, dispatcher):  # noqa: ARG002
            return [BatchResult(url, success="fail" not in url) for url in urls]

    install_custom_crawl4ai_stub(monkeypatch, BatchCrawler)

    def fake_extract(html, **kwargs):  # noqa: ARG001
        return "md"

    monkeypatch.setattr(
        "web_search_mcp.scrapers.crawl4ai_scraper.extract_main_content",
        fake_extract,
    )

    scraper = Crawl4AIScraper()
    options = ScrapeOptions(formats=["markdown"], include_metadata=True)
    results = await scraper.scrape_batch(
        ["https://example.com/raw", "https://example.com/plain", "https://example.com/fail"],
        options=options,
        max_concurrent=2,
    )

    assert any(r.success for r in results)
    assert any(not r.success for r in results)


@pytest.mark.asyncio
async def test_scrape_batch_exception(monkeypatch):
    class BatchErrorCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def arun_many(self, urls, config, dispatcher):  # noqa: ARG002
            raise RuntimeError("boom")

    install_custom_crawl4ai_stub(monkeypatch, BatchErrorCrawler)
    scraper = Crawl4AIScraper()
    results = await scraper.scrape_batch(["https://example.com/a"], max_concurrent=1)
    assert results[0].success is False


@pytest.mark.asyncio
async def test_discover_urls_error_and_all_domains(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    async def fake_scrape(url, options):  # noqa: ARG001
        from web_search_mcp.models.scrape import ScrapeResult

        return ScrapeResult.from_error(url, "fail", 1.0)

    scraper = Crawl4AIScraper()
    scraper.scrape = fake_scrape  # type: ignore[assignment]
    result = await scraper.discover_urls("https://example.com")
    assert result.success is False

    # same_domain_only False
    async def good_scrape(url, options):  # noqa: ARG001
        from web_search_mcp.models.common import Link, Metadata
        from web_search_mcp.models.scrape import ScrapeResult

        links = [Link(url="https://other.com/page")]
        return ScrapeResult(
            url=url,
            markdown="",
            metadata=Metadata(),
            links=links,
            scrape_time_ms=1.0,
            success=True,
        )

    scraper.scrape = good_scrape  # type: ignore[assignment]
    result = await scraper.discover_urls("https://example.com", same_domain_only=False)
    assert "https://other.com/page" in result.urls


@pytest.mark.asyncio
async def test_discover_urls_exception(monkeypatch):
    install_crawl4ai_stub(monkeypatch)

    async def boom(url, options):  # noqa: ARG001
        raise RuntimeError("boom")

    scraper = Crawl4AIScraper()
    scraper.scrape = boom  # type: ignore[assignment]
    result = await scraper.discover_urls("https://example.com")
    assert result.success is False


@pytest.mark.asyncio
async def test_close_exception(monkeypatch):
    class CloseCrawler:
        def __init__(self, config):  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            raise RuntimeError("boom")

    install_custom_crawl4ai_stub(monkeypatch, CloseCrawler)

    scraper = Crawl4AIScraper()
    await scraper._ensure_initialized()
    await scraper.close()
    assert scraper._initialized is False
