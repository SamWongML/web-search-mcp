"""Integration tests for cache functionality.

Tests the cache in realistic scenarios including:
- Cache hit/miss behavior
- TTL expiration
- LRU eviction
- Concurrent access
- Integration with search and scrape tools
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from web_search_mcp.models.common import Metadata
from web_search_mcp.models.scrape import ScrapeResult
from web_search_mcp.models.search import SearchResponse, SearchResult
from web_search_mcp.utils.cache import LRUCache, ResponseCache


class TestCacheHitMiss:
    """Test cache hit and miss scenarios."""

    @pytest.mark.asyncio
    async def test_search_cache_hit_returns_cached_value(self):
        """Verify cache returns stored value on hit."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        original_response = {
            "query": "python tutorial",
            "results": [{"title": "Learn Python", "url": "https://example.com"}],
            "provider": "duckduckgo",
        }

        await cache.set_search("python tutorial", 10, original_response)
        cached = await cache.get_search("python tutorial", 10)

        assert cached is not None
        assert cached == original_response
        assert cached["query"] == "python tutorial"

    @pytest.mark.asyncio
    async def test_search_cache_miss_returns_none(self):
        """Verify cache returns None on miss."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        cached = await cache.get_search("nonexistent query", 10)
        assert cached is None

    @pytest.mark.asyncio
    async def test_different_params_create_different_cache_entries(self):
        """Verify different parameters create separate cache entries."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response_10 = {"results": [{"id": i} for i in range(10)]}
        response_20 = {"results": [{"id": i} for i in range(20)]}

        await cache.set_search("python", 10, response_10)
        await cache.set_search("python", 20, response_20)

        cached_10 = await cache.get_search("python", 10)
        cached_20 = await cache.get_search("python", 20)

        assert cached_10 is not None
        assert cached_20 is not None
        assert len(cached_10["results"]) == 10
        assert len(cached_20["results"]) == 20


class TestCacheTTL:
    """Test TTL (time-to-live) expiration."""

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self):
        """Verify entries expire after TTL seconds."""
        cache = ResponseCache(ttl_seconds=1, max_size=100, enabled=True)

        response = {"data": "test"}
        await cache.set_search("query", 10, response)

        # Should exist immediately
        assert await cache.get_search("query", 10) is not None

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired now
        assert await cache.get_search("query", 10) is None

    @pytest.mark.asyncio
    async def test_lru_cache_ttl_expiration(self):
        """Test LRUCache TTL directly."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=0.5)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        await asyncio.sleep(0.6)
        assert await cache.get("key1") is None


class TestCacheLRUEviction:
    """Test LRU eviction when cache is full."""

    @pytest.mark.asyncio
    async def test_lru_evicts_oldest_when_full(self):
        """Verify oldest entries are evicted when cache reaches max size."""
        cache: LRUCache[str] = LRUCache(max_size=3, ttl_seconds=None)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Cache is now full
        assert cache.size == 3

        # Adding new entry should evict key1 (oldest)
        await cache.set("key4", "value4")

        assert cache.size == 3
        assert await cache.get("key1") is None  # Evicted
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self):
        """Verify accessing an entry moves it to end (most recently used)."""
        cache: LRUCache[str] = LRUCache(max_size=3, ttl_seconds=None)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Access key1, making it most recently used
        await cache.get("key1")

        # Add new entry - should evict key2 (now oldest)
        await cache.set("key4", "value4")

        assert await cache.get("key1") == "value1"  # Still present
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_response_cache_eviction(self):
        """Test ResponseCache eviction behavior."""
        cache = ResponseCache(ttl_seconds=3600, max_size=2, enabled=True)

        await cache.set_search("query1", 10, {"id": 1})
        await cache.set_search("query2", 10, {"id": 2})
        await cache.set_search("query3", 10, {"id": 3})

        # query1 should be evicted
        assert await cache.get_search("query1", 10) is None
        assert await cache.get_search("query2", 10) is not None
        assert await cache.get_search("query3", 10) is not None


class TestCacheConcurrency:
    """Test cache behavior under concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Verify cache handles concurrent access correctly."""
        cache: LRUCache[int] = LRUCache(max_size=100, ttl_seconds=None)

        async def writer(key: str, value: int):
            await cache.set(key, value)
            await asyncio.sleep(0.01)

        async def reader(key: str) -> int | None:
            await asyncio.sleep(0.005)
            return await cache.get(key)

        # Run multiple concurrent operations
        tasks = []
        for i in range(20):
            tasks.append(writer(f"key{i}", i))
            tasks.append(reader(f"key{i}"))

        await asyncio.gather(*tasks)

        # All keys should be present
        for i in range(20):
            result = await cache.get(f"key{i}")
            assert result == i

    @pytest.mark.asyncio
    async def test_concurrent_cleanup(self):
        """Test cleanup_expired under concurrent access."""
        cache: LRUCache[str] = LRUCache(max_size=100, ttl_seconds=0.1)

        # Add entries
        for i in range(10):
            await cache.set(f"key{i}", f"value{i}")

        await asyncio.sleep(0.15)

        # Run cleanup concurrently with reads
        async def cleanup():
            return await cache.cleanup_expired()

        async def reader():
            for i in range(10):
                await cache.get(f"key{i}")

        results = await asyncio.gather(cleanup(), reader())
        removed = results[0]

        assert removed == 10
        assert cache.size == 0


class TestCacheDisabled:
    """Test cache behavior when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_cache_never_stores(self):
        """Verify disabled cache doesn't store values."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=False)

        await cache.set_search("query", 10, {"data": "test"})
        assert await cache.get_search("query", 10) is None
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_disabled_cache_scrape(self):
        """Verify disabled cache doesn't store scrape results."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=False)

        await cache.set_scrape("https://example.com", {"markdown": "test"})
        assert await cache.get_scrape("https://example.com") is None


class TestCacheKeyGeneration:
    """Test cache key generation consistency."""

    @pytest.mark.asyncio
    async def test_case_insensitive_queries(self):
        """Verify queries are case-insensitive."""
        cache = ResponseCache(enabled=True)

        await cache.set_search("Python Tutorial", 10, {"id": 1})

        # All case variations should hit the same cache entry
        assert await cache.get_search("python tutorial", 10) is not None
        assert await cache.get_search("PYTHON TUTORIAL", 10) is not None
        assert await cache.get_search("Python tutorial", 10) is not None

    @pytest.mark.asyncio
    async def test_whitespace_normalized(self):
        """Verify whitespace is normalized in queries."""
        cache = ResponseCache(enabled=True)

        await cache.set_search("  python  ", 10, {"id": 1})

        assert await cache.get_search("python", 10) is not None
        assert await cache.get_search("  python  ", 10) is not None

    @pytest.mark.asyncio
    async def test_url_case_insensitive(self):
        """Verify URLs are case-insensitive for scrape cache."""
        cache = ResponseCache(enabled=True)

        await cache.set_scrape("https://EXAMPLE.COM/Path", {"content": "test"})

        assert await cache.get_scrape("https://example.com/path") is not None


class TestCacheToolIntegration:
    """Test cache integration with tool-like behavior."""

    @pytest.mark.asyncio
    async def test_search_tool_cache_flow(self):
        """Simulate the cache flow in web_search tool."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        # Simulate first request (cache miss)
        query = "python programming"
        max_results = 10

        cached = await cache.get_search(query, max_results)
        assert cached is None  # Cache miss

        # Simulate search response
        response = {
            "query": query,
            "results": [
                {"title": "Python.org", "url": "https://python.org", "position": 1}
            ],
            "provider": "duckduckgo",
            "search_time_ms": 150.0,
        }

        await cache.set_search(query, max_results, response)

        # Simulate second request (cache hit)
        cached = await cache.get_search(query, max_results)
        assert cached is not None
        assert cached["query"] == query
        assert cached["provider"] == "duckduckgo"

        # Verify we can add the "cached" flag like the tool does
        cached["cached"] = True
        assert cached["cached"] is True

    @pytest.mark.asyncio
    async def test_scrape_tool_cache_flow(self):
        """Simulate the cache flow in scrape_url tool."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        url = "https://example.com/article"

        # First request (cache miss)
        cached = await cache.get_scrape(url)
        assert cached is None

        # Simulate successful scrape
        result = {
            "url": url,
            "markdown": "# Article Title\n\nContent here...",
            "metadata": {"title": "Article Title"},
            "success": True,
            "scrape_time_ms": 200.0,
        }

        await cache.set_scrape(url, result)

        # Second request (cache hit)
        cached = await cache.get_scrape(url)
        assert cached is not None
        assert cached["markdown"] == "# Article Title\n\nContent here..."

    @pytest.mark.asyncio
    async def test_failed_scrape_not_cached(self):
        """Verify that the tool's behavior of not caching failures is correct.

        The scrape_url tool only caches successful scrapes.
        This test verifies cache behavior matches that expectation.
        """
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        # A failed result should not be cached by the tool
        # (the tool checks result.success before caching)
        failed_result = {
            "url": "https://example.com/404",
            "markdown": "",
            "success": False,
            "error_message": "404 Not Found",
        }

        # Simulate the tool's conditional caching
        if failed_result.get("success", False):
            await cache.set_scrape(failed_result["url"], failed_result)

        # Should not be cached
        assert await cache.get_scrape("https://example.com/404") is None


class TestCacheCleanup:
    """Test cache cleanup and resource management."""

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self):
        """Verify clear() removes all entries."""
        cache = ResponseCache(enabled=True)

        await cache.set_search("query1", 10, {"id": 1})
        await cache.set_search("query2", 10, {"id": 2})
        await cache.set_scrape("https://example.com", {"id": 3})

        assert cache.size == 3

        await cache.clear()

        assert cache.size == 0
        assert await cache.get_search("query1", 10) is None
        assert await cache.get_scrape("https://example.com") is None

    @pytest.mark.asyncio
    async def test_close_clears_cache(self):
        """Verify close() releases resources."""
        cache = ResponseCache(enabled=True)

        await cache.set_search("query", 10, {"id": 1})
        assert cache.size == 1

        await cache.close()

        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_lru_cleanup_expired(self):
        """Test LRUCache cleanup_expired method."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=0.1)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        assert cache.size == 3

        await asyncio.sleep(0.15)

        removed = await cache.cleanup_expired()
        assert removed == 3
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_cleanup_with_no_ttl(self):
        """Verify cleanup does nothing when TTL is not set."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=None)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        removed = await cache.cleanup_expired()
        assert removed == 0
        assert cache.size == 2
