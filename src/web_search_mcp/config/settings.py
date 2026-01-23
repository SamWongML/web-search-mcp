"""Application settings loaded from environment variables."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All settings can be overridden via environment variables prefixed with WEBSEARCH_.
    For example, WEBSEARCH_DEBUG=true sets debug=True.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WEBSEARCH_",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Server Settings ─────────────────────────────────────────────
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS (comma-separated origins or "*")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # ─── Search Provider API Keys ────────────────────────────────────
    serpapi_key: str | None = None
    google_api_key: str | None = None
    google_cx: str | None = None  # Custom Search Engine ID
    brave_api_key: str | None = None
    jina_api_key: str | None = None

    # ─── Rate Limits ─────────────────────────────────────────────────
    serpapi_requests_per_hour: int = 50
    google_cse_requests_per_day: int = 100
    brave_requests_per_second: float = 1.0
    duckduckgo_requests_per_minute: int = 30

    # ─── HTTP Client Settings ────────────────────────────────────────
    max_connections: int = 100
    max_keepalive_connections: int = 20
    request_timeout: float = 30.0

    # ─── Scraper Settings ────────────────────────────────────────────
    max_concurrent_scrapes: int = 5
    scrape_timeout_seconds: int = 30
    use_browser_scraper: bool = True  # crawl4ai vs trafilatura

    # ─── Cache Settings ──────────────────────────────────────────────
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    redis_url: str | None = None  # Optional Redis for distributed cache

    def is_serpapi_configured(self) -> bool:
        """Check if SerpAPI is configured."""
        return bool(self.serpapi_key)

    def is_google_cse_configured(self) -> bool:
        """Check if Google Custom Search is configured."""
        return bool(self.google_api_key and self.google_cx)

    def is_brave_configured(self) -> bool:
        """Check if Brave Search is configured."""
        return bool(self.brave_api_key)

    def is_jina_configured(self) -> bool:
        """Check if Jina Reader is configured."""
        return bool(self.jina_api_key)


# Global settings instance
settings = Settings()
