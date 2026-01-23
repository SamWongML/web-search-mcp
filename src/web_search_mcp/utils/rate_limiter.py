"""Rate limiting utilities using token bucket algorithm."""

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import anyio

P = ParamSpec("P")
R = TypeVar("R")


class TokenBucketLimiter:
    """
    Token bucket rate limiter for controlling request rates.

    The bucket starts full and tokens are consumed with each request.
    Tokens are replenished at a fixed rate over time.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        """
        Initialize the token bucket limiter.

        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self._lock = anyio.Lock()

    async def _replenish(self) -> None:
        """Replenish tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self._lock:
            await self._replenish()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def acquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (None for no timeout)

        Returns:
            True if tokens were acquired, False if timeout
        """
        start_time = time.monotonic()

        while True:
            if await self.try_acquire(tokens):
                return True

            # Check timeout
            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # Wait for tokens to replenish
            async with self._lock:
                await self._replenish()
                if self.tokens < tokens:
                    wait_time = (tokens - self.tokens) / self.rate
                    if timeout is not None:
                        remaining = timeout - (time.monotonic() - start_time)
                        wait_time = min(wait_time, remaining)

            await anyio.sleep(min(wait_time, 0.1))

    @property
    def available_tokens(self) -> float:
        """Return current available tokens (approximate)."""
        elapsed = time.monotonic() - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class SlidingWindowLimiter:
    """
    Sliding window rate limiter for request counting.

    Tracks requests within a time window and limits the rate.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        """
        Initialize the sliding window limiter.

        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        self._lock = anyio.Lock()

    async def _cleanup(self) -> None:
        """Remove expired requests from the window."""
        cutoff = time.monotonic() - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]

    async def try_acquire(self) -> bool:
        """
        Try to make a request without blocking.

        Returns:
            True if request is allowed, False otherwise
        """
        async with self._lock:
            await self._cleanup()

            if len(self.requests) < self.max_requests:
                self.requests.append(time.monotonic())
                return True
            return False

    async def acquire(self, timeout: float | None = None) -> bool:
        """
        Acquire a request slot, waiting if necessary.

        Args:
            timeout: Maximum time to wait (None for no timeout)

        Returns:
            True if request is allowed, False if timeout
        """
        start_time = time.monotonic()

        while True:
            if await self.try_acquire():
                return True

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # Calculate wait time until oldest request expires
            async with self._lock:
                await self._cleanup()
                if self.requests:
                    oldest = self.requests[0]
                    wait_time = (oldest + self.window_seconds) - time.monotonic()
                    wait_time = max(0.01, wait_time)
                else:
                    wait_time = 0.01

            await anyio.sleep(min(wait_time, 0.1))

    @property
    def remaining_requests(self) -> int:
        """Return approximate remaining requests in current window."""
        cutoff = time.monotonic() - self.window_seconds
        current = sum(1 for t in self.requests if t > cutoff)
        return max(0, self.max_requests - current)


class MultiProviderRateLimiter:
    """
    Manages rate limiters for multiple providers.

    Each provider has its own rate limiter with different limits.
    """

    def __init__(self, settings: Any) -> None:
        """
        Initialize rate limiters for all providers.

        Args:
            settings: Application settings with rate limit configuration
        """
        self._limiters: dict[str, TokenBucketLimiter | SlidingWindowLimiter] = {}

        # SerpAPI: X requests per hour
        self._limiters["serpapi"] = SlidingWindowLimiter(
            max_requests=settings.serpapi_requests_per_hour,
            window_seconds=3600,
        )

        # Tavily: X requests per month (approximated as daily limit)
        # 1000/month ≈ 33/day
        self._limiters["tavily"] = SlidingWindowLimiter(
            max_requests=max(1, settings.tavily_requests_per_month // 30),
            window_seconds=86400,
        )

        # Brave: X requests per second
        self._limiters["brave"] = TokenBucketLimiter(
            rate=settings.brave_requests_per_second,
            capacity=max(1, int(settings.brave_requests_per_second * 2)),
        )

        # DuckDuckGo: X requests per minute
        self._limiters["duckduckgo"] = SlidingWindowLimiter(
            max_requests=settings.duckduckgo_requests_per_minute,
            window_seconds=60,
        )

        # Jina: 20 requests per minute without API key
        self._limiters["jina"] = SlidingWindowLimiter(
            max_requests=20,
            window_seconds=60,
        )

    async def try_acquire(self, provider: str) -> bool:
        """
        Try to acquire a request slot for a provider.

        Args:
            provider: Provider name

        Returns:
            True if request is allowed, False otherwise
        """
        limiter = self._limiters.get(provider)
        if limiter is None:
            return True  # Unknown provider, allow by default
        return await limiter.try_acquire()

    async def acquire(self, provider: str, timeout: float | None = None) -> bool:
        """
        Acquire a request slot for a provider, waiting if necessary.

        Args:
            provider: Provider name
            timeout: Maximum time to wait

        Returns:
            True if request is allowed, False if timeout
        """
        limiter = self._limiters.get(provider)
        if limiter is None:
            return True
        return await limiter.acquire(timeout=timeout)

    def get_limiter(self, provider: str) -> TokenBucketLimiter | SlidingWindowLimiter | None:
        """Get the limiter for a specific provider."""
        return self._limiters.get(provider)


def rate_limited(
    limiter: TokenBucketLimiter | SlidingWindowLimiter,
    timeout: float | None = 30.0,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to apply rate limiting to an async function.

    Args:
        limiter: Rate limiter to use
        timeout: Maximum time to wait for rate limit

    Returns:
        Decorated function
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            acquired = await limiter.acquire(timeout=timeout)
            if not acquired:
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {func.__name__}, timeout after {timeout}s"
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class RateLimitExceededError(Exception):
    """Raised when a rate limit is exceeded and timeout occurs."""

    pass
