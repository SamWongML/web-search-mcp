"""Tool registration for the MCP server."""

from mcp.server.fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    """
    Register all tools with the MCP server.

    This function imports and registers all tool modules.

    Args:
        mcp: FastMCP server instance
    """
    # Import tool modules to trigger registration
    from web_search_mcp.tools import batch_scrape, discover, scrape, search

    # Register each tool module
    search.register(mcp)
    scrape.register(mcp)
    batch_scrape.register(mcp)
    discover.register(mcp)
