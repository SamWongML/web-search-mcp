"""Google Custom Search (Programmable Search) provider."""

import time
from typing import Any

import httpx
import structlog

from web_search_mcp.exceptions import (
    ProviderAPIError,
    ProviderRateLimitError,
)
from web_search_mcp.models.common import Metadata
from web_search_mcp.models.search import SearchResult

logger = structlog.get_logger(__name__)

GOOGLE_CSE_BASE_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleCSEProvider:
    """
    Google Custom Search (Programmable Search Engine) provider.

    Provides official Google search results through the Custom Search API.
    Free tier: 100 queries/day.

    https://developers.google.com/custom-search/v1/overview
    """

    def __init__(
        self,
        api_key: str | None = None,
        cx: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the Google CSE provider.

        Args:
            api_key: Google API key
            cx: Custom Search Engine ID
            http_client: Shared HTTP client (optional)
        """
        self._api_key = api_key
        self._cx = cx
        self._http_client = http_client
        self._owns_client = http_client is None

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "google_cse"

    @property
    def is_configured(self) -> bool:
        """Return True if the provider is configured."""
        return bool(self._api_key and self._cx)

    async def is_available(self) -> bool:
        """Check if the provider is available for requests."""
        return self.is_configured

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Perform a search using Google Custom Search API.

        Args:
            query: Search query
            max_results: Maximum results to return (max 10 per request)
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        if not self.is_configured:
            raise ProviderAPIError(self.name, 401, "API key or CX not configured")

        client = await self._get_client()
        should_close = self._owns_client and self._http_client is None

        try:
            # Google CSE returns max 10 results per request
            num = min(max_results, 10)

            params = {
                "q": query,
                "key": self._api_key,
                "cx": self._cx,
                "num": num,
            }

            # Add optional parameters
            if "language" in kwargs:
                params["lr"] = f"lang_{kwargs['language']}"
            if "region" in kwargs:
                params["gl"] = kwargs["region"]
            if kwargs.get("safe_search", True):
                params["safe"] = "active"

            start_time = time.monotonic()
            response = await client.get(GOOGLE_CSE_BASE_URL, params=params)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "google_cse_request",
                query=query[:50],
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )

            if response.status_code == 429:
                raise ProviderRateLimitError(self.name)

            if response.status_code == 403:
                data = response.json() if response.content else {}
                error = data.get("error", {})
                if "Daily Limit Exceeded" in str(error):
                    raise ProviderRateLimitError(self.name)
                raise ProviderAPIError(
                    self.name, 403, error.get("message", "Forbidden")
                )

            if response.status_code != 200:
                data = response.json() if response.content else {}
                error = data.get("error", {})
                raise ProviderAPIError(
                    self.name,
                    response.status_code,
                    error.get("message", response.text[:200]),
                )

            data = response.json()
            return self._parse_results(data, max_results)

        finally:
            if should_close and isinstance(client, httpx.AsyncClient):
                await client.aclose()

    def _parse_results(self, data: dict, max_results: int) -> list[SearchResult]:
        """Parse Google CSE response into SearchResult objects."""
        results: list[SearchResult] = []

        items = data.get("items", [])

        for i, item in enumerate(items[:max_results], start=1):
            try:
                # Extract metadata from pagemap if available
                pagemap = item.get("pagemap", {})
                metatags = pagemap.get("metatags", [{}])[0] if pagemap.get("metatags") else {}

                result = SearchResult(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    position=i,
                    metadata=Metadata(
                        title=item.get("title"),
                        description=item.get("snippet"),
                        site_name=item.get("displayLink"),
                        author=metatags.get("author"),
                    ),
                )
                results.append(result)
            except Exception as e:
                logger.warning("google_cse_parse_error", error=str(e), item=item)
                continue

        return results
