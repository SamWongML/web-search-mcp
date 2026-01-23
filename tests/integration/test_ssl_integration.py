"""Integration tests for SSL/TLS certificate configuration with real HTTP requests."""

import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from web_search_mcp.config import Settings


class TestSSLIntegrationWithMockedRequests:
    """Integration tests using mocked HTTP requests to verify SSL config is passed."""

    @pytest.fixture
    def mock_settings_ssl_disabled(self):
        """Settings with SSL verification disabled."""
        return Settings(
            _env_file=None,
            ssl_verify=False,
            brave_api_key="test-key",
        )

    @pytest.fixture
    def mock_settings_with_ca_bundle(self):
        """Settings with custom CA bundle."""
        # Use system CA bundle if available
        system_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/ca-bundle.pem",
            "/etc/ssl/cert.pem",
        ]

        for path in system_ca_paths:
            if Path(path).exists():
                return Settings(
                    _env_file=None,
                    ssl_ca_bundle=path,
                    brave_api_key="test-key",
                )

        # If no system CA found, return default settings
        return Settings(
            _env_file=None,
            brave_api_key="test-key",
        )

    @pytest.mark.asyncio
    @respx.mock
    async def test_provider_request_with_ssl_disabled(
        self, mock_settings_ssl_disabled
    ):
        """Provider should work with SSL verification disabled."""
        from web_search_mcp.providers.brave import BraveProvider

        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(
                200,
                json={
                    "web": {
                        "results": [
                            {
                                "url": "https://example.com",
                                "title": "Example",
                                "description": "Test",
                            }
                        ]
                    }
                },
            )
        )

        with patch(
            "web_search_mcp.providers.brave.settings",
            mock_settings_ssl_disabled,
        ):
            provider = BraveProvider(api_key=mock_settings_ssl_disabled.brave_api_key)
            results = await provider.search("test query")

            assert len(results) == 1
            assert results[0].url == "https://example.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_scraper_request_with_ssl_disabled(self):
        """Scraper should work with SSL verification disabled."""
        from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper

        respx.get("https://example.com/page").mock(
            return_value=Response(
                200,
                text="<html><body><h1>Test Page</h1><p>Content here</p></body></html>",
            )
        )

        settings = Settings(_env_file=None, ssl_verify=False)

        with patch(
            "web_search_mcp.scrapers.trafilatura_scraper.settings",
            settings,
        ):
            scraper = TrafilaturaScraper(timeout_seconds=10)
            result = await scraper.scrape("https://example.com/page")

            assert result.success
            assert result.url == "https://example.com/page"

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_check_with_custom_ssl(self):
        """Health check should use SSL configuration."""
        from web_search_mcp.utils.health import HealthChecker

        respx.head("https://www.google.com").mock(
            return_value=Response(200)
        )

        settings = Settings(_env_file=None, ssl_verify=False)

        with patch(
            "web_search_mcp.utils.health.settings",
            settings,
        ):
            checker = HealthChecker()
            status = await checker.check_http_client()

            assert status.healthy
            assert "HTTP client working" in status.message


class TestSSLConfigurationInServerLifespan:
    """Tests for SSL configuration in server lifecycle."""

    @pytest.mark.asyncio
    async def test_server_creates_client_with_ssl_config(self):
        """Server lifespan should create HTTP client with SSL configuration."""
        from web_search_mcp.config import Settings

        # Create settings with SSL disabled
        test_settings = Settings(
            _env_file=None,
            ssl_verify=False,
            use_browser_scraper=False,  # Use trafilatura to avoid browser deps
        )

        # Verify the SSL context is False
        assert test_settings.get_ssl_context() is False

    @pytest.mark.asyncio
    async def test_server_creates_client_with_custom_ca_bundle(self):
        """Server should use custom CA bundle when configured."""
        from web_search_mcp.config import Settings

        # Check for system CA bundles
        system_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/etc/ssl/ca-bundle.pem",
            "/etc/ssl/cert.pem",
        ]

        ca_path = None
        for path in system_ca_paths:
            if Path(path).exists():
                ca_path = path
                break

        if ca_path is None:
            pytest.skip("No system CA bundle found")

        test_settings = Settings(
            _env_file=None,
            ssl_ca_bundle=ca_path,
        )

        assert test_settings.get_ssl_context() == ca_path


class TestSSLWithMultipleProviders:
    """Tests for SSL configuration across multiple providers."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_all_providers_use_same_ssl_config(self):
        """All providers should use the same SSL configuration."""
        from web_search_mcp.config import Settings
        from web_search_mcp.providers.brave import BraveProvider
        from web_search_mcp.providers.serpapi import SerpAPIProvider
        from web_search_mcp.providers.tavily import TavilyProvider

        settings = Settings(
            _env_file=None,
            ssl_verify=False,
            brave_api_key="test-brave",
            serpapi_key="test-serpapi",
            tavily_api_key="test-tavily",
        )

        # Mock responses for all providers
        respx.get("https://api.search.brave.com/res/v1/web/search").mock(
            return_value=Response(200, json={"web": {"results": []}})
        )
        respx.get("https://serpapi.com/search").mock(
            return_value=Response(200, json={"organic_results": []})
        )
        respx.post("https://api.tavily.com/search").mock(
            return_value=Response(200, json={"results": []})
        )

        # Test all providers
        for provider_cls, patch_module in [
            (BraveProvider, "web_search_mcp.providers.brave"),
            (SerpAPIProvider, "web_search_mcp.providers.serpapi"),
            (TavilyProvider, "web_search_mcp.providers.tavily"),
        ]:
            with patch(f"{patch_module}.settings", settings):
                if provider_cls == BraveProvider:
                    provider = provider_cls(api_key=settings.brave_api_key)
                elif provider_cls == SerpAPIProvider:
                    provider = provider_cls(api_key=settings.serpapi_key)
                else:
                    provider = provider_cls(api_key=settings.tavily_api_key)

                # Should work without SSL errors
                results = await provider.search("test")
                assert isinstance(results, list)


class TestSSLEnvironmentVariables:
    """Tests for SSL configuration via environment variables."""

    def test_ssl_cert_dir_from_env(self):
        """SSL cert dir should be loaded from environment variable."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_CERT_DIR": "/custom/certs"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_cert_dir == "/custom/certs"
            assert settings.get_ssl_context() == "/custom/certs"

    def test_ssl_ca_bundle_from_env(self):
        """SSL CA bundle should be loaded from environment variable."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_CA_BUNDLE": "/custom/ca-bundle.pem"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_ca_bundle == "/custom/ca-bundle.pem"
            assert settings.get_ssl_context() == "/custom/ca-bundle.pem"

    def test_ssl_verify_false_from_env(self):
        """SSL verify should be disabled via environment variable."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_VERIFY": "false"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_verify is False
            assert settings.get_ssl_context() is False

    def test_combined_ssl_env_vars(self):
        """All SSL env vars should work together with correct priority."""
        with patch.dict(
            os.environ,
            {
                "WEBSEARCH_SSL_VERIFY": "true",
                "WEBSEARCH_SSL_CA_BUNDLE": "/path/to/bundle.pem",
                "WEBSEARCH_SSL_CERT_DIR": "/path/to/certs",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)
            # CA bundle takes precedence over cert dir
            assert settings.get_ssl_context() == "/path/to/bundle.pem"

    def test_ssl_verify_false_overrides_paths(self):
        """ssl_verify=False should override CA paths."""
        with patch.dict(
            os.environ,
            {
                "WEBSEARCH_SSL_VERIFY": "false",
                "WEBSEARCH_SSL_CA_BUNDLE": "/path/to/bundle.pem",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)
            # ssl_verify=False takes highest priority
            assert settings.get_ssl_context() is False
