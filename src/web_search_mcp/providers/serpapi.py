"""SerpAPI search provider."""

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

SERPAPI_BASE_URL = "https://serpapi.com/search"


class SerpAPIProvider:
    """
    SerpAPI search provider.

    SerpAPI provides structured Google search results with CAPTCHA handling
    and proxy rotation. Free tier: 250 searches/month.

    https://serpapi.com/
    """

    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the SerpAPI provider.

        Args:
            api_key: SerpAPI API key
            http_client: Shared HTTP client (optional)
        """
        self._api_key = api_key
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "serpapi"

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
        Perform a search using SerpAPI.

        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Additional SerpAPI parameters

        Returns:
            List of search results
        """
        if not self.is_configured:
            raise ProviderAPIError(self.name, 401, "API key not configured")

        client = await self._get_client()
        should_close = self._owns_client and self._http_client is None

        try:
            params = {
                "q": query,
                "api_key": self._api_key,
                "engine": kwargs.get("engine", "google"),
                "num": min(max_results, 100),
                "output": "json",
            }

            # Add optional parameters
            if "language" in kwargs:
                params["hl"] = kwargs["language"]
            if "region" in kwargs:
                params["gl"] = kwargs["region"]
            if kwargs.get("safe_search", True):
                params["safe"] = "active"

            start_time = time.monotonic()
            response = await client.get(SERPAPI_BASE_URL, params=params)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "serpapi_request",
                query=query[:50],
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            if response.status_code == 429:
                raise ProviderRateLimitError(self.name)

            if response.status_code != 200:
                data = response.json() if response.content else {}
                error_msg = data.get("error", response.text[:200])
                raise ProviderAPIError(self.name, response.status_code, error_msg)

            data = response.json()
            return self._parse_results(data, max_results)

        finally:
            if should_close and isinstance(client, httpx.AsyncClient):
                await client.aclose()

    def _parse_results(self, data: dict, max_results: int) -> list[SearchResult]:
        """Parse SerpAPI response into SearchResult objects."""
        results: list[SearchResult] = []

        organic_results = data.get("organic_results", [])

        for item in organic_results[:max_results]:
            try:
                result = SearchResult(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    position=item.get("position", len(results) + 1),
                    metadata=Metadata(
                        title=item.get("title"),
                        description=item.get("snippet"),
                        site_name=item.get("source"),
                    ),
                )
                results.append(result)
            except Exception as e:
                logger.warning("serpapi_parse_error", error=str(e), item=item)
                continue

        return results
