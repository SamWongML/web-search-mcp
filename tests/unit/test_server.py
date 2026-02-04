"""Unit tests for server helpers."""

import builtins

import pytest

from web_search_mcp.config import settings
from web_search_mcp.server import create_scraper


@pytest.mark.asyncio
async def test_create_scraper_fallback(monkeypatch):
    monkeypatch.setattr(settings, "use_browser_scraper", True)

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "web_search_mcp.scrapers.crawl4ai_scraper":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    scraper = await create_scraper()
    assert scraper.__class__.__name__ == "TrafilaturaScraper"
