"""Tavily Search API provider."""

import time
from typing import Any

import httpx
import structlog

from web_search_mcp.config import settings
from web_search_mcp.exceptions import (
    ProviderAPIError,
    ProviderRateLimitError,
)
from web_search_mcp.models.common import Metadata
from web_search_mcp.models.search import SearchResult

logger = structlog.get_logger(__name__)

TAVILY_BASE_URL = "https://api.tavily.com/search"


class TavilyProvider:
    """
    Tavily Search API provider.

    Provides high-quality AI-optimized search results.
    Free tier: 1,000 API credits/month.

    https://docs.tavily.com/documentation/api-reference/endpoint/search
    """

    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the Tavily provider.

        Args:
            api_key: Tavily API key (starts with 'tvly-')
            http_client: Shared HTTP client (optional)
        """
        self._api_key = api_key
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "tavily"

    @property
    def is_configured(self) -> bool:
        """Return True if the provider is configured."""
        return bool(self._api_key)

    async def is_available(self) -> bool:
        """Check if the provider is available for requests."""
        return self.is_configured

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(
            timeout=30.0,
            verify=settings.get_ssl_context(),
        )

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Perform a search using Tavily Search API.

        Args:
            query: Search query
            max_results: Maximum results to return (max 20 per request)
            **kwargs: Additional parameters (topic, search_depth, etc.)

        Returns:
            List of search results
        """
        if not self.is_configured:
            raise ProviderAPIError(self.name, 401, "API key not configured")

        client = await self._get_client()
        should_close = self._owns_client and self._http_client is None

        try:
            # Tavily supports max 20 results per request
            num = min(max_results, 20)

            payload: dict[str, Any] = {
                "query": query,
                "max_results": num,
                "search_depth": kwargs.get("search_depth", "basic"),
            }

            # Add optional parameters
            if "topic" in kwargs:
                payload["topic"] = kwargs["topic"]
            if "time_range" in kwargs:
                payload["time_range"] = kwargs["time_range"]
            if "include_domains" in kwargs:
                payload["include_domains"] = kwargs["include_domains"]
            if "exclude_domains" in kwargs:
                payload["exclude_domains"] = kwargs["exclude_domains"]

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            start_time = time.monotonic()
            response = await client.post(
                TAVILY_BASE_URL,
                json=payload,
                headers=headers,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "tavily_request",
                query=query[:50],
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            if response.status_code == 429:
                raise ProviderRateLimitError(self.name)

            if response.status_code == 401:
                raise ProviderAPIError(self.name, 401, "Invalid API key")

            if response.status_code == 403:
                data = response.json() if response.content else {}
                error_msg = data.get("detail", "Forbidden - quota may be exceeded")
                # Treat quota exceeded as rate limit
                if "quota" in error_msg.lower() or "limit" in error_msg.lower():
                    raise ProviderRateLimitError(self.name)
                raise ProviderAPIError(self.name, 403, error_msg)

            if response.status_code != 200:
                data = response.json() if response.content else {}
                error_msg = data.get("detail", response.text[:200])
                raise ProviderAPIError(
                    self.name,
                    response.status_code,
                    error_msg,
                )

            data = response.json()
            return self._parse_results(data, max_results)

        finally:
            if should_close and isinstance(client, httpx.AsyncClient):
                await client.aclose()

    def _parse_results(self, data: dict[str, Any], max_results: int) -> list[SearchResult]:
        """Parse Tavily response into SearchResult objects."""
        results: list[SearchResult] = []

        items = data.get("results", [])

        for i, item in enumerate(items[:max_results], start=1):
            try:
                result = SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    position=i,
                    metadata=Metadata(
                        title=item.get("title"),
                        description=item.get("content"),
                        # Tavily doesn't provide site_name directly, extract from URL
                        site_name=self._extract_domain(item.get("url", "")),
                    ),
                )
                results.append(result)
            except Exception as e:
                logger.warning("tavily_parse_error", error=str(e), item=item)
                continue

        return results

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        """Extract domain from URL for site_name."""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            return parsed.netloc or None
        except Exception:
            return None
