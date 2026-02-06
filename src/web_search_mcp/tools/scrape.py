"""URL scraping tool for MCP."""

from typing import Any
from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.models.scrape import ScrapeOptions, ScrapeResult


def register(mcp: FastMCP) -> None:
    """Register the scrape_url tool with the MCP server."""

    @mcp.tool()
    async def scrape_url(
        url: str,
        include_links: bool = True,
        include_images: bool = False,
        use_browser: bool = True,
        formats: list[str] | str | None = None,
        only_main_content: bool | None = None,
        include_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        wait_for_selector: str | None = None,
        max_length: int | None = None,
        max_age_seconds: int | None = None,
        ctx: Context[Any] = None,  # type: ignore[assignment, type-arg]
    ) -> dict[str, Any]:
        """
        Scrape a single URL and return AI-friendly markdown content.

        Extracts the main content from a web page and converts it to clean markdown,
        suitable for LLM processing.

        Args:
            url: URL to scrape (required)
            include_links: Extract and include links from the page (default: true)
            include_images: Extract and include images from the page (default: false)
            use_browser: Use browser-based scraping for JavaScript-heavy sites (default: true)
            formats: Output formats as a LIST (e.g., ["markdown"] or ["markdown", "html"]).
                     Valid: "markdown", "text", "html", "raw_html". Single string also accepted.
            only_main_content: Remove non-main content elements (default: true)
            include_tags: CSS selectors to force-include
            exclude_tags: CSS selectors to exclude
            wait_for_selector: CSS selector to wait for before scraping
            max_length: Max characters for markdown/text outputs
            max_age_seconds: Max cache age (seconds) for cached responses

        Returns:
            Scraped content as markdown with metadata, links, and images
        """
        from web_search_mcp.server import AppContext

        # Get app context
        app_ctx: AppContext = ctx.request_context.lifespan_context

        # Create options
        options = ScrapeOptions(
            include_links=include_links,
            include_images=include_images,
            use_browser=use_browser,
            formats=formats,
            only_main_content=only_main_content,
            include_tags=include_tags or [],
            exclude_tags=exclude_tags or [],
            wait_for_selector=wait_for_selector,
            max_length=max_length,
            max_age_seconds=max_age_seconds,
        )
        options = options.apply_defaults()

        cache_key_params = {
            "include_links": options.include_links,
            "include_images": options.include_images,
            "use_browser": options.use_browser,
            "formats": options.formats or [],
            "only_main_content": options.only_main_content,
            "include_tags": options.include_tags,
            "exclude_tags": options.exclude_tags,
            "wait_for_selector": options.wait_for_selector,
            "max_length": options.max_length,
        }

        # Check cache first
        cached = await app_ctx.cache.get_scrape(
            url,
            max_age_seconds=max_age_seconds,
            **cache_key_params,
        )
        if cached:
            cached["cached"] = True
            return cached

        # Perform scrape
        result: ScrapeResult = await app_ctx.scraper.scrape(url=url, options=options)

        # Convert to dict
        result_dict = result.model_dump()

        # Cache successful results
        if result.success:
            await app_ctx.cache.set_scrape(url, result_dict, **cache_key_params)

        return result_dict
