"""URL scraping tool for MCP."""

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
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """
        Scrape a single URL and return AI-friendly markdown content.

        Extracts the main content from a web page and converts it to clean markdown,
        suitable for LLM processing.

        Args:
            url: URL to scrape (required)
            include_links: Extract and include links from the page (default: true)
            include_images: Extract and include images from the page (default: false)
            use_browser: Use browser-based scraping for JavaScript-heavy sites (default: true)

        Returns:
            Scraped content as markdown with metadata, links, and images
        """
        from web_search_mcp.server import AppContext

        # Get app context
        app_ctx: AppContext = ctx.request_context.lifespan_context

        # Check cache first
        cached = await app_ctx.cache.get_scrape(url)
        if cached:
            cached["cached"] = True
            return cached

        # Create options
        options = ScrapeOptions(
            include_links=include_links,
            include_images=include_images,
            use_browser=use_browser,
        )

        # Perform scrape
        result: ScrapeResult = await app_ctx.scraper.scrape(url=url, options=options)

        # Convert to dict
        result_dict = result.model_dump()

        # Cache successful results
        if result.success:
            await app_ctx.cache.set_scrape(url, result_dict)

        return result_dict
