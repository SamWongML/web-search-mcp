"""Search-related Pydantic models."""

from pydantic import BaseModel, Field

from web_search_mcp.models.common import Metadata


class SearchQuery(BaseModel):
    """Input parameters for a search query."""

    query: str = Field(..., min_length=1, max_length=2000, description="Search query string")
    max_results: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    language: str | None = Field(default=None, description="Language code (e.g., 'en', 'es')")
    region: str | None = Field(default=None, description="Region code (e.g., 'us', 'uk')")
    safe_search: bool = Field(default=True, description="Enable safe search filtering")

    model_config = {"extra": "ignore"}


class SearchResult(BaseModel):
    """A single search result."""

    url: str = Field(..., description="URL of the search result")
    title: str = Field(..., description="Title of the page")
    snippet: str = Field(default="", description="Text snippet/description")
    position: int = Field(..., ge=1, description="Position in search results")
    metadata: Metadata = Field(default_factory=Metadata, description="Additional metadata")

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
