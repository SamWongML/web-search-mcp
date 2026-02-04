"""Jina Reader API-based scraper (cloud-based, high quality)."""

import time

import httpx
import structlog

from web_search_mcp.config import settings
from web_search_mcp.models.common import Metadata
from web_search_mcp.models.scrape import DiscoverResult, ScrapeOptions, ScrapeResult
from web_search_mcp.utils.markdown import clean_markdown, markdown_to_text, truncate_markdown, truncate_text

logger = structlog.get_logger(__name__)

JINA_READER_BASE_URL = "https://r.jina.ai"


class JinaReaderScraper:
    """
    Jina Reader API-based scraper.

    Uses Jina's Reader API to convert web pages to LLM-friendly markdown.
    Free tier: 10M tokens, 20 RPM without API key.

    https://jina.ai/reader/
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: int = 30,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the Jina Reader scraper.

        Args:
            api_key: Jina API key (optional, higher limits)
            timeout_seconds: Request timeout
            http_client: Shared HTTP client (optional)
        """
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the scraper name."""
        return "jina_reader"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(
            timeout=float(self._timeout),
            verify=settings.get_ssl_context(),
        )

    async def scrape(
        self,
        url: str,
        options: ScrapeOptions | None = None,
    ) -> ScrapeResult:
        """
        Scrape a single URL using Jina Reader API.

        Args:
            url: URL to scrape
            options: Scraping options

        Returns:
            ScrapeResult with markdown content
        """
        options = (options or ScrapeOptions()).apply_defaults()
        start_time = time.monotonic()

        client = await self._get_client()
        should_close = self._owns_client and self._http_client is None

        try:
            # Build Jina Reader URL
            jina_url = f"{JINA_READER_BASE_URL}/{url}"

            headers = {
                "Accept": "application/json",
            }

            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            # Add options as headers
            if options.include_links:
                headers["X-With-Links-Summary"] = "true"
            if options.include_images:
                headers["X-With-Images-Summary"] = "true"

            response = await client.get(jina_url, headers=headers)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            if response.status_code != 200:
                return ScrapeResult.from_error(
                    url,
                    f"Jina Reader error: {response.status_code}",
                    elapsed_ms,
                )

            data = response.json()

            if data.get("code") != 200:
                return ScrapeResult.from_error(
                    url,
                    data.get("message", "Unknown error"),
                    elapsed_ms,
                )

            content_data = data.get("data", {})

            formats = {f.strip().lower() for f in (options.formats or []) if f and f.strip()}
            if not formats:
                formats = {"markdown"}

            markdown = clean_markdown(content_data.get("content", ""))
            text: str | None = None
            html_out: str | None = None

            if "text" in formats:
                text = markdown_to_text(markdown)

            if options.max_length:
                if markdown and "markdown" in formats:
                    markdown = truncate_markdown(markdown, options.max_length)
                if text:
                    text = truncate_text(text, options.max_length)

            metadata = Metadata()
            if options.include_metadata:
                metadata = Metadata(
                    title=content_data.get("title"),
                    description=content_data.get("description"),
                )

            return ScrapeResult(
                url=url,
                markdown=markdown if "markdown" in formats else "",
                text=text,
                html=html_out,
                raw_html=None,
                metadata=metadata,
                scrape_time_ms=elapsed_ms,
                success=True,
            )

        except httpx.RequestError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return ScrapeResult.from_error(url, f"Request failed: {e}", elapsed_ms)

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.exception("jina_scrape_error", url=url, error=str(e))
            return ScrapeResult.from_error(url, str(e), elapsed_ms)

        finally:
            if should_close:
                await client.aclose()

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
        same_domain_only: bool = True,
        include_subdomains: bool = False,
    ) -> DiscoverResult:
        """
        Discover URLs on a website.

        Jina Reader doesn't have built-in discovery, so we scrape and extract links.

        Args:
            base_url: Base URL to start discovery
            max_urls: Maximum URLs to discover

        Returns:
            DiscoverResult with discovered URLs
        """
        start_time = time.monotonic()

        try:
            result = await self.scrape(base_url, ScrapeOptions(include_links=True))

            if not result.success:
                return DiscoverResult.from_error(
                    base_url,
                    result.error_message or "Scrape failed",
                    result.scrape_time_ms,
                )

            # Extract URLs from links
            from urllib.parse import urlparse

            base_domain = urlparse(base_url).netloc
            discovered: list[str] = []

            for link in result.links:
                try:
                    link_domain = urlparse(link.url).netloc
                    if same_domain_only:
                        if include_subdomains:
                            is_match = link_domain == base_domain or link_domain.endswith(
                                f".{base_domain}"
                            )
                        else:
                            is_match = link_domain == base_domain
                    else:
                        is_match = True

                    if is_match and link.url not in discovered:
                        discovered.append(link.url)
                        if len(discovered) >= max_urls:
                            break
                except Exception:
                    continue

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
        # Nothing to clean up
        pass
