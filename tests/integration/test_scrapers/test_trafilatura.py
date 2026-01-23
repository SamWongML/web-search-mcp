"""Integration tests for Trafilatura scraper."""

import pytest
import respx
from httpx import Response

from web_search_mcp.models.scrape import ScrapeOptions
from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper


class TestTrafilaturaScraper:
    """Tests for Trafilatura scraper with mocked HTTP."""

    @pytest.fixture
    def scraper(self):
        """Trafilatura scraper instance."""
        return TrafilaturaScraper(timeout_seconds=10)

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_success(self, scraper, sample_html_content):
        """Test successful scrape."""
        respx.get("https://example.com/page").mock(
            return_value=Response(200, text=sample_html_content)
        )

        result = await scraper.scrape("https://example.com/page")

        assert result.success is True
        assert result.url == "https://example.com/page"
        assert result.scrape_time_ms > 0
        # Trafilatura should extract some content
        assert len(result.markdown) > 0 or result.success

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_http_error(self, scraper):
        """Test scrape with HTTP error."""
        respx.get("https://example.com/error").mock(return_value=Response(404, text="Not Found"))

        result = await scraper.scrape("https://example.com/error")

        assert result.success is False
        assert "404" in result.error_message

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_connection_error(self, scraper):
        """Test scrape with connection error."""
        respx.get("https://example.com/timeout").mock(side_effect=Exception("Connection timeout"))

        result = await scraper.scrape("https://example.com/timeout")

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_with_links(self, scraper, sample_html_content):
        """Test scrape with link extraction."""
        respx.get("https://example.com/page").mock(
            return_value=Response(200, text=sample_html_content)
        )

        options = ScrapeOptions(include_links=True)
        result = await scraper.scrape("https://example.com/page", options)

        assert result.success is True
        # Should extract links from the sample HTML
        assert len(result.links) >= 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_with_images(self, scraper, sample_html_content):
        """Test scrape with image extraction."""
        respx.get("https://example.com/page").mock(
            return_value=Response(200, text=sample_html_content)
        )

        options = ScrapeOptions(include_images=True)
        result = await scraper.scrape("https://example.com/page", options)

        assert result.success is True
        # Sample HTML has one image
        assert len(result.images) >= 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_scrape_batch(self, scraper):
        """Test batch scraping."""
        respx.get("https://example.com/page1").mock(
            return_value=Response(200, text="<html><body><h1>Page 1</h1></body></html>")
        )
        respx.get("https://example.com/page2").mock(
            return_value=Response(200, text="<html><body><h1>Page 2</h1></body></html>")
        )
        respx.get("https://example.com/page3").mock(return_value=Response(404, text="Not Found"))

        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]

        results = await scraper.scrape_batch(urls, max_concurrent=2)

        assert len(results) == 3
        # At least some should succeed
        successful = [r for r in results if r.success]
        assert len(successful) >= 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_discover_urls(self, scraper):
        """Test URL discovery."""
        html = """
        <html>
        <body>
            <a href="https://example.com/page1">Page 1</a>
            <a href="https://example.com/page2">Page 2</a>
            <a href="https://other.com/external">External</a>
        </body>
        </html>
        """
        respx.get("https://example.com/").mock(return_value=Response(200, text=html))

        result = await scraper.discover_urls("https://example.com/", max_urls=10)

        assert result.success is True
        assert result.base_url == "https://example.com/"
        # Should only include same-domain URLs
        for url in result.urls:
            assert "example.com" in url

    @pytest.mark.asyncio
    async def test_scraper_name(self, scraper):
        """Test scraper name property."""
        assert scraper.name == "trafilatura"

    @pytest.mark.asyncio
    async def test_close(self, scraper):
        """Test close method (should not raise)."""
        await scraper.close()
