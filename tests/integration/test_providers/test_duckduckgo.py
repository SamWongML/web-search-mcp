"""Integration tests for DuckDuckGo provider."""

from unittest.mock import MagicMock, patch

import pytest

from web_search_mcp.exceptions import ProviderAPIError
from web_search_mcp.providers.duckduckgo import DuckDuckGoProvider


class TestDuckDuckGoProvider:
    """Tests for DuckDuckGo provider."""

    @pytest.fixture
    def provider(self):
        """DuckDuckGo provider instance."""
        return DuckDuckGoProvider()

    @pytest.mark.asyncio
    async def test_search_success(self, provider, sample_search_results):
        """Test successful search with DuckDuckGo."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = sample_search_results

        with patch.object(provider, "_create_ddgs", return_value=mock_ddgs):
            results = await provider.search("python programming", max_results=10)

            assert len(results) == 3
            assert results[0].title == "Python Documentation"
            assert results[0].url == "https://docs.python.org/"
            assert results[0].position == 1

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self, provider):
        """Test handling of empty search results."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []

        with patch.object(provider, "_create_ddgs", return_value=mock_ddgs):
            results = await provider.search("nonexistent", max_results=10)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_exception(self, provider):
        """Test handling of exceptions."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.side_effect = Exception("Network error")

        with (
            patch.object(provider, "_create_ddgs", return_value=mock_ddgs),
            pytest.raises(ProviderAPIError),
        ):
            await provider.search("python", max_results=10)

    @pytest.mark.asyncio
    async def test_always_configured(self, provider):
        """Test that DuckDuckGo is always configured (no API key needed)."""
        assert provider.is_configured is True

    @pytest.mark.asyncio
    async def test_always_available(self, provider):
        """Test that DuckDuckGo is always available."""
        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_provider_name(self, provider):
        """Test provider name property."""
        assert provider.name == "duckduckgo"

    @pytest.mark.asyncio
    async def test_search_with_options(self, provider):
        """Test search with custom options."""
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "Test", "href": "https://test.com", "body": "Test"}
        ]

        with patch.object(provider, "_create_ddgs", return_value=mock_ddgs):
            await provider.search(
                "python",
                max_results=5,
                region="us-en",
                safe_search=False,
            )

            # Verify text was called with correct parameters
            mock_ddgs.text.assert_called_once()
            call_kwargs = mock_ddgs.text.call_args
            assert call_kwargs[1]["safesearch"] == "off"
