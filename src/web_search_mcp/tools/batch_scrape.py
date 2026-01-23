"""Batch scraping tool for MCP."""

from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.models.scrape import BatchScrapeResult, ScrapeOptions


def register(mcp: FastMCP) -> None:
    """Register the batch_scrape tool with the MCP server."""

    @mcp.tool()
    async def batch_scrape(
        urls: list[str],
        max_concurrent: int = 5,
        include_links: bool = True,
        include_images: bool = False,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """
        Scrape multiple URLs concurrently and return AI-friendly markdown content.

        Efficiently scrapes multiple URLs in parallel, returning markdown content
        for each. Failed URLs are included in the response with error details.

        Args:
            urls: List of URLs to scrape (required, max 50)
            max_concurrent: Maximum concurrent scrapes (1-10, default: 5)
            include_links: Extract links from pages (default: true)
            include_images: Extract images from pages (default: false)

        Returns:
            Batch result with individual scrape results, success/failure counts
        """
        import time

        from web_search_mcp.server import AppContext

        # Validate inputs
        if len(urls) > 50:
            return {
                "success": False,
                "error": "Maximum 50 URLs allowed per batch request",
                "total_urls": len(urls),
            }

        if len(urls) == 0:
            return {
                "success": False,
                "error": "At least one URL is required",
                "total_urls": 0,
            }

        max_concurrent = max(1, min(10, max_concurrent))

        start_time = time.monotonic()

        # Get app context
        app_ctx: AppContext = ctx.request_context.lifespan_context

        # Create options
        options = ScrapeOptions(
            include_links=include_links,
            include_images=include_images,
        )

        # Perform batch scrape
        results = await app_ctx.scraper.scrape_batch(
            urls=urls,
            options=options,
            max_concurrent=max_concurrent,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Build response
        batch_result = BatchScrapeResult.from_results(results, elapsed_ms)

        return batch_result.model_dump()
