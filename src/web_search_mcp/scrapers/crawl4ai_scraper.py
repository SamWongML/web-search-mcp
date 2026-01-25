"""Crawl4AI-based web scraper (browser-based, handles JavaScript)."""

import time

import structlog

from web_search_mcp.models.common import Image, Link, Metadata
from web_search_mcp.models.scrape import DiscoverResult, ScrapeOptions, ScrapeResult
from web_search_mcp.utils.content_extractor import extract_main_content, extract_metadata
from web_search_mcp.utils.markdown import clean_markdown

logger = structlog.get_logger(__name__)


class Crawl4AIScraper:
    """
    Crawl4AI-based web scraper.

    A high-performance browser-based scraper that handles JavaScript-heavy sites.
    Provides LLM-optimized markdown output.

    https://github.com/unclecode/crawl4ai
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_concurrent: int = 5,
        headless: bool = True,
    ) -> None:
        """
        Initialize the Crawl4AI scraper.

        Args:
            timeout_seconds: Page load timeout
            max_concurrent: Maximum concurrent browser sessions
            headless: Run browser in headless mode
        """
        self._timeout = timeout_seconds
        self._max_concurrent = max_concurrent
        self._headless = headless
        self._crawler = None
        self._initialized = False

    @property
    def name(self) -> str:
        """Return the scraper name."""
        return "crawl4ai"

    async def _ensure_initialized(self) -> None:
        """Ensure the crawler is initialized."""
        if self._initialized:
            return

        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig

            browser_config = BrowserConfig(
                headless=self._headless,
                browser_type="chromium",
                verbose=False,
            )

            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.__aenter__()
            self._initialized = True

            logger.info("crawl4ai_initialized", headless=self._headless)

        except ImportError as e:
            logger.error("crawl4ai_import_error", error=str(e))
            raise
        except Exception as e:
            logger.error("crawl4ai_init_error", error=str(e))
            raise

    async def scrape(
        self,
        url: str,
        options: ScrapeOptions | None = None,
    ) -> ScrapeResult:
        """
        Scrape a single URL using Crawl4AI.

        Args:
            url: URL to scrape
            options: Scraping options

        Returns:
            ScrapeResult with markdown content
        """
        options = options or ScrapeOptions()
        start_time = time.monotonic()

        try:
            await self._ensure_initialized()

            from crawl4ai import CacheMode, CrawlerRunConfig

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=self._timeout * 1000,  # Convert to ms
                wait_until="domcontentloaded",
                word_count_threshold=10,
            )

            # Add wait for selector if specified
            if options.wait_for_selector:
                run_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=self._timeout * 1000,
                    wait_until="domcontentloaded",
                    wait_for=options.wait_for_selector,
                )

            result = await self._crawler.arun(url=url, config=run_config)

            elapsed_ms = (time.monotonic() - start_time) * 1000

            if not result.success:
                return ScrapeResult.from_error(
                    url, result.error_message or "Crawl failed", elapsed_ms
                )

            # Extract main content using trafilatura/readability pipeline
            # This produces Firecrawl-quality clean markdown
            markdown = extract_main_content(
                result.html,
                url=url,
                include_links=options.include_links,
                include_images=options.include_images,
                include_tables=True,
                favor_precision=True,
            )

            # Fall back to Crawl4AI's markdown if extraction fails
            if not markdown or len(markdown.strip()) < 50:
                logger.debug(
                    "content_extractor_fallback",
                    reason="extraction_failed",
                    url=url,
                )
                if hasattr(result, "markdown"):
                    if hasattr(result.markdown, "raw_markdown"):
                        markdown = result.markdown.raw_markdown
                    elif hasattr(result.markdown, "fit_markdown"):
                        markdown = result.markdown.fit_markdown
                    else:
                        markdown = str(result.markdown)
                markdown = clean_markdown(markdown)

            # Build metadata
            metadata = Metadata()
            if hasattr(result, "metadata") and result.metadata:
                metadata = Metadata(
                    title=result.metadata.get("title"),
                    description=result.metadata.get("description"),
                    author=result.metadata.get("author"),
                    language=result.metadata.get("language"),
                )

            # Extract links if requested
            links: list[Link] = []
            if options.include_links and hasattr(result, "links"):
                internal = (
                    result.links.get("internal", []) if isinstance(result.links, dict) else []
                )
                external = (
                    result.links.get("external", []) if isinstance(result.links, dict) else []
                )

                for link_data in internal + external:
                    if isinstance(link_data, dict):
                        links.append(
                            Link(
                                url=link_data.get("href", ""),
                                text=link_data.get("text"),
                            )
                        )
                    elif isinstance(link_data, str):
                        links.append(Link(url=link_data))

            # Extract images if requested
            images: list[Image] = []
            if options.include_images and hasattr(result, "media"):
                media_images = (
                    result.media.get("images", []) if isinstance(result.media, dict) else []
                )
                for img_data in media_images:
                    if isinstance(img_data, dict):
                        images.append(
                            Image(
                                url=img_data.get("src", ""),
                                alt=img_data.get("alt"),
                            )
                        )

            return ScrapeResult(
                url=url,
                markdown=markdown,
                metadata=metadata,
                links=links[:100],
                images=images[:50],
                scrape_time_ms=elapsed_ms,
                success=True,
            )

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.exception("crawl4ai_scrape_error", url=url, error=str(e))
            return ScrapeResult.from_error(url, str(e), elapsed_ms)

    async def scrape_batch(
        self,
        urls: list[str],
        options: ScrapeOptions | None = None,
        max_concurrent: int = 5,
    ) -> list[ScrapeResult]:
        """
        Scrape multiple URLs concurrently using Crawl4AI.

        Args:
            urls: List of URLs to scrape
            options: Scraping options
            max_concurrent: Maximum concurrent scrapes

        Returns:
            List of ScrapeResult objects
        """
        options = options or ScrapeOptions()
        start_time = time.monotonic()

        try:
            await self._ensure_initialized()

            from crawl4ai import CacheMode, CrawlerRunConfig, MemoryAdaptiveDispatcher

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=self._timeout * 1000,
                wait_until="domcontentloaded",
            )

            dispatcher = MemoryAdaptiveDispatcher(
                max_session_permit=max_concurrent,
                memory_threshold_percent=80.0,
                check_interval=1.0,
            )

            raw_results = await self._crawler.arun_many(
                urls=urls,
                config=run_config,
                dispatcher=dispatcher,
            )

            # Convert to ScrapeResult objects
            results: list[ScrapeResult] = []
            for raw_result in raw_results:
                elapsed_ms = (time.monotonic() - start_time) * 1000

                if not raw_result.success:
                    results.append(
                        ScrapeResult.from_error(
                            raw_result.url,
                            raw_result.error_message or "Crawl failed",
                            elapsed_ms,
                        )
                    )
                    continue

                # Extract main content using trafilatura/readability pipeline
                markdown = extract_main_content(
                    raw_result.html,
                    url=raw_result.url,
                    include_links=True,
                    include_images=False,
                    include_tables=True,
                    favor_precision=True,
                )

                # Fall back to Crawl4AI's markdown if extraction fails
                if not markdown or len(markdown.strip()) < 50:
                    if hasattr(raw_result, "markdown"):
                        if hasattr(raw_result.markdown, "raw_markdown"):
                            markdown = raw_result.markdown.raw_markdown
                        else:
                            markdown = str(raw_result.markdown)
                    markdown = clean_markdown(markdown)

                # Build metadata
                metadata = Metadata()
                if hasattr(raw_result, "metadata") and raw_result.metadata:
                    metadata = Metadata(
                        title=raw_result.metadata.get("title"),
                        description=raw_result.metadata.get("description"),
                    )

                results.append(
                    ScrapeResult(
                        url=raw_result.url,
                        markdown=markdown,
                        metadata=metadata,
                        scrape_time_ms=elapsed_ms,
                        success=True,
                    )
                )

            return results

        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.exception("crawl4ai_batch_error", error=str(e))
            # Return error results for all URLs
            return [ScrapeResult.from_error(url, str(e), elapsed_ms) for url in urls]

    async def discover_urls(
        self,
        base_url: str,
        max_urls: int = 100,
    ) -> DiscoverResult:
        """
        Discover URLs on a website using Crawl4AI.

        Args:
            base_url: Base URL to start discovery
            max_urls: Maximum URLs to discover

        Returns:
            DiscoverResult with discovered URLs
        """
        start_time = time.monotonic()

        try:
            # Scrape the base URL with link extraction
            result = await self.scrape(base_url, ScrapeOptions(include_links=True))

            if not result.success:
                return DiscoverResult.from_error(
                    base_url,
                    result.error_message or "Scrape failed",
                    result.scrape_time_ms,
                )

            # Filter URLs to same domain
            from urllib.parse import urlparse

            base_domain = urlparse(base_url).netloc
            discovered: list[str] = []

            for link in result.links:
                try:
                    link_domain = urlparse(link.url).netloc
                    if link_domain == base_domain and link.url not in discovered:
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
        """Close the scraper and release browser resources."""
        if self._crawler and self._initialized:
            try:
                await self._crawler.__aexit__(None, None, None)
                logger.info("crawl4ai_closed")
            except Exception as e:
                logger.warning("crawl4ai_close_error", error=str(e))
            finally:
                self._crawler = None
                self._initialized = False
