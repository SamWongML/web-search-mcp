"""Provider registry with automatic fallback."""

import time
from typing import Any

import structlog

from web_search_mcp.exceptions import AllProvidersExhaustedError, ProviderError
from web_search_mcp.models.search import SearchResponse
from web_search_mcp.providers.base import SearchProvider

logger = structlog.get_logger(__name__)


class ProviderRegistry:
    """
    Registry that manages multiple search providers with automatic fallback.

    Providers are tried in order until one succeeds. If all providers fail,
    an AllProvidersExhaustedError is raised.
    """

    def __init__(self, providers: list[SearchProvider]) -> None:
        """
        Initialize the registry with a list of providers.

        Args:
            providers: List of search providers in priority order
        """
        self._providers = providers
        self._provider_status: dict[str, dict[str, Any]] = {}

        for provider in providers:
            self._provider_status[provider.name] = {
                "failures": 0,
                "last_failure": None,
                "last_success": None,
            }

    @property
    def providers(self) -> list[SearchProvider]:
        """Return list of registered providers."""
        return self._providers

    @property
    def available_providers(self) -> list[str]:
        """Return names of configured providers."""
        return [p.name for p in self._providers if p.is_configured]

    def _record_success(self, provider_name: str) -> None:
        """Record a successful request."""
        status = self._provider_status.get(provider_name, {})
        status["failures"] = 0
        status["last_success"] = time.time()
        self._provider_status[provider_name] = status

    def _record_failure(self, provider_name: str) -> None:
        """Record a failed request."""
        status = self._provider_status.get(provider_name, {})
        status["failures"] = status.get("failures", 0) + 1
        status["last_failure"] = time.time()
        self._provider_status[provider_name] = status

    def _should_skip_provider(self, provider_name: str) -> bool:
        """
        Check if a provider should be skipped due to recent failures.

        Implements exponential backoff for failing providers.
        """
        status = self._provider_status.get(provider_name, {})
        failures = status.get("failures", 0)
        last_failure = status.get("last_failure")

        if failures == 0 or last_failure is None:
            return False

        # Exponential backoff: 2^failures seconds, max 5 minutes
        backoff_seconds = min(2**failures, 300)
        elapsed = time.time() - last_failure

        return bool(elapsed < backoff_seconds)

    async def search(
        self,
        query: str,
        max_results: int = 10,
        preferred_provider: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """
        Search using available providers with automatic fallback.

        Args:
            query: Search query string
            max_results: Maximum results to return
            preferred_provider: Preferred provider name (optional)
            **kwargs: Additional search options

        Returns:
            SearchResponse with results

        Raises:
            AllProvidersExhaustedError: If all providers fail
        """
        start_time = time.monotonic()
        errors: list[tuple[str, str]] = []

        # Build provider order
        providers_to_try = self._get_provider_order(preferred_provider)

        for provider in providers_to_try:
            if not provider.is_configured:
                logger.debug("provider_not_configured", provider=provider.name)
                continue

            if self._should_skip_provider(provider.name):
                logger.debug("provider_skipped_backoff", provider=provider.name)
                continue

            if not await provider.is_available():
                logger.debug("provider_not_available", provider=provider.name)
                continue

            try:
                logger.info(
                    "searching_with_provider",
                    provider=provider.name,
                    query=query[:50],
                    max_results=max_results,
                )

                results = await provider.search(query, max_results=max_results, **kwargs)
                elapsed_ms = (time.monotonic() - start_time) * 1000

                self._record_success(provider.name)

                logger.info(
                    "search_success",
                    provider=provider.name,
                    result_count=len(results),
                    elapsed_ms=elapsed_ms,
                )

                return SearchResponse(
                    query=query,
                    results=results,
                    total_results=len(results),
                    provider=provider.name,
                    search_time_ms=elapsed_ms,
                )

            except ProviderError as e:
                self._record_failure(provider.name)
                errors.append((provider.name, str(e)))
                logger.warning(
                    "provider_error",
                    provider=provider.name,
                    error=str(e),
                )
                continue

            except Exception as e:
                self._record_failure(provider.name)
                errors.append((provider.name, str(e)))
                logger.exception(
                    "unexpected_provider_error",
                    provider=provider.name,
                    error=str(e),
                )
                continue

        # All providers failed
        elapsed_ms = (time.monotonic() - start_time) * 1000
        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)

        logger.error(
            "all_providers_exhausted",
            query=query[:50],
            errors=error_summary,
            elapsed_ms=elapsed_ms,
        )

        raise AllProvidersExhaustedError(f"All search providers failed. Errors: {error_summary}")

    def _get_provider_order(self, preferred: str | None) -> list[SearchProvider]:
        """Get providers in order, with preferred provider first if specified."""
        if not preferred:
            return self._providers

        # Move preferred provider to front
        ordered: list[SearchProvider] = []
        rest: list[SearchProvider] = []

        for provider in self._providers:
            if provider.name == preferred:
                ordered.insert(0, provider)
            else:
                rest.append(provider)

        return ordered + rest

    def get_provider(self, name: str) -> SearchProvider | None:
        """Get a provider by name."""
        for provider in self._providers:
            if provider.name == name:
                return provider
        return None

    def get_status(self) -> dict[str, Any]:
        """Get status information for all providers."""
        return {
            "providers": [
                {
                    "name": p.name,
                    "configured": p.is_configured,
                    "status": self._provider_status.get(p.name, {}),
                }
                for p in self._providers
            ],
            "available_count": len(self.available_providers),
        }
