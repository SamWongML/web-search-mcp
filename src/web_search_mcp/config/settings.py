"""Application settings loaded from environment variables."""

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
    cors_origins: str = "*"

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as a list (parsed from comma-separated string)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ─── Search Provider API Keys ────────────────────────────────────
    serpapi_key: str | None = None
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    jina_api_key: str | None = None

    # ─── Rate Limits ─────────────────────────────────────────────────
    serpapi_requests_per_hour: int = 50
    tavily_requests_per_month: int = 1000  # Free tier: 1000 credits/month
    brave_requests_per_second: float = 1.0
    duckduckgo_requests_per_minute: int = 30

    # ─── HTTP Client Settings ────────────────────────────────────────
    max_connections: int = 100
    max_keepalive_connections: int = 20
    request_timeout: float = 30.0

    # ─── SSL/TLS Settings ───────────────────────────────────────────
    # Path to corporate CA certificate bundle (PEM format)
    # Can be a single file or directory containing certificates
    ssl_cert_dir: str | None = None
    # Path to a specific CA certificate file (alternative to ssl_cert_dir)
    ssl_ca_bundle: str | None = None
    # Disable SSL verification (NOT recommended for production)
    ssl_verify: bool = True

    # ─── Scraper Settings ────────────────────────────────────────────
    max_concurrent_scrapes: int = 5
    scrape_timeout_seconds: int = 30
    use_browser_scraper: bool = True  # crawl4ai vs trafilatura
    search_scrape_max_concurrent: int = 5
    default_scrape_formats: str = "markdown"
    default_only_main_content: bool = True

    # ─── Cache Settings ──────────────────────────────────────────────
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    cache_max_size: int = 1000
    redis_url: str | None = None  # Optional Redis for distributed cache

    def is_serpapi_configured(self) -> bool:
        """Check if SerpAPI is configured."""
        return bool(self.serpapi_key)

    def is_tavily_configured(self) -> bool:
        """Check if Tavily Search is configured."""
        return bool(self.tavily_api_key)

    def is_brave_configured(self) -> bool:
        """Check if Brave Search is configured."""
        return bool(self.brave_api_key)

    def is_jina_configured(self) -> bool:
        """Check if Jina Reader is configured."""
        return bool(self.jina_api_key)

    def get_ssl_context(self) -> bool | str:
        """
        Get SSL verification configuration for httpx.

        Returns:
            - False if ssl_verify is disabled
            - Path to CA bundle/cert dir if configured
            - True for default SSL verification

        Priority: ssl_verify=False > ssl_ca_bundle > ssl_cert_dir > True
        """
        if not self.ssl_verify:
            return False
        if self.ssl_ca_bundle:
            return self.ssl_ca_bundle
        if self.ssl_cert_dir:
            return self.ssl_cert_dir
        return True

    def get_default_scrape_formats(self) -> list[str]:
        """Return default scrape formats as a list."""
        if isinstance(self.default_scrape_formats, str):
            parts = [p.strip() for p in self.default_scrape_formats.split(",")]
            return [p for p in parts if p]
        return list(self.default_scrape_formats)


# Global settings instance
settings = Settings()
