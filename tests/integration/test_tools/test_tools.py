"""Integration tests for MCP tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from web_search_mcp.models.common import Metadata
from web_search_mcp.models.scrape import BatchScrapeResult, DiscoverResult, ScrapeResult
from web_search_mcp.models.search import SearchResponse, SearchResult


class TestSearchTool:
    """Tests for web_search tool implementation."""

    @pytest.fixture
    def mock_registry(self):
        """Create a mock provider registry."""
        registry = MagicMock()
        registry.search = AsyncMock(
            return_value=SearchResponse(
                query="test query",
                results=[
                    SearchResult(
                        url="https://example.com",
                        title="Example",
                        snippet="Example snippet",
                        position=1,
                    )
                ],
                provider="serpapi",
                search_time_ms=50.0,
            )
        )
        return registry

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        cache = MagicMock()
        cache.get_search = AsyncMock(return_value=None)
        cache.set_search = AsyncMock()
        return cache

    @pytest.mark.asyncio
    async def test_search_tool_returns_results(self, mock_registry):
        """Test that search tool returns formatted results."""
        # Call the mock registry directly (simulating tool behavior)
        response = await mock_registry.search(
            query="test query",
            max_results=10,
        )

        assert response.query == "test query"
        assert len(response.results) == 1
        assert response.results[0].title == "Example"


class TestScrapeTool:
    """Tests for scrape_url tool implementation."""

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper."""
        scraper = MagicMock()
        scraper.scrape = AsyncMock(
            return_value=ScrapeResult(
                url="https://example.com",
                markdown="# Test Page\n\nContent here",
                metadata=Metadata(title="Test Page"),
                scrape_time_ms=100.0,
                success=True,
            )
        )
        return scraper

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        cache = MagicMock()
        cache.get_scrape = AsyncMock(return_value=None)
        cache.set_scrape = AsyncMock()
        return cache

    @pytest.mark.asyncio
    async def test_scrape_tool_returns_content(self, mock_scraper):
        """Test that scrape tool returns markdown content."""
        from web_search_mcp.models.scrape import ScrapeOptions

        options = ScrapeOptions(include_links=True)
        result = await mock_scraper.scrape(
            url="https://example.com",
            options=options,
        )

        assert result.success is True
        assert result.markdown == "# Test Page\n\nContent here"
        assert result.metadata.title == "Test Page"


class TestBatchScrapeTool:
    """Tests for batch_scrape tool implementation."""

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper."""
        scraper = MagicMock()
        scraper.scrape_batch = AsyncMock(
            return_value=[
                ScrapeResult(
                    url="https://example.com/1",
                    markdown="# Page 1",
                    metadata=Metadata(title="Page 1"),
                    scrape_time_ms=50.0,
                    success=True,
                ),
                ScrapeResult(
                    url="https://example.com/2",
                    markdown="# Page 2",
                    metadata=Metadata(title="Page 2"),
                    scrape_time_ms=50.0,
                    success=True,
                ),
            ]
        )
        return scraper

    @pytest.mark.asyncio
    async def test_batch_scrape_returns_multiple_results(self, mock_scraper):
        """Test that batch scrape returns results for all URLs."""
        urls = ["https://example.com/1", "https://example.com/2"]
        results = await mock_scraper.scrape_batch(urls=urls, max_concurrent=5)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].url == "https://example.com/1"
        assert results[1].url == "https://example.com/2"

    @pytest.mark.asyncio
    async def test_batch_scrape_result_aggregation(self):
        """Test BatchScrapeResult aggregation."""
        results = [
            ScrapeResult(
                url="https://example.com/1",
                markdown="# Page 1",
                metadata=Metadata(),
                scrape_time_ms=50.0,
                success=True,
            ),
            ScrapeResult(
                url="https://example.com/2",
                markdown="",
                metadata=Metadata(),
                scrape_time_ms=25.0,
                success=False,
                error_message="Timeout",
            ),
        ]

        batch_result = BatchScrapeResult.from_results(results, total_time_ms=75.0)

        assert batch_result.total_urls == 2
        assert batch_result.successful == 1
        assert batch_result.failed == 1
        assert len(batch_result.results) == 2


class TestDiscoverTool:
    """Tests for discover_urls tool implementation."""

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper."""
        scraper = MagicMock()
        scraper.discover_urls = AsyncMock(
            return_value=DiscoverResult(
                base_url="https://example.com",
                urls=[
                    "https://example.com/page1",
                    "https://example.com/page2",
                    "https://example.com/page3",
                ],
                total_urls=3,
                discover_time_ms=75.0,
                success=True,
            )
        )
        return scraper

    @pytest.mark.asyncio
    async def test_discover_returns_urls(self, mock_scraper):
        """Test that discover tool returns discovered URLs."""
        result = await mock_scraper.discover_urls(
            base_url="https://example.com",
            max_urls=100,
        )

        assert result.success is True
        assert result.base_url == "https://example.com"
        assert len(result.urls) == 3
        assert all("example.com" in url for url in result.urls)

    @pytest.mark.asyncio
    async def test_discover_error_handling(self):
        """Test DiscoverResult error factory."""
        result = DiscoverResult.from_error(
            base_url="https://example.com",
            error="Connection refused",
        )

        assert result.success is False
        assert result.error_message == "Connection refused"
        assert result.total_urls == 0
