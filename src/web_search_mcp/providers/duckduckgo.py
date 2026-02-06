"""DuckDuckGo search provider using ddgs library."""

import asyncio
import time
from typing import Any

import structlog

from web_search_mcp.exceptions import ProviderAPIError
from web_search_mcp.models.common import Metadata
from web_search_mcp.models.search import SearchResult

logger = structlog.get_logger(__name__)


class DuckDuckGoProvider:
    """
    DuckDuckGo search provider.

    Uses the ddgs library which scrapes DuckDuckGo.
    No API key required, but has rate limits.

    https://github.com/deedy5/ddgs
    """

    def __init__(self) -> None:
        """Initialize the DuckDuckGo provider."""
        pass

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "duckduckgo"

    @property
    def is_configured(self) -> bool:
        """Return True if the provider is configured (always True for DDG)."""
        return True

    async def is_available(self) -> bool:
        """Check if the provider is available for requests."""
        return True

    def _create_ddgs(self) -> Any:
        """Create a DDGS instance. Separated for easier testing."""
        try:
            from ddgs import DDGS
        except ImportError as e:
            raise ProviderAPIError(self.name, 500, f"ddgs library not installed: {e}") from e
        return DDGS()

    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Perform a search using DuckDuckGo.

        Args:
            query: Search query
            max_results: Maximum results to return
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        # Create DDGS instance (can be mocked in tests)
        ddgs = self._create_ddgs()

        # Build search parameters
        include_domains = kwargs.get("include_domains") or []
        exclude_domains = kwargs.get("exclude_domains") or []
        query_string = self._apply_domain_filters(query, include_domains, exclude_domains)

        region = kwargs.get("region", "wt-wt")
        safesearch = "moderate" if kwargs.get("safe_search", True) else "off"
        timelimit = kwargs.get("timelimit")  # d, w, m, y
        if "time_range" in kwargs and kwargs["time_range"]:
            timelimit = self._normalize_time_range(kwargs["time_range"]) or timelimit

        # DDG search is synchronous, run in executor
        def do_search() -> list[dict[str, Any]]:
            results = ddgs.text(
                keywords=query_string,
                region=region,
                safesearch=safesearch,
                timelimit=timelimit,
                max_results=max_results,
            )
            return list(results)

        start_time = time.monotonic()

        try:
            # Run synchronous search in thread pool
            loop = asyncio.get_event_loop()
            raw_results = await loop.run_in_executor(None, do_search)

            elapsed_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "duckduckgo_request",
                query=query[:50],
                result_count=len(raw_results),
                elapsed_ms=elapsed_ms,
            )

            return self._parse_results(raw_results, max_results)

        except Exception as e:
            logger.warning("duckduckgo_error", error=str(e))
            raise ProviderAPIError(self.name, 500, str(e)) from e

    def _parse_results(self, raw_results: list[dict[str, Any]], max_results: int) -> list[SearchResult]:
        """Parse DuckDuckGo results into SearchResult objects."""
        results: list[SearchResult] = []

        for i, item in enumerate(raw_results[:max_results], start=1):
            try:
                result = SearchResult(
                    url=item.get("href", ""),
                    title=item.get("title", ""),
                    snippet=item.get("body", ""),
                    position=i,
                    metadata=Metadata(
                        title=item.get("title"),
                        description=item.get("body"),
                    ),
                )
                results.append(result)
            except Exception as e:
                logger.warning("duckduckgo_parse_error", error=str(e), item=item)
                continue

        return results

    @staticmethod
    def _normalize_time_range(value: str) -> str | None:
        v = value.strip().lower()
        mapping = {
            "d": "d",
            "day": "d",
            "w": "w",
            "week": "w",
            "m": "m",
            "month": "m",
            "y": "y",
            "year": "y",
        }
        return mapping.get(v)

    @staticmethod
    def _apply_domain_filters(query: str, include_domains: list[str], exclude_domains: list[str]) -> str:
        terms = [query]
        if include_domains:
            include_expr = " OR ".join(f"site:{domain}" for domain in include_domains)
            terms.append(f"({include_expr})")
        if exclude_domains:
            terms.extend(f"-site:{domain}" for domain in exclude_domains)
        return " ".join(t for t in terms if t)
