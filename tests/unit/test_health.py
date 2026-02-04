"""Unit tests for health utilities."""

from types import SimpleNamespace

import pytest

from web_search_mcp.utils.health import HealthChecker


@pytest.mark.asyncio
async def test_check_http_client_success(monkeypatch):
    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def head(self, url):  # noqa: ARG002
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(
        "web_search_mcp.utils.health.httpx.AsyncClient",
        lambda **kwargs: DummyClient(),  # noqa: ARG005
    )

    checker = HealthChecker()
    status = await checker.check_http_client()
    assert status.healthy is True


@pytest.mark.asyncio
async def test_check_http_client_failure(monkeypatch):
    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return None

        async def head(self, url):  # noqa: ARG002
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "web_search_mcp.utils.health.httpx.AsyncClient",
        lambda **kwargs: DummyClient(),  # noqa: ARG005
    )

    checker = HealthChecker()
    status = await checker.check_http_client()
    assert status.healthy is False


@pytest.mark.asyncio
async def test_check_readiness():
    checker = HealthChecker()
    status = await checker.check_readiness()
    assert status["ready"] is True
    assert "duckduckgo" in status["providers"]


@pytest.mark.asyncio
async def test_check_providers_configured_with_keys(monkeypatch):
    from web_search_mcp.config import settings

    monkeypatch.setattr(settings, "serpapi_key", "token")
    monkeypatch.setattr(settings, "tavily_api_key", "token")
    monkeypatch.setattr(settings, "brave_api_key", "token")

    checker = HealthChecker()
    status = await checker.check_providers_configured()
    providers = status.details.get("providers", [])
    assert "serpapi" in providers
    assert "tavily" in providers
    assert "brave" in providers
