"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from web_search_mcp.models.common import Link, Metadata
from web_search_mcp.models.scrape import (
    BatchScrapeResult,
    DiscoverResult,
    ScrapeOptions,
    ScrapeResult,
)
from web_search_mcp.models.search import SearchQuery, SearchResponse, SearchResult


class TestMetadata:
    """Tests for Metadata model."""

    def test_default_metadata(self):
        """Test creating metadata with defaults."""
        metadata = Metadata()
        assert metadata.title is None
        assert metadata.description is None
        assert metadata.keywords == []

    def test_metadata_with_values(self):
        """Test creating metadata with values."""
        metadata = Metadata(
            title="Test Title",
            description="Test description",
            author="Test Author",
            language="en",
            keywords=["test", "example"],
        )
        assert metadata.title == "Test Title"
        assert metadata.description == "Test description"
        assert metadata.author == "Test Author"
        assert metadata.language == "en"
        assert metadata.keywords == ["test", "example"]


class TestLink:
    """Tests for Link model."""

    def test_link_with_url_only(self):
        """Test creating a link with URL only."""
        link = Link(url="https://example.com")
        assert link.url == "https://example.com"
        assert link.title is None
        assert link.text is None

    def test_link_with_all_fields(self):
        """Test creating a link with all fields."""
        link = Link(
            url="https://example.com",
            title="Example",
            text="Click here",
        )
        assert link.url == "https://example.com"
        assert link.title == "Example"
        assert link.text == "Click here"


class TestSearchQuery:
    """Tests for SearchQuery model."""

    def test_valid_search_query(self):
        """Test creating a valid search query."""
        query = SearchQuery(query="python programming")
        assert query.query == "python programming"
        assert query.max_results == 10
        assert query.safe_search is True

    def test_search_query_with_options(self):
        """Test search query with custom options."""
        query = SearchQuery(
            query="python",
            max_results=20,
            language="en",
            region="us",
            safe_search=False,
            time_range="week",
            include_domains=["example.com"],
            exclude_domains=["ads.example.com"],
            search_depth="advanced",
        )
        assert query.max_results == 20
        assert query.language == "en"
        assert query.region == "us"
        assert query.safe_search is False
        assert query.time_range == "week"
        assert query.include_domains == ["example.com"]
        assert query.exclude_domains == ["ads.example.com"]
        assert query.search_depth == "advanced"

    def test_empty_query_raises_error(self):
        """Test that empty query raises validation error."""
        with pytest.raises(ValidationError):
            SearchQuery(query="")

    def test_max_results_bounds(self):
        """Test max_results validation bounds."""
        # Valid bounds
        query = SearchQuery(query="test", max_results=1)
        assert query.max_results == 1

        query = SearchQuery(query="test", max_results=100)
        assert query.max_results == 100

        # Invalid bounds
        with pytest.raises(ValidationError):
            SearchQuery(query="test", max_results=0)

        with pytest.raises(ValidationError):
            SearchQuery(query="test", max_results=101)


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_valid_search_result(self):
        """Test creating a valid search result."""
        result = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="This is an example.",
            position=1,
        )
        assert result.url == "https://example.com"
        assert result.title == "Example"
        assert result.snippet == "This is an example."
        assert result.position == 1
        assert result.metadata is not None

    def test_search_result_with_metadata(self):
        """Test search result with custom metadata."""
        metadata = Metadata(title="Custom Title", language="en")
        result = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="Test",
            position=1,
            metadata=metadata,
        )
        assert result.metadata.title == "Custom Title"
        assert result.metadata.language == "en"

    def test_search_result_with_scrape(self):
        """Test search result with scrape content."""
        scrape = ScrapeResult(
            url="https://example.com",
            markdown="# Example",
            metadata=Metadata(title="Example"),
            scrape_time_ms=10.0,
            success=True,
        )
        result = SearchResult(
            url="https://example.com",
            title="Example",
            snippet="Test",
            position=1,
            scrape=scrape,
        )
        assert result.scrape is not None

    def test_invalid_position(self):
        """Test that position must be >= 1."""
        with pytest.raises(ValidationError):
            SearchResult(
                url="https://example.com",
                title="Test",
                snippet="Test",
                position=0,
            )


class TestSearchResponse:
    """Tests for SearchResponse model."""

    def test_empty_response(self):
        """Test creating an empty search response."""
        response = SearchResponse(
            query="test",
            results=[],
            provider="test_provider",
            search_time_ms=100.5,
        )
        assert response.query == "test"
        assert response.results == []
        assert response.provider == "test_provider"
        assert response.search_time_ms == 100.5
        assert response.result_count == 0

    def test_response_with_results(self):
        """Test response with multiple results."""
        results = [
            SearchResult(url="https://a.com", title="A", snippet="A", position=1),
            SearchResult(url="https://b.com", title="B", snippet="B", position=2),
        ]
        response = SearchResponse(
            query="test",
            results=results,
            provider="test",
            search_time_ms=50.0,
            total_results=100,
        )
        assert response.result_count == 2
        assert response.total_results == 100


class TestScrapeOptions:
    """Tests for ScrapeOptions model."""

    def test_default_options(self):
        """Test default scrape options."""
        options = ScrapeOptions()
        assert options.include_links is True
        assert options.include_images is False
        assert options.include_metadata is True
        assert options.use_browser is True
        assert options.timeout_seconds == 30
        assert options.formats is None
        assert options.only_main_content is None

    def test_custom_options(self):
        """Test custom scrape options."""
        options = ScrapeOptions(
            include_links=False,
            include_images=True,
            timeout_seconds=60,
            use_browser=False,
            formats=["markdown", "text"],
            only_main_content=False,
            include_tags=["main"],
            exclude_tags=[".ads"],
            max_length=1000,
        )
        assert options.include_links is False
        assert options.include_images is True
        assert options.timeout_seconds == 60
        assert options.use_browser is False
        assert options.formats == ["markdown", "text"]
        assert options.only_main_content is False
        assert options.include_tags == ["main"]
        assert options.exclude_tags == [".ads"]
        assert options.max_length == 1000

    def test_apply_defaults(self):
        """Test applying default settings to scrape options."""
        from web_search_mcp.config import settings

        options = ScrapeOptions()
        applied = options.apply_defaults()

        assert applied.formats == settings.get_default_scrape_formats()
        assert applied.only_main_content == settings.default_only_main_content

    def test_apply_defaults_noop(self):
        """Test apply_defaults returns same instance when no changes needed."""
        options = ScrapeOptions(formats=["markdown"], only_main_content=False)
        applied = options.apply_defaults()

        assert applied is options


class TestScrapeResult:
    """Tests for ScrapeResult model."""

    def test_successful_scrape(self):
        """Test successful scrape result."""
        result = ScrapeResult(
            url="https://example.com",
            markdown="# Hello World",
            metadata=Metadata(title="Hello"),
            scrape_time_ms=150.5,
            success=True,
        )
        assert result.success is True
        assert result.error_message is None
        assert result.markdown == "# Hello World"

    def test_failed_scrape(self):
        """Test failed scrape result."""
        result = ScrapeResult(
            url="https://example.com",
            markdown="",
            metadata=Metadata(),
            scrape_time_ms=50.0,
            success=False,
            error_message="Connection timeout",
        )
        assert result.success is False
        assert result.error_message == "Connection timeout"

    def test_from_error_factory(self):
        """Test ScrapeResult.from_error factory method."""
        result = ScrapeResult.from_error(
            url="https://example.com",
            error="Network error",
            scrape_time_ms=25.0,
        )
        assert result.success is False
        assert result.error_message == "Network error"
        assert result.url == "https://example.com"
        assert result.scrape_time_ms == 25.0


class TestBatchScrapeResult:
    """Tests for BatchScrapeResult model."""

    def test_from_results_factory(self):
        """Test BatchScrapeResult.from_results factory method."""
        results = [
            ScrapeResult(
                url="https://a.com",
                markdown="# A",
                metadata=Metadata(),
                scrape_time_ms=100,
                success=True,
            ),
            ScrapeResult(
                url="https://b.com",
                markdown="",
                metadata=Metadata(),
                scrape_time_ms=50,
                success=False,
                error_message="Failed",
            ),
            ScrapeResult(
                url="https://c.com",
                markdown="# C",
                metadata=Metadata(),
                scrape_time_ms=80,
                success=True,
            ),
        ]

        batch = BatchScrapeResult.from_results(results, total_time_ms=500.0)

        assert batch.total_urls == 3
        assert batch.successful == 2
        assert batch.failed == 1
        assert batch.total_time_ms == 500.0
        assert len(batch.results) == 3


class TestDiscoverResult:
    """Tests for DiscoverResult model."""

    def test_successful_discover(self):
        """Test successful URL discovery."""
        result = DiscoverResult(
            base_url="https://example.com",
            urls=["https://example.com/a", "https://example.com/b"],
            total_urls=2,
            discover_time_ms=200.0,
            success=True,
        )
        assert result.success is True
        assert result.total_urls == 2
        assert len(result.urls) == 2

    def test_from_error_factory(self):
        """Test DiscoverResult.from_error factory method."""
        result = DiscoverResult.from_error(
            base_url="https://example.com",
            error="Connection refused",
            discover_time_ms=10.0,
        )
        assert result.success is False
        assert result.error_message == "Connection refused"
        assert result.urls == []
        assert result.total_urls == 0
