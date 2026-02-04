"""Unit tests for tool handlers using DummyMCP."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from web_search_mcp.models.common import Metadata
from web_search_mcp.models.scrape import DiscoverResult, ScrapeResult
from web_search_mcp.models.search import SearchResponse, SearchResult


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class DummyCtx:
    def __init__(self, app_ctx):
        self.request_context = SimpleNamespace(lifespan_context=app_ctx)


@pytest.mark.asyncio
async def test_web_search_tool_with_scrape():
    from web_search_mcp.tools import search as search_tool

    mcp = DummyMCP()
    search_tool.register(mcp)
    web_search = mcp.tools["web_search"]

    provider_registry = MagicMock()
    provider_registry.search = AsyncMock(
        return_value=SearchResponse(
            query="q",
            results=[
                SearchResult(
                    url="https://example.com",
                    title="Example",
                    snippet="",
                    position=1,
                )
            ],
            provider="mock",
            search_time_ms=10.0,
        )
    )

    cache = MagicMock()
    cache.get_search = AsyncMock(return_value=None)
    cache.set_search = AsyncMock()
    cache.get_scrape = AsyncMock(return_value=None)
    cache.set_scrape = AsyncMock()

    scraper = MagicMock()
    scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            url="https://example.com",
            markdown="# Example",
            metadata=Metadata(title="Example"),
            scrape_time_ms=10.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(provider_registry=provider_registry, cache=cache, scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await web_search(
        query="q",
        max_results=5,
        scrape_options={"formats": ["markdown"]},
        ctx=ctx,
    )

    assert result["results"][0]["scrape"]["success"] is True


@pytest.mark.asyncio
async def test_web_search_tool_cache_hit():
    from web_search_mcp.tools import search as search_tool

    mcp = DummyMCP()
    search_tool.register(mcp)
    web_search = mcp.tools["web_search"]

    cache = MagicMock()
    cache.get_search = AsyncMock(
        return_value={"query": "q", "results": [], "provider": "mock", "search_time_ms": 1.0}
    )

    app_ctx = SimpleNamespace(provider_registry=MagicMock(), cache=cache, scraper=MagicMock())
    ctx = DummyCtx(app_ctx)

    result = await web_search(query="q", max_results=5, ctx=ctx)
    assert result["cached"] is True


@pytest.mark.asyncio
async def test_scrape_url_tool_cache_miss():
    from web_search_mcp.tools import scrape as scrape_tool

    mcp = DummyMCP()
    scrape_tool.register(mcp)
    scrape_url = mcp.tools["scrape_url"]

    cache = MagicMock()
    cache.get_scrape = AsyncMock(return_value=None)
    cache.set_scrape = AsyncMock()

    scraper = MagicMock()
    scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            url="https://example.com",
            markdown="# Example",
            metadata=Metadata(title="Example"),
            scrape_time_ms=10.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(cache=cache, scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await scrape_url(url="https://example.com", formats=["markdown"], ctx=ctx)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_scrape_url_tool_cache_hit():
    from web_search_mcp.tools import scrape as scrape_tool

    mcp = DummyMCP()
    scrape_tool.register(mcp)
    scrape_url = mcp.tools["scrape_url"]

    cache = MagicMock()
    cache.get_scrape = AsyncMock(return_value={"url": "https://example.com", "success": True})
    cache.set_scrape = AsyncMock()

    app_ctx = SimpleNamespace(cache=cache, scraper=MagicMock())
    ctx = DummyCtx(app_ctx)

    result = await scrape_url(url="https://example.com", ctx=ctx)
    assert result["cached"] is True


@pytest.mark.asyncio
async def test_batch_scrape_tool_validation():
    from web_search_mcp.tools import batch_scrape as batch_tool

    mcp = DummyMCP()
    batch_tool.register(mcp)
    batch_scrape = mcp.tools["batch_scrape"]

    app_ctx = SimpleNamespace(scraper=MagicMock())
    ctx = DummyCtx(app_ctx)

    result = await batch_scrape(urls=[], ctx=ctx)
    assert result["success"] is False


@pytest.mark.asyncio
async def test_batch_scrape_tool_success():
    from web_search_mcp.tools import batch_scrape as batch_tool

    mcp = DummyMCP()
    batch_tool.register(mcp)
    batch_scrape = mcp.tools["batch_scrape"]

    scraper = MagicMock()
    scraper.scrape_batch = AsyncMock(
        return_value=[
            ScrapeResult(
                url="https://example.com/1",
                markdown="A",
                metadata=Metadata(),
                scrape_time_ms=1.0,
                success=True,
            )
        ]
    )

    app_ctx = SimpleNamespace(scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await batch_scrape(urls=["https://example.com/1"], ctx=ctx)
    assert result["successful"] == 1
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_batch_scrape_tool_too_many_urls():
    from web_search_mcp.tools import batch_scrape as batch_tool

    mcp = DummyMCP()
    batch_tool.register(mcp)
    batch_scrape = mcp.tools["batch_scrape"]

    app_ctx = SimpleNamespace(scraper=MagicMock())
    ctx = DummyCtx(app_ctx)

    urls = [f"https://example.com/{i}" for i in range(51)]
    result = await batch_scrape(urls=urls, ctx=ctx)
    assert result["success"] is False


@pytest.mark.asyncio
async def test_discover_urls_tool():
    from web_search_mcp.tools import discover as discover_tool

    mcp = DummyMCP()
    discover_tool.register(mcp)
    discover_urls = mcp.tools["discover_urls"]

    scraper = MagicMock()
    scraper.discover_urls = AsyncMock(
        return_value=DiscoverResult(
            base_url="https://example.com",
            urls=["https://example.com/a"],
            total_urls=1,
            discover_time_ms=10.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await discover_urls(url="https://example.com", ctx=ctx)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_map_urls_tool_filters():
    from web_search_mcp.tools import map as map_tool

    mcp = DummyMCP()
    map_tool.register(mcp)
    map_urls = mcp.tools["map_urls"]

    scraper = MagicMock()
    scraper.discover_urls = AsyncMock(
        return_value=DiscoverResult(
            base_url="https://example.com",
            urls=[
                "https://example.com/docs",
                "https://example.com/blog",
                "https://example.com/ignore?utm=1",
            ],
            total_urls=3,
            discover_time_ms=5.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await map_urls(
        url="https://example.com",
        search="docs",
        exclude_patterns=[r"utm="],
        ctx=ctx,
    )

    assert result["urls"] == ["https://example.com/docs"]


@pytest.mark.asyncio
async def test_map_urls_tool_error():
    from web_search_mcp.tools import map as map_tool

    mcp = DummyMCP()
    map_tool.register(mcp)
    map_urls = mcp.tools["map_urls"]

    scraper = MagicMock()
    scraper.discover_urls = AsyncMock(
        return_value=DiscoverResult(
            base_url="https://example.com",
            urls=[],
            total_urls=0,
            discover_time_ms=1.0,
            success=False,
            error_message="fail",
        )
    )

    app_ctx = SimpleNamespace(scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await map_urls(url="https://example.com", ctx=ctx)
    assert result["success"] is False


@pytest.mark.asyncio
async def test_map_urls_tool_invalid_regex():
    from web_search_mcp.tools import map as map_tool

    mcp = DummyMCP()
    map_tool.register(mcp)
    map_urls = mcp.tools["map_urls"]

    scraper = MagicMock()
    scraper.discover_urls = AsyncMock(
        return_value=DiscoverResult(
            base_url="https://example.com",
            urls=["https://example.com/a", "https://example.com/b"],
            total_urls=2,
            discover_time_ms=1.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await map_urls(
        url="https://example.com",
        exclude_patterns=["[bad"],
        ctx=ctx,
    )
    assert result["urls"] == ["https://example.com/a", "https://example.com/b"]


@pytest.mark.asyncio
async def test_attach_scrapes_cache_hit():
    from web_search_mcp.models.scrape import ScrapeOptions
    from web_search_mcp.tools.search import _attach_scrapes

    cache = MagicMock()
    cache.get_scrape = AsyncMock(return_value={"url": "https://example.com", "success": True})
    cache.set_scrape = AsyncMock()

    scraper = MagicMock()
    app_ctx = SimpleNamespace(cache=cache, scraper=scraper)

    result_dict = {"results": [{"url": "https://example.com"}]}
    options = ScrapeOptions(formats=["markdown"])

    updated = await _attach_scrapes(result_dict, options, max_scrape_results=1, app_ctx=app_ctx)
    assert updated["results"][0]["scrape"]["cached"] is True


@pytest.mark.asyncio
async def test_attach_scrapes_empty_results():
    from web_search_mcp.models.scrape import ScrapeOptions
    from web_search_mcp.tools.search import _attach_scrapes

    app_ctx = SimpleNamespace(cache=MagicMock(), scraper=MagicMock())
    result_dict = {"results": []}
    updated = await _attach_scrapes(result_dict, ScrapeOptions(), None, app_ctx)
    assert updated["results"] == []


@pytest.mark.asyncio
async def test_attach_scrapes_success_caches():
    from web_search_mcp.models.scrape import ScrapeOptions
    from web_search_mcp.tools.search import _attach_scrapes

    cache = MagicMock()
    cache.get_scrape = AsyncMock(return_value=None)
    cache.set_scrape = AsyncMock()

    scraper = MagicMock()
    scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            url="https://example.com",
            markdown="md",
            metadata=Metadata(),
            scrape_time_ms=1.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(cache=cache, scraper=scraper)
    result_dict = {"results": [{"url": "https://example.com"}, {"url": None}]}

    updated = await _attach_scrapes(result_dict, ScrapeOptions(formats=["markdown"]), None, app_ctx)
    assert updated["results"][0]["scrape"]["success"] is True
    cache.set_scrape.assert_awaited()


@pytest.mark.asyncio
async def test_web_search_cache_hit_with_scrape_options():
    from web_search_mcp.tools import search as search_tool

    mcp = DummyMCP()
    search_tool.register(mcp)
    web_search = mcp.tools["web_search"]

    cache = MagicMock()
    cache.get_search = AsyncMock(
        return_value={"query": "q", "results": [{"url": "https://example.com"}], "provider": "mock"}
    )
    cache.get_scrape = AsyncMock(return_value=None)
    cache.set_scrape = AsyncMock()

    scraper = MagicMock()
    scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            url="https://example.com",
            markdown="md",
            metadata=Metadata(),
            scrape_time_ms=1.0,
            success=True,
        )
    )

    app_ctx = SimpleNamespace(provider_registry=MagicMock(), cache=cache, scraper=scraper)
    ctx = DummyCtx(app_ctx)

    result = await web_search(
        query="q",
        max_results=5,
        scrape_options={"formats": ["markdown"]},
        ctx=ctx,
    )
    assert result["cached"] is True
    assert result["results"][0]["scrape"]["success"] is True
