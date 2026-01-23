"""Pydantic models for Web Search MCP."""

from web_search_mcp.models.common import Link, Metadata
from web_search_mcp.models.scrape import (
    BatchScrapeResult,
    DiscoverResult,
    ScrapeOptions,
    ScrapeResult,
)
from web_search_mcp.models.search import SearchQuery, SearchResponse, SearchResult

__all__ = [
    "Link",
    "Metadata",
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    "ScrapeOptions",
    "ScrapeResult",
    "BatchScrapeResult",
    "DiscoverResult",
]
