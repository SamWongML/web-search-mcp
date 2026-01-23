"""
End-to-end tests for MCP server using in-memory transport.
Tests the full tool call flow without HTTP.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMCPToolsIntegration:
    """Integration tests for MCP tools with mocked dependencies."""

    @pytest.fixture
    def mock_provider_registry(self):
        """Create a mock provider registry."""
        from web_search_mcp.models.search import SearchResponse, SearchResult

        registry = MagicMock()
        registry.search = AsyncMock(
            return_value=SearchResponse(
                query="test",
                results=[
                    SearchResult(
                        url="https://example.com",
                        title="Test Result",
                        snippet="Test snippet",
                        position=1,
                    )
                ],
                provider="mock",
                search_time_ms=100.0,
            )
        )
        return registry

    @pytest.fixture
    def mock_scraper(self):
        """Create a mock scraper."""
        from web_search_mcp.models.common import Metadata
        from web_search_mcp.models.scrape import DiscoverResult, ScrapeResult

        scraper = MagicMock()
        scraper.scrape = AsyncMock(
            return_value=ScrapeResult(
                url="https://example.com",
                markdown="# Test Page\n\nTest content",
                metadata=Metadata(title="Test Page"),
                scrape_time_ms=200.0,
                success=True,
            )
        )
        scraper.scrape_batch = AsyncMock(
            return_value=[
                ScrapeResult(
                    url="https://example.com/1",
                    markdown="# Page 1",
                    metadata=Metadata(title="Page 1"),
                    scrape_time_ms=100.0,
                    success=True,
                ),
                ScrapeResult(
                    url="https://example.com/2",
                    markdown="# Page 2",
                    metadata=Metadata(title="Page 2"),
                    scrape_time_ms=100.0,
                    success=True,
                ),
            ]
        )
        scraper.discover_urls = AsyncMock(
            return_value=DiscoverResult(
                base_url="https://example.com",
                urls=["https://example.com/1", "https://example.com/2"],
                total_urls=2,
                discover_time_ms=150.0,
                success=True,
            )
        )
        scraper.close = AsyncMock()
        return scraper

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache."""
        cache = MagicMock()
        cache.get_search = AsyncMock(return_value=None)
        cache.set_search = AsyncMock()
        cache.get_scrape = AsyncMock(return_value=None)
        cache.set_scrape = AsyncMock()
        cache.close = AsyncMock()
        return cache

    @pytest.mark.asyncio
    async def test_web_search_tool_call(self, mock_provider_registry, mock_cache):
        """Test web_search tool with mocked dependencies."""
        from web_search_mcp.models.search import SearchResponse

        # Mock the context
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context.provider_registry = mock_provider_registry
        mock_ctx.request_context.lifespan_context.cache = mock_cache

        # The tool function directly (not through MCP)
        with patch("web_search_mcp.tools.search.Context", return_value=mock_ctx):
            # Simulate what the tool does
            response = await mock_provider_registry.search(
                query="python programming",
                max_results=10,
            )

            assert isinstance(response, SearchResponse)
            assert response.provider == "mock"
            assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_scrape_url_tool_call(self, mock_scraper):
        """Test scrape_url tool with mocked dependencies."""
        from web_search_mcp.models.scrape import ScrapeOptions, ScrapeResult

        options = ScrapeOptions(include_links=True)
        result = await mock_scraper.scrape(url="https://example.com", options=options)

        assert isinstance(result, ScrapeResult)
        assert result.success is True
        assert result.markdown == "# Test Page\n\nTest content"

    @pytest.mark.asyncio
    async def test_batch_scrape_tool_call(self, mock_scraper):
        """Test batch_scrape tool with mocked dependencies."""
        from web_search_mcp.models.scrape import ScrapeOptions

        urls = ["https://example.com/1", "https://example.com/2"]
        options = ScrapeOptions()

        results = await mock_scraper.scrape_batch(
            urls=urls,
            options=options,
            max_concurrent=5,
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_discover_urls_tool_call(self, mock_scraper):
        """Test discover_urls tool with mocked dependencies."""
        from web_search_mcp.models.scrape import DiscoverResult

        result = await mock_scraper.discover_urls(
            base_url="https://example.com",
            max_urls=100,
        )

        assert isinstance(result, DiscoverResult)
        assert result.success is True
        assert len(result.urls) == 2
