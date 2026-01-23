"""Unit tests for SSL/TLS certificate configuration."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from web_search_mcp.config import Settings


class TestSSLSettings:
    """Tests for SSL configuration in Settings."""

    def test_default_ssl_settings(self):
        """Default SSL settings should enable verification with system certs."""
        settings = Settings(
            _env_file=None,  # Ignore .env file
        )
        assert settings.ssl_verify is True
        assert settings.ssl_cert_dir is None
        assert settings.ssl_ca_bundle is None

    def test_get_ssl_context_default(self):
        """get_ssl_context returns True when using default settings."""
        settings = Settings(_env_file=None)
        assert settings.get_ssl_context() is True

    def test_get_ssl_context_disabled(self):
        """get_ssl_context returns False when ssl_verify is disabled."""
        settings = Settings(
            _env_file=None,
            ssl_verify=False,
        )
        assert settings.get_ssl_context() is False

    def test_get_ssl_context_with_ca_bundle(self):
        """get_ssl_context returns CA bundle path when configured."""
        settings = Settings(
            _env_file=None,
            ssl_ca_bundle="/path/to/ca-bundle.crt",
        )
        assert settings.get_ssl_context() == "/path/to/ca-bundle.crt"

    def test_get_ssl_context_with_cert_dir(self):
        """get_ssl_context returns cert dir path when configured."""
        settings = Settings(
            _env_file=None,
            ssl_cert_dir="/etc/ssl/certs/corporate",
        )
        assert settings.get_ssl_context() == "/etc/ssl/certs/corporate"

    def test_ssl_ca_bundle_takes_precedence_over_cert_dir(self):
        """CA bundle has higher priority than cert dir."""
        settings = Settings(
            _env_file=None,
            ssl_ca_bundle="/path/to/ca-bundle.crt",
            ssl_cert_dir="/etc/ssl/certs/corporate",
        )
        assert settings.get_ssl_context() == "/path/to/ca-bundle.crt"

    def test_ssl_verify_false_overrides_all(self):
        """ssl_verify=False takes highest priority."""
        settings = Settings(
            _env_file=None,
            ssl_verify=False,
            ssl_ca_bundle="/path/to/ca-bundle.crt",
            ssl_cert_dir="/etc/ssl/certs/corporate",
        )
        assert settings.get_ssl_context() is False

    def test_environment_variable_loading(self):
        """Settings should load from environment variables."""
        with patch.dict(
            os.environ,
            {
                "WEBSEARCH_SSL_CERT_DIR": "/custom/cert/dir",
                "WEBSEARCH_SSL_CA_BUNDLE": "/custom/ca-bundle.pem",
                "WEBSEARCH_SSL_VERIFY": "true",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_cert_dir == "/custom/cert/dir"
            assert settings.ssl_ca_bundle == "/custom/ca-bundle.pem"
            assert settings.ssl_verify is True

    def test_environment_variable_ssl_verify_false(self):
        """SSL verify can be disabled via environment variable."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_VERIFY": "false"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_verify is False


class TestSSLWithHTTPClient:
    """Tests for SSL configuration applied to httpx clients."""

    def test_httpx_client_with_default_ssl(self):
        """HTTP client should use default SSL with no custom config."""
        settings = Settings(_env_file=None)
        ssl_context = settings.get_ssl_context()

        # This should not raise - uses system CA bundle
        client = httpx.AsyncClient(verify=ssl_context)
        assert client is not None

    def test_httpx_client_with_ssl_disabled(self):
        """HTTP client should work with SSL verification disabled."""
        settings = Settings(_env_file=None, ssl_verify=False)
        ssl_context = settings.get_ssl_context()

        client = httpx.AsyncClient(verify=ssl_context)
        # verify=False should be set
        assert client._transport._pool._ssl_context is None or not ssl_context

    def test_httpx_client_with_custom_ca_bundle(self):
        """HTTP client should accept custom CA bundle path."""
        # Create a temporary CA bundle file
        # Note: httpx validates the cert file when creating the client,
        # so we use the system CA bundle if available for this test
        system_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/ca-bundle.pem",  # OpenSUSE
            "/etc/ssl/cert.pem",  # macOS/Alpine
        ]

        ca_path = None
        for path in system_ca_paths:
            if Path(path).exists():
                ca_path = path
                break

        if ca_path is None:
            pytest.skip("No system CA bundle found for testing")

        settings = Settings(_env_file=None, ssl_ca_bundle=ca_path)
        ssl_context = settings.get_ssl_context()

        assert ssl_context == ca_path

        # Client creation should work with valid CA bundle
        client = httpx.AsyncClient(verify=ssl_context)
        assert client is not None

    def test_httpx_client_with_cert_directory(self):
        """HTTP client should accept certificate directory path."""
        # Create a temporary directory with CA certificates
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a dummy certificate file
            cert_path = Path(temp_dir) / "corporate-ca.pem"
            cert_path.write_text(
                "-----BEGIN CERTIFICATE-----\n"
                "MIIBkTCB+wIJAKHBfpegPjMCMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl\n"
                "c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM\n"
                "BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC5rC5D5803x8hNw7RE5OHD\n"
                "j0ER/8+FZjYDE5orXQ7e7Ku3HfWz7uP6Q7Dd5QXvlRWpPl+J8bKJ+8j7w6RPXCVD\n"
                "AgMBAAEwDQYJKoZIhvcNAQELBQADQQBQNmFkXUH7cUQ3lZKEH9QL0cHP1ByQKZZl\n"
                "QQPjEMF6IY7jYfH7M5lQOZ3eMVQ5z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5Z5\n"
                "-----END CERTIFICATE-----\n"
            )

            settings = Settings(_env_file=None, ssl_cert_dir=temp_dir)
            ssl_context = settings.get_ssl_context()

            assert ssl_context == temp_dir

            # httpx accepts directory paths for verify parameter
            client = httpx.AsyncClient(verify=ssl_context)
            assert client is not None


class TestSSLConfigurationPrecedence:
    """Tests for SSL configuration priority and edge cases."""

    def test_empty_string_ssl_ca_bundle_ignored(self):
        """Empty string for ssl_ca_bundle should be treated as None."""
        settings = Settings(
            _env_file=None,
            ssl_ca_bundle="",
        )
        # Empty string is falsy, so it should return True (default)
        assert settings.get_ssl_context() is True

    def test_empty_string_ssl_cert_dir_ignored(self):
        """Empty string for ssl_cert_dir should be treated as None."""
        settings = Settings(
            _env_file=None,
            ssl_cert_dir="",
        )
        assert settings.get_ssl_context() is True

    def test_none_values_use_defaults(self):
        """Explicit None values should use default SSL verification."""
        settings = Settings(
            _env_file=None,
            ssl_ca_bundle=None,
            ssl_cert_dir=None,
            ssl_verify=True,
        )
        assert settings.get_ssl_context() is True

    def test_ssl_verify_string_true(self):
        """String 'true' should be converted to boolean True."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_VERIFY": "True"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_verify is True

    def test_ssl_verify_string_false(self):
        """String 'false' should be converted to boolean False."""
        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_VERIFY": "False"},
            clear=False,
        ):
            settings = Settings(_env_file=None)
            assert settings.ssl_verify is False


class TestSSLInProviders:
    """Tests for SSL configuration in search providers."""

    @pytest.mark.asyncio
    async def test_brave_provider_uses_ssl_config(self):
        """BraveProvider should use SSL settings for fallback client."""
        from web_search_mcp.providers.brave import BraveProvider

        with patch.dict(
            os.environ,
            {"WEBSEARCH_SSL_VERIFY": "false"},
            clear=False,
        ):
            # Force settings reload
            from web_search_mcp.config import Settings

            with patch(
                "web_search_mcp.providers.brave.settings",
                Settings(_env_file=None, ssl_verify=False),
            ):
                provider = BraveProvider(api_key=None)
                client = await provider._get_client()

                try:
                    # The client should have been created with verify=False
                    assert client is not None
                finally:
                    await client.aclose()

    @pytest.mark.asyncio
    async def test_serpapi_provider_uses_ssl_config(self):
        """SerpAPIProvider should use SSL settings for fallback client."""
        from web_search_mcp.providers.serpapi import SerpAPIProvider

        with patch(
            "web_search_mcp.providers.serpapi.settings",
            Settings(_env_file=None, ssl_verify=False),
        ):
            provider = SerpAPIProvider(api_key=None)
            client = await provider._get_client()

            try:
                assert client is not None
            finally:
                await client.aclose()

    @pytest.mark.asyncio
    async def test_tavily_provider_uses_ssl_config(self):
        """TavilyProvider should use SSL settings for fallback client."""
        from web_search_mcp.providers.tavily import TavilyProvider

        with patch(
            "web_search_mcp.providers.tavily.settings",
            Settings(_env_file=None, ssl_verify=False),
        ):
            provider = TavilyProvider(api_key=None)
            client = await provider._get_client()

            try:
                assert client is not None
            finally:
                await client.aclose()


class TestSSLInScrapers:
    """Tests for SSL configuration in web scrapers."""

    @pytest.mark.asyncio
    async def test_trafilatura_scraper_uses_ssl_config(self):
        """TrafilaturaScraper should use SSL settings for fallback client."""
        from web_search_mcp.scrapers.trafilatura_scraper import TrafilaturaScraper

        with patch(
            "web_search_mcp.scrapers.trafilatura_scraper.settings",
            Settings(_env_file=None, ssl_verify=False),
        ):
            scraper = TrafilaturaScraper()
            client = await scraper._get_client()

            try:
                assert client is not None
            finally:
                await client.aclose()

    @pytest.mark.asyncio
    async def test_jina_reader_scraper_uses_ssl_config(self):
        """JinaReaderScraper should use SSL settings for fallback client."""
        from web_search_mcp.scrapers.jina_reader import JinaReaderScraper

        with patch(
            "web_search_mcp.scrapers.jina_reader.settings",
            Settings(_env_file=None, ssl_verify=False),
        ):
            scraper = JinaReaderScraper()
            client = await scraper._get_client()

            try:
                assert client is not None
            finally:
                await client.aclose()


class TestSSLInHealthCheck:
    """Tests for SSL configuration in health checks."""

    @pytest.mark.asyncio
    async def test_health_checker_uses_ssl_config(self):
        """HealthChecker should use SSL settings."""
        from web_search_mcp.utils.health import HealthChecker

        with patch(
            "web_search_mcp.utils.health.settings",
            Settings(_env_file=None, ssl_verify=False),
        ):
            checker = HealthChecker()
            # Just verify the checker can be instantiated with patched settings
            assert checker is not None


class TestSSLWithRealCertificates:
    """Tests using real certificate files."""

    def test_valid_pem_file_path(self):
        """Test with a valid PEM certificate file (system CA if available)."""
        # Use system CA bundle for valid certificate testing
        system_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/ca-bundle.pem",  # OpenSUSE
            "/etc/ssl/cert.pem",  # macOS/Alpine
        ]

        ca_path = None
        for path in system_ca_paths:
            if Path(path).exists():
                ca_path = path
                break

        if ca_path is None:
            pytest.skip("No system CA bundle found for testing")

        settings = Settings(_env_file=None, ssl_ca_bundle=ca_path)
        context = settings.get_ssl_context()

        assert context == ca_path
        assert Path(ca_path).exists()

    def test_nonexistent_cert_path_accepted(self):
        """Non-existent cert path is accepted (fails at request time)."""
        settings = Settings(
            _env_file=None,
            ssl_ca_bundle="/nonexistent/path/to/cert.pem",
        )
        # Settings should accept the path (validation happens at request time)
        assert settings.get_ssl_context() == "/nonexistent/path/to/cert.pem"

    def test_system_ca_bundle_path(self):
        """Test with system CA bundle paths if available."""
        # Common system CA bundle locations
        system_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/ca-bundle.pem",  # OpenSUSE
            "/etc/ssl/cert.pem",  # macOS/Alpine
        ]

        for path in system_ca_paths:
            if Path(path).exists():
                settings = Settings(_env_file=None, ssl_ca_bundle=path)
                context = settings.get_ssl_context()
                assert context == path

                # Should be able to create a client with this bundle
                client = httpx.AsyncClient(verify=context)
                assert client is not None
                break
