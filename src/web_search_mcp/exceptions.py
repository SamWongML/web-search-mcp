"""Custom exceptions for Web Search MCP."""


class WebSearchMCPError(Exception):
    """Base exception for all Web Search MCP errors."""

    pass


# ─── Provider Errors ─────────────────────────────────────────────


class ProviderError(WebSearchMCPError):
    """Base exception for search provider errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ProviderNotConfiguredError(ProviderError):
    """Raised when a provider is not configured (missing API key)."""

    def __init__(self, provider: str) -> None:
        super().__init__(provider, "Provider is not configured (missing API key)")


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rate limit is exceeded."""

    def __init__(self, provider: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(provider, message)


class ProviderAPIError(ProviderError):
    """Raised when a provider API returns an error."""

    def __init__(self, provider: str, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(provider, f"API error {status_code}: {message}")


class AllProvidersExhaustedError(WebSearchMCPError):
    """Raised when all search providers have been exhausted."""

    def __init__(self, message: str = "All search providers have been exhausted") -> None:
        super().__init__(message)


# ─── Scraper Errors ──────────────────────────────────────────────


class ScraperError(WebSearchMCPError):
    """Base exception for scraper errors."""

    def __init__(self, url: str, message: str) -> None:
        self.url = url
        self.message = message
        super().__init__(f"[{url}] {message}")


class ScraperTimeoutError(ScraperError):
    """Raised when a scrape operation times out."""

    def __init__(self, url: str, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(url, f"Scrape timed out after {timeout_seconds}s")


class ScraperConnectionError(ScraperError):
    """Raised when a connection to a URL fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(url, f"Connection failed: {reason}")


class ScraperContentError(ScraperError):
    """Raised when content extraction fails."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(url, f"Content extraction failed: {reason}")


# ─── Validation Errors ───────────────────────────────────────────


class ValidationError(WebSearchMCPError):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Validation error for '{field}': {message}")


class InvalidURLError(ValidationError):
    """Raised when a URL is invalid."""

    def __init__(self, url: str, reason: str = "Invalid URL format") -> None:
        self.url = url
        super().__init__("url", f"{reason}: {url}")


# ─── Cache Errors ────────────────────────────────────────────────


class CacheError(WebSearchMCPError):
    """Base exception for cache errors."""

    pass


class CacheConnectionError(CacheError):
    """Raised when connection to cache backend fails."""

    def __init__(self, backend: str, reason: str) -> None:
        self.backend = backend
        super().__init__(f"Failed to connect to {backend} cache: {reason}")
