"""Integration tests for Google Custom Search provider."""

import pytest
import respx
from httpx import Response

from web_search_mcp.exceptions import ProviderAPIError, ProviderRateLimitError
from web_search_mcp.providers.google_cse import GoogleCSEProvider


class TestGoogleCSEProvider:
    """Tests for Google CSE provider with mocked HTTP."""

    @pytest.fixture
    def provider(self, mock_settings):
        """Google CSE provider instance."""
        return GoogleCSEProvider(
            api_key=mock_settings.google_api_key,
            cx=mock_settings.google_cx,
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_success(self, provider, sample_google_cse_response):
        """Test successful search with Google CSE."""
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(200, json=sample_google_cse_response)
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
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(200, json={"items": []})
        )

        results = await provider.search("nonexistent", max_results=10)
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_no_items_key(self, provider):
        """Test handling when items key is missing."""
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(200, json={})
        )

        results = await provider.search("nonexistent", max_results=10)
        assert results == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_rate_limit(self, provider):
        """Test handling of rate limit error."""
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(429, json={"error": {"message": "Rate limit"}})
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_daily_limit(self, provider):
        """Test handling of daily limit exceeded."""
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(
                403,
                json={"error": {"message": "Daily Limit Exceeded"}},
            )
        )

        with pytest.raises(ProviderRateLimitError):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_handles_forbidden_error(self, provider):
        """Test handling of forbidden error (not rate limit)."""
        respx.get("https://www.googleapis.com/customsearch/v1").mock(
            return_value=Response(
                403,
                json={"error": {"message": "Access denied"}},
            )
        )

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.search("python", max_results=10)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_is_configured_with_both_keys(self, provider):
        """Test configuration check with both API key and CX."""
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_is_not_configured_without_api_key(self):
        """Test not configured without API key."""
        provider = GoogleCSEProvider(api_key=None, cx="test-cx")
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_is_not_configured_without_cx(self):
        """Test not configured without CX."""
        provider = GoogleCSEProvider(api_key="test-key", cx=None)
        assert provider.is_configured is False

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.name == "google_cse"
