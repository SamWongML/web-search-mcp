"""Integration tests for Brave Search provider."""

import pytest
import respx
from httpx import Response

from web_search_mcp.exceptions import ProviderAPIError, ProviderRateLimitError
from web_search_mcp.providers.brave import BraveProvider


class TestBraveProvider:
    """Tests for Brave Search provider with mocked HTTP."""

    @pytest.fixture
    def provider(self, mock_settings):
        """Brave provider instance."""
        return BraveProvider(api_key=mock_settings.brave_api_key)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_success(self, provider, sample_brave_response):
        """Test successful search with Brave."""
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(200, json=sample_brave_response)
        )

        results = await provider.search("python programming", max_results=10)

        assert len(results) == 2
        assert results[0].title == "Python.org"
        assert results[0].url == "https://www.python.org/"
        assert results[0].position == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_empty_results(self, provider):
        """Test handling of empty search results."""
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(200, json={"web": {"results": []}})
        )

        results = await provider.search("nonexistent", max_results=10)
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_rate_limit(self, provider):
        """Test handling of rate limit error."""
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(
                429,
                text="Rate limit exceeded",
                headers={"Retry-After": "60"},
            )
        )

        with pytest.raises(ProviderRateLimitError) as exc_info:
            await provider.search("python", max_results=10)

        assert exc_info.value.retry_after == 60.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_api_error(self, provider):
        """Test handling of API errors."""
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(500, text="Internal server error")
        )

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.search("python", max_results=10)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_is_configured_with_key(self, provider):
        """Test configuration check with API key."""
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_is_not_configured_without_key(self):
        """Test not configured without API key."""
        provider = BraveProvider(api_key=None)
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.name == "brave"
