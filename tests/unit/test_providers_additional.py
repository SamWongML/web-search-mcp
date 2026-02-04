"""Additional unit tests for providers to improve branch coverage."""

import builtins
from types import SimpleNamespace

import pytest

from web_search_mcp.exceptions import ProviderAPIError
from web_search_mcp.providers.brave import BraveProvider
from web_search_mcp.providers.duckduckgo import DuckDuckGoProvider
from web_search_mcp.providers.serpapi import SerpAPIProvider
from web_search_mcp.providers.tavily import TavilyProvider


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = {}
        self.content = text.encode() if text else b"{}"

    def json(self):
        return self._json


class DummyClient:
    def __init__(self, response):
        self.response = response
        self.params = None
        self.headers = None
        self.json_payload = None
        self.closed = False

    async def get(self, url, headers=None, params=None):  # noqa: ARG002
        self.params = params
        self.headers = headers
        return self.response

    async def post(self, url, json=None, headers=None):  # noqa: ARG002
        self.json_payload = json
        self.headers = headers
        return self.response

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_brave_search_params_and_safe_search():
    response = DummyResponse(
        200,
        json_data={"web": {"results": [{"url": "https://example.com", "title": "T"}]}},
    )
    client = DummyClient(response)
    provider = BraveProvider(api_key="token", http_client=client)  # type: ignore[arg-type]

    assert await provider.is_available() is True
    results = await provider.search(
        "query",
        max_results=5,
        language="en",
        region="us",
        safe_search=False,
        include_domains=["example.com"],
        exclude_domains=["other.com"],
    )

    assert results
    assert client.params["search_lang"] == "en"
    assert client.params["country"] == "us"
    assert client.params["safesearch"] == "off"
    assert "site:example.com" in client.params["q"]


@pytest.mark.asyncio
async def test_brave_not_configured_raises():
    provider = BraveProvider(api_key=None)
    with pytest.raises(ProviderAPIError):
        await provider.search("query")


def test_brave_parse_error():
    provider = BraveProvider(api_key="token")
    results = provider._parse_results({"web": {"results": ["bad"]}}, max_results=5)
    assert results == []


def test_duckduckgo_import_error(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ARG001
        if name == "ddgs":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    provider = DuckDuckGoProvider()
    with pytest.raises(ProviderAPIError):
        provider._create_ddgs()


def test_duckduckgo_parse_error():
    provider = DuckDuckGoProvider()
    results = provider._parse_results(["bad"], max_results=5)
    assert results == []


@pytest.mark.asyncio
async def test_serpapi_search_params_and_time_range():
    response = DummyResponse(
        200,
        json_data={"organic_results": [{"link": "https://example.com", "title": "T"}]},
    )
    client = DummyClient(response)
    provider = SerpAPIProvider(api_key="token", http_client=client)  # type: ignore[arg-type]

    results = await provider.search(
        "query",
        max_results=5,
        language="en",
        region="us",
        time_range="qdr:d",
        safe_search=True,
    )

    assert results
    assert client.params["hl"] == "en"
    assert client.params["gl"] == "us"
    assert client.params["tbs"] == "qdr:d"


def test_serpapi_normalize_time_range_qdr():
    assert SerpAPIProvider._normalize_time_range("qdr:w") == "qdr:w"


def test_serpapi_parse_error():
    provider = SerpAPIProvider(api_key="token")
    results = provider._parse_results({"organic_results": ["bad"]}, max_results=5)
    assert results == []


@pytest.mark.asyncio
async def test_tavily_payload_includes_domains():
    response = DummyResponse(
        200,
        json_data={"results": [{"url": "https://example.com", "title": "T", "content": "C"}]},
    )
    client = DummyClient(response)
    provider = TavilyProvider(api_key="token", http_client=client)  # type: ignore[arg-type]

    results = await provider.search(
        "query",
        max_results=5,
        topic="general",
        time_range="week",
        include_domains=["example.com"],
        exclude_domains=["other.com"],
    )

    assert results
    assert client.json_payload["include_domains"] == ["example.com"]
    assert client.json_payload["exclude_domains"] == ["other.com"]


@pytest.mark.asyncio
async def test_tavily_not_configured_raises():
    provider = TavilyProvider(api_key=None)
    with pytest.raises(ProviderAPIError):
        await provider.search("query")


@pytest.mark.asyncio
async def test_tavily_error_non_200():
    response = DummyResponse(500, json_data={"detail": "Boom"}, text="Boom")
    client = DummyClient(response)
    provider = TavilyProvider(api_key="token", http_client=client)  # type: ignore[arg-type]

    with pytest.raises(ProviderAPIError):
        await provider.search("query")


def test_tavily_parse_error():
    provider = TavilyProvider(api_key="token")
    results = provider._parse_results({"results": ["bad"]}, max_results=5)
    assert results == []


def test_tavily_extract_domain_error(monkeypatch):
    def boom(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr("urllib.parse.urlparse", boom)
    assert TavilyProvider._extract_domain("https://example.com") is None
