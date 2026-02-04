"""Search-related Pydantic models."""

from pydantic import BaseModel, Field

from web_search_mcp.models.common import Metadata
from web_search_mcp.models.scrape import ScrapeOptions, ScrapeResult


class SearchQuery(BaseModel):
    """Input parameters for a search query."""

    query: str = Field(..., min_length=1, max_length=2000, description="Search query string")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    language: str | None = Field(default=None, description="Language code (e.g., 'en', 'es')")
    region: str | None = Field(default=None, description="Region code (e.g., 'us', 'uk')")
    safe_search: bool = Field(default=True, description="Enable safe search filtering")
    time_range: str | None = Field(
        default=None, description="Time range filter (provider-specific)"
    )
    location: str | None = Field(default=None, description="Location string (provider-specific)")
    country: str | None = Field(default=None, description="Country code (provider-specific)")
    sources: list[str] | None = Field(default=None, description="Preferred sources list")
    categories: list[str] | None = Field(default=None, description="Category filters")
    include_domains: list[str] | None = Field(
        default=None, description="Domains to include (whitelist)"
    )
    exclude_domains: list[str] | None = Field(
        default=None, description="Domains to exclude (blacklist)"
    )
    search_depth: str | None = Field(
        default=None, description="Search depth (provider-specific)"
    )
    topic: str | None = Field(default=None, description="Topic filter (provider-specific)")
    scrape_options: ScrapeOptions | None = Field(
        default=None, description="Optional scrape options for search results"
    )
    max_scrape_results: int | None = Field(
        default=None, ge=1, le=100, description="Max results to scrape"
    )

    model_config = {"extra": "ignore"}


class SearchResult(BaseModel):
    """A single search result."""

    url: str = Field(..., description="URL of the search result")
    title: str = Field(..., description="Title of the page")
    snippet: str = Field(default="", description="Text snippet/description")
    position: int = Field(..., ge=1, description="Position in search results")
    metadata: Metadata = Field(default_factory=Metadata, description="Additional metadata")
    scrape: ScrapeResult | None = Field(default=None, description="Scraped content (optional)")

    model_config = {"extra": "ignore"}


class SearchResponse(BaseModel):
    """Response from a search operation."""

    query: str = Field(..., description="The original search query")
    results: list[SearchResult] = Field(default_factory=list, description="Search results")
    total_results: int | None = Field(default=None, description="Total results available")
    provider: str = Field(..., description="Search provider used")
    search_time_ms: float = Field(..., ge=0, description="Search time in milliseconds")
    cached: bool = Field(default=False, description="Whether result was from cache")

    model_config = {"extra": "ignore"}

    @property
    def result_count(self) -> int:
        """Return the number of results."""
        return len(self.results)
