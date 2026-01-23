"""Trafilatura-based web scraper (lightweight, no browser)."""

import asyncio
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from web_search_mcp.exceptions import ScraperContentError
from web_search_mcp.models.common import Image, Link, Metadata
from web_search_mcp.models.scrape import DiscoverResult, ScrapeOptions, ScrapeResult
from web_search_mcp.utils.markdown import clean_markdown

logger = structlog.get_logger(__name__)


class TrafilaturaScraper:
    """
    Trafilatura-based web scraper.

    A lightweight scraper that uses trafilatura for content extraction.
    Does not require a browser, suitable for static content.

    https://github.com/adbar/trafilatura
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the trafilatura scraper.

        Args:
            timeout_seconds: Request timeout
            http_client: Shared HTTP client (optional)
        """
        self._timeout = timeout_seconds
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the scraper name."""
        return "trafilatura"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(
            timeout=float(self._timeout),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WebSearchMCP/1.0)",
            },
        )

    async def scrape(
        self,
        url: str,
        options: ScrapeOptions | None = None,
    ) -> ScrapeResult:
        """
        Scrape a single URL using trafilatura.

        Args:
            url: URL to scrape
            options: Scraping options

        Returns:
            ScrapeResult with markdown content
        """
        options = options or ScrapeOptions()
        start_time = time.monotonic()

        try:
            # Fetch HTML
            client = await self._get_client()
            should_close = self._owns_client and self._http_client is None

            try:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
            except httpx.HTTPStatusError as e:
                return ScrapeResult.from_error(
                    url, f"HTTP {e.response.status_code}", (time.monotonic() - start_time) * 1000
                )
            except httpx.RequestError as e:
                return ScrapeResult.from_error(
                    url, f"Request failed: {e}", (time.monotonic() - start_time) * 1000
                )
            finally:
                if should_close:
                    await client.aclose()

            # Extract content using trafilatura
            markdown, metadata = await self._extract_content(html, url, options)

            # Extract links if requested
            links: list[Link] = []
            if options.include_links:
                links = await self._extract_links(html, url)

            # Extract images if requested
            images: list[Image] = []
            if options.include_images:
                images = await self._extract_images(html, url)

            elapsed_ms = (time.monotonic() - start_time) * 1000

            return ScrapeResult(
                url=url,
                markdown=markdown,
                metadata=metadata,
                links=links,
                images=images,
                scrape_time_ms=elapsed_ms,
                success=True,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.exception("scrape_error", url=url, error=str(e))
            return ScrapeResult.from_error(url, str(e), elapsed_ms)

    async def _extract_content(
        self, html: str, url: str, options: ScrapeOptions
    ) -> tuple[str, Metadata]:
        """Extract content from HTML using trafilatura."""
        try:
            import trafilatura
        except ImportError as e:
            raise ScraperContentError(url, "trafilatura library not installed") from e

        def do_extract() -> tuple[str | None, dict[str, Any] | None]:
            # Extract as markdown
            text = trafilatura.extract(
                html,
                output_format="markdown",
                include_links=options.include_links,
                include_images=options.include_images,
                include_comments=False,
                include_tables=True,
                with_metadata=True,
            )

            # Extract metadata separately
            metadata = trafilatura.extract_metadata(html)

            # Convert metadata to dict - handle both dataclass and legacy __dict__
            meta_dict = None
            if metadata is not None:
                try:
                    # Try dataclass asdict first (trafilatura 2.0+)
                    from dataclasses import asdict
                    meta_dict = asdict(metadata)
                except (TypeError, ImportError):
                    # Fall back to __dict__ for older versions
                    if hasattr(metadata, "__dict__"):
                        meta_dict = metadata.__dict__
                    elif hasattr(metadata, "_asdict"):
                        meta_dict = metadata._asdict()

            return text, meta_dict

        # Run in executor (trafilatura is synchronous)
        loop = asyncio.get_event_loop()
        text, meta_dict = await loop.run_in_executor(None, do_extract)

        markdown = clean_markdown(text or "")

        # Build metadata
        metadata = Metadata()
        if meta_dict:
            metadata = Metadata(
                title=meta_dict.get("title"),
                description=meta_dict.get("description"),
                author=meta_dict.get("author"),
                site_name=meta_dict.get("sitename"),
                language=meta_dict.get("language"),
            )

        return markdown, metadata

    async def _extract_links(self, html: str, base_url: str) -> list[Link]:
        """Extract links from HTML."""
        import re

        links: list[Link] = []
        seen_urls: set[str] = set()

        # Simple regex to find links
        pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for href, text in matches:
            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)

            # Skip duplicates and non-http URLs
            if absolute_url in seen_urls:
                continue
            if not absolute_url.startswith(("http://", "https://")):
                continue

            seen_urls.add(absolute_url)
            links.append(Link(url=absolute_url, text=text.strip() or None))

        return links[:100]  # Limit to 100 links

    async def _extract_images(self, html: str, base_url: str) -> list[Image]:
        """Extract images from HTML."""
        import re

        images: list[Image] = []
        seen_urls: set[str] = set()

        # Simple regex to find images
        pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for src, alt in matches:
            # Resolve relative URLs
            absolute_url = urljoin(base_url, src)

            # Skip duplicates and data URLs
            if absolute_url in seen_urls:
                continue
            if absolute_url.startswith("data:"):
                continue

            seen_urls.add(absolute_url)
            images.append(Image(url=absolute_url, alt=alt or None))

        return images[:50]  # Limit to 50 images

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
        import anyio

        results: list[ScrapeResult] = []
        semaphore = anyio.Semaphore(max_concurrent)

        async def scrape_with_semaphore(url: str) -> ScrapeResult:
            async with semaphore:
                return await self.scrape(url, options)

        async with anyio.create_task_group() as tg:
            for url in urls:
                async def do_scrape(u: str) -> None:
                    result = await scrape_with_semaphore(u)
                    results.append(result)

                tg.start_soon(do_scrape, url)

        return results

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
        start_time = time.monotonic()

        try:
            # Fetch the page
            result = await self.scrape(base_url, ScrapeOptions(include_links=True))

            if not result.success:
                return DiscoverResult.from_error(
                    base_url, result.error_message or "Scrape failed"
                )

            # Extract URLs from the same domain
            base_domain = urlparse(base_url).netloc
            discovered: list[str] = []

            for link in result.links:
                link_domain = urlparse(link.url).netloc
                if link_domain == base_domain and link.url not in discovered:
                    discovered.append(link.url)
                    if len(discovered) >= max_urls:
                        break

            elapsed_ms = (time.monotonic() - start_time) * 1000

            return DiscoverResult(
                base_url=base_url,
                urls=discovered,
                total_urls=len(discovered),
                discover_time_ms=elapsed_ms,
                success=True,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return DiscoverResult.from_error(base_url, str(e), elapsed_ms)

    async def close(self) -> None:
        """Close the scraper and release resources."""
        # Nothing to clean up for trafilatura
        pass
