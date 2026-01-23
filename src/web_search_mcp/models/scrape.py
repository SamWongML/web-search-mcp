"""Scraping-related Pydantic models."""

from pydantic import BaseModel, Field

from web_search_mcp.models.common import Image, Link, Metadata


class ScrapeOptions(BaseModel):
    """Options for scraping a URL."""

    include_links: bool = Field(default=True, description="Extract links from the page")
    include_images: bool = Field(default=False, description="Extract images from the page")
    include_metadata: bool = Field(default=True, description="Extract page metadata")
    wait_for_selector: str | None = Field(
        default=None, description="CSS selector to wait for before scraping"
    )
    timeout_seconds: int = Field(default=30, ge=1, le=120, description="Scrape timeout")
    use_browser: bool = Field(default=True, description="Use browser-based scraping")

    model_config = {"extra": "ignore"}


class ScrapeResult(BaseModel):
    """Result of scraping a single URL."""

    url: str = Field(..., description="The scraped URL")
    markdown: str = Field(default="", description="Page content as markdown")
    html: str | None = Field(default=None, description="Raw HTML content")
    metadata: Metadata = Field(default_factory=Metadata, description="Page metadata")
    links: list[Link] = Field(default_factory=list, description="Extracted links")
    images: list[Image] = Field(default_factory=list, description="Extracted images")
    scrape_time_ms: float = Field(..., ge=0, description="Scrape time in milliseconds")
    success: bool = Field(default=True, description="Whether scrape succeeded")
    error_message: str | None = Field(default=None, description="Error message if failed")
    cached: bool = Field(default=False, description="Whether result was from cache")

    model_config = {"extra": "ignore"}

    @classmethod
    def from_error(cls, url: str, error: str, scrape_time_ms: float = 0) -> "ScrapeResult":
        """Create a failed scrape result from an error."""
        return cls(
            url=url,
            markdown="",
            metadata=Metadata(),
            scrape_time_ms=scrape_time_ms,
            success=False,
            error_message=error,
        )


class BatchScrapeResult(BaseModel):
    """Result of scraping multiple URLs."""

    results: list[ScrapeResult] = Field(default_factory=list, description="Individual results")
    total_urls: int = Field(..., ge=0, description="Total URLs requested")
    successful: int = Field(default=0, ge=0, description="Number of successful scrapes")
    failed: int = Field(default=0, ge=0, description="Number of failed scrapes")
    total_time_ms: float = Field(..., ge=0, description="Total time in milliseconds")

    model_config = {"extra": "ignore"}

    @classmethod
    def from_results(cls, results: list[ScrapeResult], total_time_ms: float) -> "BatchScrapeResult":
        """Create a batch result from individual results."""
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        return cls(
            results=results,
            total_urls=len(results),
            successful=successful,
            failed=failed,
            total_time_ms=total_time_ms,
        )


class DiscoverResult(BaseModel):
    """Result of discovering URLs on a website."""

    base_url: str = Field(..., description="The base URL that was crawled")
    urls: list[str] = Field(default_factory=list, description="Discovered URLs")
    total_urls: int = Field(default=0, ge=0, description="Total URLs discovered")
    discover_time_ms: float = Field(..., ge=0, description="Discovery time in milliseconds")
    success: bool = Field(default=True, description="Whether discovery succeeded")
    error_message: str | None = Field(default=None, description="Error message if failed")

    model_config = {"extra": "ignore"}

    @classmethod
    def from_error(cls, base_url: str, error: str, discover_time_ms: float = 0) -> "DiscoverResult":
        """Create a failed discover result from an error."""
        return cls(
            base_url=base_url,
            urls=[],
            total_urls=0,
            discover_time_ms=discover_time_ms,
            success=False,
            error_message=error,
        )
