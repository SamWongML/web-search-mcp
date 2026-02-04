"""Unit tests for custom exceptions."""

from web_search_mcp import exceptions


def test_provider_errors():
    err = exceptions.ProviderNotConfiguredError("serpapi")
    assert "serpapi" in str(err)

    err = exceptions.ProviderRateLimitError("brave", retry_after=10)
    assert err.retry_after == 10
    assert "retry after 10" in str(err)

    err = exceptions.ProviderAPIError("tavily", 403, "Forbidden")
    assert err.status_code == 403
    assert "API error 403" in str(err)


def test_scraper_errors():
    err = exceptions.ScraperTimeoutError("https://example.com", 5)
    assert err.timeout_seconds == 5
    assert "timed out" in str(err)

    err = exceptions.ScraperConnectionError("https://example.com", "boom")
    assert "Connection failed" in str(err)

    err = exceptions.ScraperContentError("https://example.com", "bad html")
    assert "Content extraction failed" in str(err)


def test_validation_and_cache_errors():
    err = exceptions.InvalidURLError("not a url")
    assert err.url == "not a url"
    assert "Invalid URL format" in str(err)

    err = exceptions.CacheConnectionError("redis", "no route")
    assert err.backend == "redis"
    assert "Failed to connect" in str(err)
