"""Integration tests for SerpAPI provider."""

import pytest
import respx
from httpx import Response

from web_search_mcp.exceptions import ProviderAPIError, ProviderRateLimitError
from web_search_mcp.providers.serpapi import SerpAPIProvider


class TestSerpAPIProvider:
    """Tests for SerpAPI provider with mocked HTTP."""

    @pytest.fixture
    def provider(self, mock_settings):
        """SerpAPI provider instance."""
        return SerpAPIProvider(api_key=mock_settings.serpapi_key)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_success(self, provider, sample_serpapi_response):
        """Test successful search with SerpAPI."""
        respx.get("https://serpapi.com/search").mock(
            return_value=Response(200, json=sample_serpapi_response)
        )

        results = await provider.search("python programming", max_results=10)

        assert len(results) == 2
        assert results[0].title == "Python.org"
        assert results[0].url == "https://www.python.org/"
        assert results[0].position == 1
        assert results[1].title == "Python Tutorial"
        assert results[1].position == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_empty_results(self, provider):
        """Test handling of empty search results."""
        respx.get("https://serpapi.com/search").mock(
            return_value=Response(200, json={"organic_results": []})
        )

        results = await provider.search("xyznonexistent123", max_results=10)

        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_rate_limit(self, provider):
        """Test handling of rate limit error."""
        respx.get("https://serpapi.com/search").mock(
            return_value=Response(429, json={"error": "Rate limit exceeded"})
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_api_error(self, provider):
        """Test handling of API errors."""
        respx.get("https://serpapi.com/search").mock(
            return_value=Response(500, json={"error": "Internal server error"})
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
        """Test that provider is not configured without API key."""
        provider = SerpAPIProvider(api_key=None)
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_search_without_api_key_raises_error(self):
        """Test that search without API key raises error."""
        provider = SerpAPIProvider(api_key=None)

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.search("python", max_results=10)

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.name == "serpapi"

    @pytest.mark.asyncio
    async def test_is_available(self, provider):
        """Test is_available method."""
        assert await provider.is_available() is True

        unconfigured = SerpAPIProvider(api_key=None)
        assert await unconfigured.is_available() is False
