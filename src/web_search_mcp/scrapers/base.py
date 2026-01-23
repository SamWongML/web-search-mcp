"""Base protocol for web scrapers."""

from abc import abstractmethod
from typing import Protocol, runtime_checkable

from web_search_mcp.models.scrape import DiscoverResult, ScrapeOptions, ScrapeResult


@runtime_checkable
class Scraper(Protocol):
    """
    Protocol for web scrapers.

    All scrapers must implement this interface.
    """

    @property
    def name(self) -> str:
        """Return the scraper name."""
        ...

    @abstractmethod
    async def scrape(
        self,
        url: str,
        options: ScrapeOptions | None = None,
    ) -> ScrapeResult:
        """
        Scrape a single URL and return content as markdown.

        Args:
            url: URL to scrape
            options: Scraping options

        Returns:
            ScrapeResult with markdown content

        Raises:
            ScraperError: If scraping fails
        """
        ...

    @abstractmethod
    async def scrape_batch(
        self,
        urls: list[str],
        options: ScrapeOptions | None = None,
        max_concurrent: int = 5,
    ) -> list[ScrapeResult]:
        """
        Scrape multiple URLs concurrently.

        Args:
            urls: List of URLs to scrape
            options: Scraping options
            max_concurrent: Maximum concurrent scrapes

        Returns:
            List of ScrapeResult objects
        """
        ...

    @abstractmethod
    async def discover_urls(
        self,
        base_url: str,
        max_urls: int = 100,
    ) -> DiscoverResult:
        """
        Discover URLs on a website.

        Args:
            base_url: Base URL to start discovery
            max_urls: Maximum URLs to discover

        Returns:
            DiscoverResult with discovered URLs
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the scraper and release resources."""
        ...
