"""Unit tests for cache utilities."""

import asyncio

import pytest

from web_search_mcp.utils.cache import LRUCache, ResponseCache


class TestLRUCache:
    """Tests for LRUCache."""

    @pytest.mark.asyncio
    async def test_get_set(self):
        """Test basic get/set operations."""
        cache: LRUCache[str] = LRUCache(max_size=10)

        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self):
        """Test that missing key returns None."""
        cache: LRUCache[str] = LRUCache(max_size=10)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_eviction_on_max_size(self):
        """Test that oldest items are evicted at max size."""
        cache: LRUCache[str] = LRUCache(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")  # Should evict key1

        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_lru_order_updated_on_access(self):
        """Test that accessing a key updates its position."""
        cache: LRUCache[str] = LRUCache(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Access key1, making key2 the LRU
        await cache.get("key1")

        # Add key3, should evict key2 (not key1)
        await cache.set("key3", "value3")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is None
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Test that items expire after TTL."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=0.1)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        # Wait for expiry
        await asyncio.sleep(0.15)

        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a key."""
        cache: LRUCache[str] = LRUCache(max_size=10)

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

        deleted = await cache.delete("key1")
        assert deleted is True
        assert await cache.get("key1") is None

        # Deleting non-existent key returns False
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test clearing all entries."""
        cache: LRUCache[str] = LRUCache(max_size=10)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert cache.size == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=0.1)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        await asyncio.sleep(0.15)

        removed = await cache.cleanup_expired()
        assert removed == 2
        assert cache.size == 0

    def test_sync_get_set(self):
        """Test synchronous get/set operations."""
        cache: LRUCache[str] = LRUCache(max_size=10)

        cache.set_sync("key1", "value1")
        result = cache.get_sync("key1")
        assert result == "value1"

    def test_sync_get_missing_and_expired(self):
        """Test sync get handles missing and expired entries."""
        cache: LRUCache[str] = LRUCache(max_size=10, ttl_seconds=0.1)

        assert cache.get_sync("missing") is None

        cache.set_sync("key1", "value1")
        assert cache.get_sync("key1") == "value1"

        import time

        time.sleep(0.15)
        assert cache.get_sync("key1") is None

    def test_sync_set_overwrite_and_eviction(self):
        """Test sync set overwrites and evicts."""
        cache: LRUCache[str] = LRUCache(max_size=2)

        cache.set_sync("key1", "value1")
        cache.set_sync("key1", "value2")
        assert cache.get_sync("key1") == "value2"

        cache.set_sync("key2", "value2")
        cache.set_sync("key3", "value3")
        assert cache.get_sync("key1") is None
        assert cache.get_sync("key2") == "value2"

    def test_size_property(self):
        """Test size property."""
        cache: LRUCache[str] = LRUCache(max_size=10)

        assert cache.size == 0

        cache.set_sync("key1", "value1")
        assert cache.size == 1

        cache.set_sync("key2", "value2")
        assert cache.size == 2


class TestResponseCache:
    """Tests for ResponseCache."""

    @pytest.mark.asyncio
    async def test_search_cache(self):
        """Test caching search results."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response = {"results": [{"title": "Test"}], "provider": "test"}

        await cache.set_search("python", 10, response)
        cached = await cache.get_search("python", 10)

        assert cached == response

    @pytest.mark.asyncio
    async def test_search_cache_miss(self):
        """Test cache miss for search."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        cached = await cache.get_search("nonexistent", 10)
        assert cached is None

    @pytest.mark.asyncio
    async def test_search_cache_key_includes_params(self):
        """Test that cache key includes all parameters."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response1 = {"results": [{"id": 1}]}
        response2 = {"results": [{"id": 2}]}

        await cache.set_search("python", 10, response1)
        await cache.set_search("python", 20, response2)

        assert await cache.get_search("python", 10) == response1
        assert await cache.get_search("python", 20) == response2

    @pytest.mark.asyncio
    async def test_scrape_cache(self):
        """Test caching scrape results."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response = {"markdown": "# Test", "url": "https://example.com"}

        await cache.set_scrape("https://example.com", response)
        cached = await cache.get_scrape("https://example.com")

        assert cached == response

    @pytest.mark.asyncio
    async def test_cache_max_age(self):
        """Test max_age_seconds enforcement."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response = {"markdown": "# Test", "url": "https://example.com"}
        await cache.set_scrape("https://example.com", response)

        assert await cache.get_scrape("https://example.com", max_age_seconds=1) == response

        await asyncio.sleep(1.1)
        assert await cache.get_scrape("https://example.com", max_age_seconds=1) is None

    @pytest.mark.asyncio
    async def test_search_cache_max_age_expired(self):
        """Test search cache respects max_age_seconds."""
        cache = ResponseCache(ttl_seconds=3600, max_size=100, enabled=True)

        response = {"results": [{"title": "Test"}], "provider": "test"}
        await cache.set_search("python", 10, response)

        assert await cache.get_search("python", 10, max_age_seconds=1) == response
        await asyncio.sleep(1.1)
        assert await cache.get_search("python", 10, max_age_seconds=1) is None

    def test_unwrap_response_passthrough(self):
        """Test unwrap_response returns entry without cache wrapper."""
        assert ResponseCache._unwrap_response({"foo": "bar"}) == {"foo": "bar"}

    def test_is_fresh_with_missing_cached_at(self):
        """Test _is_fresh handles missing cached_at."""
        assert ResponseCache._is_fresh({"_cached_at": None}, max_age_seconds=10) is True

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test that disabled cache always returns None."""
        cache = ResponseCache(enabled=False)

        response = {"results": []}
        await cache.set_search("test", 10, response)

        assert await cache.get_search("test", 10) is None

    @pytest.mark.asyncio
    async def test_clear_and_close(self):
        """Test clear and close methods."""
        cache = ResponseCache(enabled=True)

        await cache.set_search("test", 10, {"results": []})
        assert cache.size > 0

        await cache.clear()
        assert cache.size == 0

        # Close should not raise
        await cache.close()

    @pytest.mark.asyncio
    async def test_case_insensitive_keys(self):
        """Test that cache keys are case-insensitive."""
        cache = ResponseCache(enabled=True)

        response = {"results": []}
        await cache.set_search("Python", 10, response)

        # Should match with different case
        cached = await cache.get_search("python", 10)
        assert cached == response

    def test_generate_key_with_unsortable_list(self):
        """Test cache key generation with unsortable list values."""
        key = ResponseCache._generate_key(
            "search",
            query="q",
            filters=[{"a": 1}, {"b": 2}],
        )
        assert isinstance(key, str)
