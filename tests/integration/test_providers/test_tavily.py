"""Integration tests for Tavily Search provider."""

import pytest
import respx
from httpx import Response

from web_search_mcp.exceptions import ProviderAPIError, ProviderRateLimitError
from web_search_mcp.providers.tavily import TavilyProvider


class TestTavilyProvider:
    """Tests for Tavily provider with mocked HTTP."""

    @pytest.fixture
    def provider(self, mock_settings):
        """Tavily provider instance."""
        return TavilyProvider(api_key=mock_settings.tavily_api_key)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_success(self, provider, sample_tavily_response):
        """Test successful search with Tavily."""
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=sample_tavily_response)
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
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json={"results": []})
        )

        results = await provider.search("nonexistent", max_results=10)
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_no_results_key(self, provider):
        """Test handling when results key is missing."""
        respx.post("https://api.tavily.com/search").mock(return_value=Response(200, json={}))

        results = await provider.search("nonexistent", max_results=10)
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_rate_limit(self, provider):
        """Test handling of rate limit error."""
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(429, json={"detail": "Rate limit exceeded"})
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_quota_exceeded(self, provider):
        """Test handling of quota exceeded (403)."""
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(
                403,
                json={"detail": "Monthly quota exceeded"},
            )
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_forbidden_error(self, provider):
        """Test handling of forbidden error (not quota related)."""
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(
                403,
                json={"detail": "Access denied"},
            )
        )

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.search("python", max_results=10)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_invalid_api_key(self, provider):
        """Test handling of invalid API key."""
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(401, json={"detail": "Invalid API key"})
        )

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.search("python", max_results=10)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_is_configured_with_api_key(self, provider):
        """Test configuration check with API key."""
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_is_not_configured_without_api_key(self):
        """Test not configured without API key."""
        provider = TavilyProvider(api_key=None)
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.name == "tavily"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_with_optional_params(self, provider, sample_tavily_response):
        """Test search with optional parameters."""
        route = respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json=sample_tavily_response)
        )

        await provider.search(
            "python news",
            max_results=5,
            topic="news",
            search_depth="advanced",
            time_range="week",
        )

        # Verify the request was made with correct parameters
        assert route.called
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["query"] == "python news"
        assert body["max_results"] == 5
        assert body["topic"] == "news"
        assert body["search_depth"] == "advanced"
        assert body["time_range"] == "week"
