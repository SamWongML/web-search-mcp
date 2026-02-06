"""URL mapping tool for MCP."""

import re
from typing import Any
from mcp.server.fastmcp import Context, FastMCP

from web_search_mcp.models.scrape import DiscoverResult


def register(mcp: FastMCP) -> None:
    """Register the map_urls tool with the MCP server."""

    @mcp.tool()
    async def map_urls(
        url: str,
        max_urls: int = 100,
        search: str | None = None,
        same_domain_only: bool = True,
        include_subdomains: bool = False,
        exclude_patterns: list[str] | None = None,
        ctx: Context[Any] = None,  # type: ignore[assignment, type-arg]
    ) -> dict[str, Any]:
        """
        Map URLs on a site with optional filters.

        Args:
            url: Base URL to start mapping
            max_urls: Maximum URLs to discover (1-500, default: 100)
            search: Optional substring filter for URLs
            same_domain_only: Restrict to same domain (default: true)
            include_subdomains: Include subdomains when same_domain_only is true
            exclude_patterns: Regex patterns to exclude

        Returns:
            List of discovered URLs with metadata
        """
        from web_search_mcp.server import AppContext

        max_urls = max(1, min(500, max_urls))

        app_ctx: AppContext = ctx.request_context.lifespan_context

        result: DiscoverResult = await app_ctx.scraper.discover_urls(
            base_url=url,
            max_urls=max_urls,
            same_domain_only=same_domain_only,
            include_subdomains=include_subdomains,
        )

        result_dict = result.model_dump()

        if not result.success:
            return result_dict

        urls = result_dict.get("urls", [])

        if search:
            needle = search.lower()
            urls = [u for u in urls if needle in u.lower()]

        if exclude_patterns:
            compiled = []
            for pattern in exclude_patterns:
                try:
                    compiled.append(re.compile(pattern))
                except re.error:
                    continue

            if compiled:
                filtered = []
                for u in urls:
                    if any(regex.search(u) for regex in compiled):
                        continue
                    filtered.append(u)
                urls = filtered

        result_dict["urls"] = urls
        result_dict["total_urls"] = len(urls)
        return result_dict
