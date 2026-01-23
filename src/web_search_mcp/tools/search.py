"""Web search tool for MCP."""

from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.models.search import SearchResponse


def register(mcp: FastMCP) -> None:
    """Register the web_search tool with the MCP server."""

    @mcp.tool()
    async def web_search(
        query: str,
        max_results: int = 10,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """
        Search the web and return results with links, titles, and metadata.

        Uses multiple search providers with automatic fallback:
        1. SerpAPI (if configured)
        2. Google Custom Search (if configured)
        3. Brave Search (if configured)
        4. DuckDuckGo (always available)

        Args:
            query: Search query string (required)
            max_results: Maximum number of results to return (1-100, default: 10)

        Returns:
            Search results with URLs, titles, snippets, and metadata
        """
        from web_search_mcp.server import AppContext

        # Get app context from lifespan
        app_ctx: AppContext = ctx.request_context.lifespan_context

        # Check cache first
        cached = await app_ctx.cache.get_search(query, max_results)
        if cached:
            cached["cached"] = True
            return cached

        # Perform search
        response: SearchResponse = await app_ctx.provider_registry.search(
            query=query,
            max_results=max_results,
        )

        # Convert to dict for response
        result = response.model_dump()

        # Cache the result
        await app_ctx.cache.set_search(query, max_results, result)

        return result
