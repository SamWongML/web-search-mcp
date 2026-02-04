"""Brave Search API provider."""

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

BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveProvider:
    """
    Brave Search API provider.

    Brave Search provides an independent search index with privacy focus.
    Free tier: 2,000 queries/month, 1 query/second.

    https://brave.com/search/api/
    """

    def __init__(
        self,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the Brave Search provider.

        Args:
            api_key: Brave Search API key
            http_client: Shared HTTP client (optional)
        """
        self._api_key = api_key
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "brave"

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
        Perform a search using Brave Search API.

        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        if not self.is_configured:
            raise ProviderAPIError(self.name, 401, "API key not configured")

        client = await self._get_client()
        should_close = self._owns_client and self._http_client is None

        try:
            include_domains = kwargs.get("include_domains") or []
            exclude_domains = kwargs.get("exclude_domains") or []
            query_string = self._apply_domain_filters(query, include_domains, exclude_domains)

            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self._api_key,
            }

            params = {
                "q": query_string,
                "count": min(max_results, 20),  # Brave max is 20
            }

            # Add optional parameters
            if "language" in kwargs:
                params["search_lang"] = kwargs["language"]
            if "region" in kwargs:
                params["country"] = kwargs["region"]
            if "country" in kwargs and "region" not in kwargs:
                params["country"] = kwargs["country"]
            if kwargs.get("safe_search", True):
                params["safesearch"] = "moderate"
            else:
                params["safesearch"] = "off"

            start_time = time.monotonic()
            response = await client.get(
                BRAVE_SEARCH_BASE_URL,
                headers=headers,
                params=params,
            )
            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "brave_request",
                query=query[:50],
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise ProviderRateLimitError(
                    self.name,
                    retry_after=float(retry_after) if retry_after else None,
                )

            if response.status_code != 200:
                raise ProviderAPIError(self.name, response.status_code, response.text[:200])

            data = response.json()
            return self._parse_results(data, max_results)

        finally:
            if should_close and isinstance(client, httpx.AsyncClient):
                await client.aclose()

    @staticmethod
    def _apply_domain_filters(query: str, include_domains: list[str], exclude_domains: list[str]) -> str:
        terms = [query]
        if include_domains:
            include_expr = " OR ".join(f"site:{domain}" for domain in include_domains)
            terms.append(f"({include_expr})")
        if exclude_domains:
            terms.extend(f"-site:{domain}" for domain in exclude_domains)
        return " ".join(t for t in terms if t)

    def _parse_results(self, data: dict, max_results: int) -> list[SearchResult]:
        """Parse Brave Search response into SearchResult objects."""
        results: list[SearchResult] = []

        web_results = data.get("web", {}).get("results", [])

        for i, item in enumerate(web_results[:max_results], start=1):
            try:
                result = SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                    position=i,
                    metadata=Metadata(
                        title=item.get("title"),
                        description=item.get("description"),
                        site_name=item.get("profile", {}).get("name"),
                        favicon=item.get("profile", {}).get("img"),
                        language=item.get("language"),
                    ),
                )
                results.append(result)
            except Exception as e:
                logger.warning("brave_parse_error", error=str(e), item=item)
                continue

        return results
