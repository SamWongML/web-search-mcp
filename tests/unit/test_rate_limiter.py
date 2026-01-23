"""Unit tests for rate limiter utilities."""

import asyncio

import pytest

from web_search_mcp.utils.rate_limiter import (
    SlidingWindowLimiter,
    TokenBucketLimiter,
)


class TestTokenBucketLimiter:
    """Tests for TokenBucketLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring tokens within limit."""
        limiter = TokenBucketLimiter(rate=10, capacity=10)

        # Should acquire 5 tokens without blocking
        for _ in range(5):
            acquired = await limiter.try_acquire()
            assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_exhausted(self):
        """Test that limiter blocks when exhausted."""
        limiter = TokenBucketLimiter(rate=1, capacity=1)

        # First acquire should succeed
        assert await limiter.try_acquire() is True

        # Second should fail (no wait)
        assert await limiter.try_acquire() is False

    @pytest.mark.asyncio
    async def test_tokens_replenish(self):
        """Test that tokens replenish over time."""
        limiter = TokenBucketLimiter(rate=100, capacity=1)  # 100 tokens/sec

        # Exhaust the token
        await limiter.try_acquire()
        assert await limiter.try_acquire() is False

        # Wait for replenishment
        await asyncio.sleep(0.02)  # 20ms = ~2 tokens at 100/sec

        assert await limiter.try_acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_with_timeout(self):
        """Test acquire with timeout."""
        limiter = TokenBucketLimiter(rate=10, capacity=1)

        # Exhaust token
        await limiter.try_acquire()

        # Should succeed after waiting
        acquired = await limiter.acquire(timeout=0.2)
        assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_timeout_exceeded(self):
        """Test that acquire returns False on timeout."""
        limiter = TokenBucketLimiter(rate=0.1, capacity=1)  # Very slow

        # Exhaust token
        await limiter.try_acquire()

        # Should timeout
        acquired = await limiter.acquire(timeout=0.05)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_available_tokens_property(self):
        """Test available_tokens property."""
        limiter = TokenBucketLimiter(rate=10, capacity=10)

        # Initially full
        assert limiter.available_tokens >= 9  # Allow for timing

        # After acquiring some
        await limiter.try_acquire()
        await limiter.try_acquire()
        assert limiter.available_tokens >= 7


class TestSlidingWindowLimiter:
    """Tests for SlidingWindowLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """Test acquiring within limit."""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert await limiter.try_acquire() is True

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self):
        """Test that exceeding limit fails."""
        limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)

        # Use up all requests
        for _ in range(3):
            assert await limiter.try_acquire() is True

        # Should fail
        assert await limiter.try_acquire() is False

    @pytest.mark.asyncio
    async def test_requests_expire(self):
        """Test that requests expire after window."""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=0.1)

        # Use request
        assert await limiter.try_acquire() is True
        assert await limiter.try_acquire() is False

        # Wait for expiry
        await asyncio.sleep(0.15)

        # Should be available again
        assert await limiter.try_acquire() is True

    @pytest.mark.asyncio
    async def test_remaining_requests_property(self):
        """Test remaining_requests property."""
        limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)

        assert limiter.remaining_requests == 5

        await limiter.try_acquire()
        await limiter.try_acquire()

        assert limiter.remaining_requests == 3

    @pytest.mark.asyncio
    async def test_acquire_with_timeout(self):
        """Test acquire with timeout waiting for expiry."""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=0.1)

        # Use request
        await limiter.try_acquire()

        # Should succeed after waiting
        acquired = await limiter.acquire(timeout=0.2)
        assert acquired is True

    @pytest.mark.asyncio
    async def test_acquire_timeout_exceeded(self):
        """Test acquire timeout when window is too long."""
        limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)

        # Use request
        await limiter.try_acquire()

        # Should timeout quickly
        acquired = await limiter.acquire(timeout=0.05)
        assert acquired is False


class TestMultiProviderRateLimiter:
    """Tests for MultiProviderRateLimiter."""

    @pytest.mark.asyncio
    async def test_try_acquire_known_provider(self, test_settings):
        """Test acquiring for a known provider."""
        from web_search_mcp.utils.rate_limiter import MultiProviderRateLimiter

        limiter = MultiProviderRateLimiter(test_settings)

        # Should be able to acquire for known providers
        assert await limiter.try_acquire("duckduckgo") is True
        assert await limiter.try_acquire("brave") is True

    @pytest.mark.asyncio
    async def test_try_acquire_unknown_provider(self, test_settings):
        """Test acquiring for unknown provider (should allow)."""
        from web_search_mcp.utils.rate_limiter import MultiProviderRateLimiter

        limiter = MultiProviderRateLimiter(test_settings)

        # Unknown providers should be allowed
        assert await limiter.try_acquire("unknown_provider") is True

    @pytest.mark.asyncio
    async def test_get_limiter(self, test_settings):
        """Test getting limiter for a provider."""
        from web_search_mcp.utils.rate_limiter import MultiProviderRateLimiter

        limiter = MultiProviderRateLimiter(test_settings)

        # Known provider should return limiter
        serpapi_limiter = limiter.get_limiter("serpapi")
        assert serpapi_limiter is not None

        # Unknown provider should return None
        unknown_limiter = limiter.get_limiter("unknown")
        assert unknown_limiter is None
