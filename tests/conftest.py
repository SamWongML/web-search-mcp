"""Shared test fixtures for the Web Search MCP test suite."""

from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
import respx

# ─── Pytest Configuration ────────────────────────────────────────


def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (no I/O)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "docker: Docker container tests")
    config.addinivalue_line("markers", "slow: Slow tests (skipped by default)")


# ─── Async Backend ───────────────────────────────────────────────


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the async backend."""
    return "asyncio"


# ─── Settings Fixtures ───────────────────────────────────────────


@pytest.fixture
def test_settings():
    """Test settings with no API keys."""
    from web_search_mcp.config import Settings

    return Settings(
        debug=True,
        log_level="DEBUG",
        serpapi_key=None,
        tavily_api_key=None,
        brave_api_key=None,
        cache_enabled=False,
    )


@pytest.fixture
def mock_settings():
    """Settings with mock API keys for testing."""
    from web_search_mcp.config import Settings

    return Settings(
        debug=True,
        serpapi_key="test-serpapi-key",
        tavily_api_key="tvly-test-key",
        brave_api_key="test-brave-key",
        jina_api_key="test-jina-key",
        cache_enabled=False,
    )


# ─── HTTP Client Fixtures ────────────────────────────────────────


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client for tests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def mock_http():
    """RESPX mock router for HTTP mocking."""
    with respx.mock(assert_all_called=False) as router:
        yield router


# ─── Provider Fixtures ───────────────────────────────────────────


@pytest.fixture
def duckduckgo_provider():
    """DuckDuckGo provider (no API key needed)."""
    from web_search_mcp.providers.duckduckgo import DuckDuckGoProvider

    return DuckDuckGoProvider()


@pytest.fixture
def serpapi_provider(mock_settings):
    """SerpAPI provider with mock settings."""
    from web_search_mcp.providers.serpapi import SerpAPIProvider

    return SerpAPIProvider(api_key=mock_settings.serpapi_key)


@pytest.fixture
def tavily_provider(mock_settings):
    """Tavily provider with mock settings."""
    from web_search_mcp.providers.tavily import TavilyProvider

    return TavilyProvider(api_key=mock_settings.tavily_api_key)


@pytest.fixture
def brave_provider(mock_settings):
    """Brave provider with mock settings."""
    from web_search_mcp.providers.brave import BraveProvider

    return BraveProvider(api_key=mock_settings.brave_api_key)


@pytest.fixture
def mock_provider_registry(duckduckgo_provider):
    """Provider registry with only DuckDuckGo."""
    from web_search_mcp.providers.registry import ProviderRegistry

    return ProviderRegistry([duckduckgo_provider])


# ─── Scraper Fixtures ────────────────────────────────────────────


@pytest.fixture
def trafilatura_scraper():
    """Trafilatura scraper instance."""
    from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper

    return TrafilaturaScraper(timeout_seconds=10)


# ─── Sample Data Fixtures ────────────────────────────────────────


@pytest.fixture
def sample_search_results() -> list[dict]:
    """Sample search results for mocking."""
    return [
        {
            "title": "Python Documentation",
            "href": "https://docs.python.org/",
            "body": "Official Python documentation and tutorials.",
        },
        {
            "title": "Real Python",
            "href": "https://realpython.com/",
            "body": "Python tutorials, articles, and resources.",
        },
        {
            "title": "Python Package Index",
            "href": "https://pypi.org/",
            "body": "The Python Package Index (PyPI) is a repository of software.",
        },
    ]


@pytest.fixture
def sample_serpapi_response() -> dict:
    """Sample SerpAPI response for mocking."""
    return {
        "search_metadata": {
            "status": "Success",
            "total_time_taken": 0.45,
        },
        "organic_results": [
            {
                "position": 1,
                "title": "Python.org",
                "link": "https://www.python.org/",
                "snippet": "The official home of the Python Programming Language.",
                "source": "Python.org",
            },
            {
                "position": 2,
                "title": "Python Tutorial",
                "link": "https://docs.python.org/3/tutorial/",
                "snippet": "Python is an easy to learn, powerful programming language.",
                "source": "Python Docs",
            },
        ],
    }


@pytest.fixture
def sample_tavily_response() -> dict:
    """Sample Tavily response for mocking."""
    return {
        "query": "python programming",
        "results": [
            {
                "title": "Python.org",
                "url": "https://www.python.org/",
                "content": "The official home of Python.",
                "score": 0.95,
            },
            {
                "title": "Python Tutorial",
                "url": "https://docs.python.org/",
                "content": "Python documentation.",
                "score": 0.90,
            },
        ],
        "response_time": 0.5,
    }


@pytest.fixture
def sample_brave_response() -> dict:
    """Sample Brave Search response for mocking."""
    return {
        "web": {
            "results": [
                {
                    "url": "https://www.python.org/",
                    "title": "Python.org",
                    "description": "The official Python website.",
                    "profile": {"name": "Python.org"},
                },
                {
                    "url": "https://docs.python.org/",
                    "title": "Python Docs",
                    "description": "Python documentation.",
                    "profile": {"name": "Python Docs"},
                },
            ]
        }
    }


@pytest.fixture
def sample_html_content() -> str:
    """Sample HTML for scraping tests."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="description" content="Test page description">
        <title>Test Page Title</title>
    </head>
    <body>
        <h1>Welcome to Test Page</h1>
        <p>This is a test paragraph with some <strong>bold text</strong>.</p>
        <p>Here is a <a href="https://example.com/link1">link to example</a>.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
            <li>Item 3</li>
        </ul>
        <img src="https://example.com/image.jpg" alt="Test image">
        <a href="/relative-link">Relative link</a>
    </body>
    </html>
    """


@pytest.fixture
def expected_markdown() -> str:
    """Expected markdown output from sample HTML."""
    return """# Welcome to Test Page

This is a test paragraph with some **bold text**.

Here is a [link to example](https://example.com/link1).

- Item 1
- Item 2
- Item 3"""
