"""URL discovery tool for MCP."""

from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.models.scrape import DiscoverResult


def register(mcp: FastMCP) -> None:
    """Register the discover_urls tool with the MCP server."""

    @mcp.tool()
    async def discover_urls(
        url: str,
        max_urls: int = 100,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """
        Discover all URLs on a website starting from a base URL.

        Crawls a website and returns all discovered URLs. Useful for site mapping
        and finding content to scrape.

        Args:
            url: Base URL to start discovery (required)
            max_urls: Maximum number of URLs to discover (1-500, default: 100)

        Returns:
            List of discovered URLs with metadata
        """
        from web_search_mcp.server import AppContext

        # Validate inputs
        max_urls = max(1, min(500, max_urls))

        # Get app context
        app_ctx: AppContext = ctx.request_context.lifespan_context

        # Perform URL discovery
        result: DiscoverResult = await app_ctx.scraper.discover_urls(
            base_url=url,
            max_urls=max_urls,
        )

        return result.model_dump()
