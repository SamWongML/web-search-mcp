"""Base protocol for search providers."""

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from web_search_mcp.models.search import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    """
    Protocol for search providers.

    All search providers must implement this interface.
    """

    @property
    def name(self) -> str:
        """Return the provider name."""
        ...

    @property
    def is_configured(self) -> bool:
        """Return True if the provider is properly configured."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Perform a search query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return
            **kwargs: Additional provider-specific options

        Returns:
            List of search results

        Raises:
            ProviderError: If the search fails
        """
        ...

    async def is_available(self) -> bool:
        """
        Check if the provider is available for requests.

        This checks both configuration and rate limits.

        Returns:
            True if the provider can accept requests
        """
        ...
