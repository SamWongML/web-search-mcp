"""Caching utilities for response caching."""

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Generic, TypeVar

import anyio

T = TypeVar("T")


class LRUCache(Generic[T]):
    """
    Thread-safe LRU cache with TTL support.

    Uses an OrderedDict for O(1) access and LRU eviction.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float | None = None) -> None:
        """
        Initialize the LRU cache.

        Args:
            max_size: Maximum number of items in the cache
            ttl_seconds: Time-to-live for cache entries (None for no expiry)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[T, float]] = OrderedDict()
        self._lock = anyio.Lock()

    def _is_expired(self, timestamp: float) -> bool:
        """Check if an entry has expired."""
        if self.ttl_seconds is None:
            return False
        return time.time() - timestamp > self.ttl_seconds

    async def get(self, key: str) -> T | None:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, timestamp = self._cache[key]

            # Check expiry
            if self._is_expired(timestamp):
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value

    async def set(self, key: str, value: T) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            # Remove if exists to update position
            if key in self._cache:
                del self._cache[key]

            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (value, time.time())

    async def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        if self.ttl_seconds is None:
            return 0

        async with self._lock:
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items() if self._is_expired(timestamp)
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    @property
    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)

    # Synchronous versions for use in non-async contexts
    def get_sync(self, key: str) -> T | None:
        """Synchronous version of get."""
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        if self._is_expired(timestamp):
            del self._cache[key]
            return None

        self._cache.move_to_end(key)
        return value

    def set_sync(self, key: str, value: T) -> None:
        """Synchronous version of set."""
        if key in self._cache:
            del self._cache[key]

        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (value, time.time())


class ResponseCache:
    """
    Response cache for search and scrape results.

    Provides methods to cache and retrieve responses with automatic key generation.
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_size: int = 1000,
        enabled: bool = True,
    ) -> None:
        """
        Initialize the response cache.

        Args:
            ttl_seconds: Time-to-live for cache entries
            max_size: Maximum number of entries
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self._cache: LRUCache[dict[str, Any]] = LRUCache(
            max_size=max_size,
            ttl_seconds=float(ttl_seconds),
        )

    @staticmethod
    def _generate_key(prefix: str, **kwargs: Any) -> str:
        """
        Generate a cache key from prefix and parameters.

        Args:
            prefix: Key prefix (e.g., "search", "scrape")
            **kwargs: Parameters to include in the key

        Returns:
            SHA256 hash of the parameters
        """
        # Normalize list values for stable ordering
        normalized: dict[str, Any] = {}
        for key, value in kwargs.items():
            if isinstance(value, list):
                try:
                    normalized[key] = sorted(value)
                except TypeError:
                    normalized[key] = sorted(str(v) for v in value)
            else:
                normalized[key] = value

        # Sort keys for consistent ordering
        sorted_items = sorted(normalized.items())
        key_string = f"{prefix}:" + json.dumps(sorted_items, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    @staticmethod
    def _wrap_response(response: dict[str, Any]) -> dict[str, Any]:
        return {"_cached_at": time.time(), "data": response}

    @staticmethod
    def _unwrap_response(entry: dict[str, Any]) -> dict[str, Any]:
        if "data" in entry and "_cached_at" in entry:
            return entry["data"]
        return entry

    @staticmethod
    def _is_fresh(entry: dict[str, Any], max_age_seconds: int | None) -> bool:
        if max_age_seconds is None:
            return True
        cached_at = entry.get("_cached_at")
        if cached_at is None:
            return True
        return (time.time() - float(cached_at)) <= max_age_seconds

    async def get_search(
        self,
        query: str,
        max_results: int,
        provider: str | None = None,
        max_age_seconds: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Get cached search results.

        Args:
            query: Search query
            max_results: Maximum results
            provider: Provider name (optional)

        Returns:
            Cached response or None
        """
        if not self.enabled:
            return None

        key = self._generate_key(
            "search",
            query=query.lower().strip(),
            max_results=max_results,
            provider=provider,
            **kwargs,
        )
        entry = await self._cache.get(key)
        if not entry:
            return None
        if not self._is_fresh(entry, max_age_seconds):
            return None
        return self._unwrap_response(entry)

    async def set_search(
        self,
        query: str,
        max_results: int,
        response: dict[str, Any],
        provider: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Cache search results.

        Args:
            query: Search query
            max_results: Maximum results
            response: Response to cache
            provider: Provider name (optional)
        """
        if not self.enabled:
            return

        key = self._generate_key(
            "search",
            query=query.lower().strip(),
            max_results=max_results,
            provider=provider,
            **kwargs,
        )
        await self._cache.set(key, self._wrap_response(response))

    async def get_scrape(
        self,
        url: str,
        max_age_seconds: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Get cached scrape result.

        Args:
            url: URL that was scraped

        Returns:
            Cached response or None
        """
        if not self.enabled:
            return None

        key = self._generate_key("scrape", url=url.lower().strip(), **kwargs)
        entry = await self._cache.get(key)
        if not entry:
            return None
        if not self._is_fresh(entry, max_age_seconds):
            return None
        return self._unwrap_response(entry)

    async def set_scrape(self, url: str, response: dict[str, Any], **kwargs: Any) -> None:
        """
        Cache scrape result.

        Args:
            url: URL that was scraped
            response: Response to cache
        """
        if not self.enabled:
            return

        key = self._generate_key("scrape", url=url.lower().strip(), **kwargs)
        await self._cache.set(key, self._wrap_response(response))

    async def clear(self) -> None:
        """Clear all cached entries."""
        await self._cache.clear()

    async def close(self) -> None:
        """Close the cache and release resources."""
        await self._cache.clear()

    @property
    def size(self) -> int:
        """Return current cache size."""
        return self._cache.size
