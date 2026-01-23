"""Integration tests for provider registry."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from web_search_mcp.exceptions import (
    AllProvidersExhaustedError,
    ProviderAPIError,
    ProviderRateLimitError,
)
from web_search_mcp.providers.registry import ProviderRegistry


class TestProviderRegistry:
    """Tests for provider registry with fallback logic."""

    @pytest.fixture
    def mock_serpapi(self):
        """Create mock SerpAPI provider."""
        provider = MagicMock()
        provider.name = "serpapi"
        provider.is_configured = True
        provider.is_available = AsyncMock(return_value=True)
        provider.search = AsyncMock()
        return provider

    @pytest.fixture
    def mock_duckduckgo(self):
        """Create mock DuckDuckGo provider."""
        provider = MagicMock()
        provider.name = "duckduckgo"
        provider.is_configured = True
        provider.is_available = AsyncMock(return_value=True)
        provider.search = AsyncMock()
        return provider

    @pytest.mark.asyncio
    async def test_uses_first_available_provider(self, mock_serpapi, mock_duckduckgo):
        """Test that registry uses first available provider."""
        from web_search_mcp.models.search import SearchResult

        mock_serpapi.search.return_value = [
            SearchResult(
                url="https://example.com",
                title="Test",
                snippet="Test snippet",
                position=1,
            )
        ]

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        response = await registry.search("test query")

        assert response.provider == "serpapi"
        assert len(response.results) == 1
        mock_serpapi.search.assert_called_once()
        mock_duckduckgo.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_error(self, mock_serpapi, mock_duckduckgo):
        """Test fallback when primary provider fails."""
        from web_search_mcp.models.search import SearchResult

        mock_serpapi.search.side_effect = ProviderRateLimitError("serpapi")
        mock_duckduckgo.search.return_value = [
            SearchResult(
                url="https://ddg.com",
                title="DDG Result",
                snippet="From DuckDuckGo",
                position=1,
            )
        ]

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        response = await registry.search("test query")

        assert response.provider == "duckduckgo"
        assert len(response.results) == 1

    @pytest.mark.asyncio
    async def test_raises_when_all_exhausted(self, mock_serpapi, mock_duckduckgo):
        """Test error when all providers are exhausted."""
        mock_serpapi.search.side_effect = ProviderRateLimitError("serpapi")
        mock_duckduckgo.search.side_effect = ProviderAPIError("duckduckgo", 500, "Error")

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])

        with pytest.raises(AllProvidersExhaustedError):
            await registry.search("test")

    @pytest.mark.asyncio
    async def test_skips_unconfigured_providers(self, mock_serpapi, mock_duckduckgo):
        """Test that unconfigured providers are skipped."""
        from web_search_mcp.models.search import SearchResult

        mock_serpapi.is_configured = False
        mock_duckduckgo.search.return_value = [
            SearchResult(
                url="https://ddg.com",
                title="Result",
                snippet="Snippet",
                position=1,
            )
        ]

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        response = await registry.search("test")

        assert response.provider == "duckduckgo"
        mock_serpapi.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_unavailable_providers(self, mock_serpapi, mock_duckduckgo):
        """Test that unavailable providers are skipped."""
        from web_search_mcp.models.search import SearchResult

        mock_serpapi.is_available = AsyncMock(return_value=False)
        mock_duckduckgo.search.return_value = [
            SearchResult(
                url="https://ddg.com",
                title="Result",
                snippet="Snippet",
                position=1,
            )
        ]

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        response = await registry.search("test")

        assert response.provider == "duckduckgo"
        mock_serpapi.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_preferred_provider(self, mock_serpapi, mock_duckduckgo):
        """Test that preferred provider is tried first."""
        from web_search_mcp.models.search import SearchResult

        mock_duckduckgo.search.return_value = [
            SearchResult(
                url="https://ddg.com",
                title="Result",
                snippet="Snippet",
                position=1,
            )
        ]

        # SerpAPI is first in list, but DDG is preferred
        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        response = await registry.search("test", preferred_provider="duckduckgo")

        assert response.provider == "duckduckgo"
        mock_serpapi.search.assert_not_called()

    def test_available_providers(self, mock_serpapi, mock_duckduckgo):
        """Test available_providers property."""
        mock_serpapi.is_configured = True
        mock_duckduckgo.is_configured = True

        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])

        assert "serpapi" in registry.available_providers
        assert "duckduckgo" in registry.available_providers

    def test_get_provider(self, mock_serpapi, mock_duckduckgo):
        """Test get_provider method."""
        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])

        assert registry.get_provider("serpapi") == mock_serpapi
        assert registry.get_provider("duckduckgo") == mock_duckduckgo
        assert registry.get_provider("nonexistent") is None

    def test_get_status(self, mock_serpapi, mock_duckduckgo):
        """Test get_status method."""
        registry = ProviderRegistry([mock_serpapi, mock_duckduckgo])
        status = registry.get_status()

        assert "providers" in status
        assert "available_count" in status
        assert len(status["providers"]) == 2

    @pytest.mark.asyncio
    async def test_empty_registry(self):
        """Test error with empty registry."""
        registry = ProviderRegistry([])

        with pytest.raises(AllProvidersExhaustedError):
            await registry.search("test")
