"""
FastMCP server with all tools registered.

Configured for stateless HTTP mode for multi-client support.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import structlog
from mcp.server.fastmcp import FastMCP

from web_search_mcp.config import settings
from web_search_mcp.providers.registry import ProviderRegistry
from web_search_mcp.scrapers.base import Scraper
from web_search_mcp.tools import register_all_tools
from web_search_mcp.utils.cache import ResponseCache
from web_search_mcp.utils.rate_limiter import MultiProviderRateLimiter

logger = structlog.get_logger(__name__)


@dataclass
class AppContext:
    """Shared application resources available to all tools."""

    http_client: httpx.AsyncClient
    provider_registry: ProviderRegistry
    scraper: Scraper
    rate_limiter: MultiProviderRateLimiter
    cache: ResponseCache


def create_providers(http_client: httpx.AsyncClient) -> list:
    """
    Create search provider instances based on configuration.

    Args:
        http_client: Shared HTTP client

    Returns:
        List of configured search providers
    """
    from web_search_mcp.providers.brave import BraveProvider
    from web_search_mcp.providers.duckduckgo import DuckDuckGoProvider
    from web_search_mcp.providers.google_cse import GoogleCSEProvider
    from web_search_mcp.providers.serpapi import SerpAPIProvider

    providers = []

    # Add providers in priority order
    # SerpAPI first (best quality)
    providers.append(
        SerpAPIProvider(
            api_key=settings.serpapi_key,
            http_client=http_client,
        )
    )

    # Google Custom Search second
    providers.append(
        GoogleCSEProvider(
            api_key=settings.google_api_key,
            cx=settings.google_cx,
            http_client=http_client,
        )
    )

    # Brave third
    providers.append(
        BraveProvider(
            api_key=settings.brave_api_key,
            http_client=http_client,
        )
    )

    # DuckDuckGo last (always available, no API key)
    providers.append(DuckDuckGoProvider())

    return providers


async def create_scraper() -> Scraper:
    """
    Create a web scraper instance.

    Returns:
        Configured scraper instance
    """
    if settings.use_browser_scraper:
        try:
            from web_search_mcp.scrapers.crawl4ai_scraper import Crawl4AIScraper

            scraper = Crawl4AIScraper(
                timeout_seconds=settings.scrape_timeout_seconds,
                max_concurrent=settings.max_concurrent_scrapes,
            )
            logger.info("using_crawl4ai_scraper")
            return scraper
        except ImportError:
            logger.warning("crawl4ai_not_available_falling_back_to_trafilatura")

    # Fallback to trafilatura
    from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper

    logger.info("using_trafilatura_scraper")
    return TrafilaturaScraper(
        timeout_seconds=settings.scrape_timeout_seconds,
    )


@asynccontextmanager
async def app_lifespan(_server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manage application lifecycle.

    Initialize expensive resources once, share across all requests.
    """
    logger.info(
        "starting_mcp_server",
        server_name="Web Search MCP",
        debug=settings.debug,
    )

    # HTTP client with connection pooling
    http_client = httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        ),
        timeout=httpx.Timeout(
            connect=5.0,
            read=settings.request_timeout,
            write=10.0,
            pool=5.0,
        ),
        http2=True,
        follow_redirects=True,
    )

    # Search providers with fallback chain
    providers = create_providers(http_client)
    registry = ProviderRegistry(providers)

    logger.info(
        "providers_initialized",
        available=registry.available_providers,
    )

    # Web scraper
    scraper = await create_scraper()

    # Rate limiter per provider
    rate_limiter = MultiProviderRateLimiter(settings)

    # Response cache
    cache = ResponseCache(
        ttl_seconds=settings.cache_ttl_seconds,
        max_size=settings.cache_max_size,
        enabled=settings.cache_enabled,
    )

    try:
        yield AppContext(
            http_client=http_client,
            provider_registry=registry,
            scraper=scraper,
            rate_limiter=rate_limiter,
            cache=cache,
        )
    finally:
        logger.info("shutting_down_mcp_server")
        await http_client.aclose()
        await scraper.close()
        await cache.close()


# Create FastMCP server
# stateless_http=True allows multiple concurrent clients
# json_response=True for structured responses
mcp = FastMCP(
    "Web Search MCP",
    lifespan=app_lifespan,
    stateless_http=True,
    json_response=True,
)

register_all_tools(mcp)
