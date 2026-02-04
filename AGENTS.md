# AGENTS.md

This repository hosts Web Search MCP, a Starlette + FastMCP server that exposes web search and scraping tools with caching and provider fallback.

**Project Summary**
- Product: Model Context Protocol (MCP) server for search, scraping, batch scrape, URL discovery, and URL mapping.
- Entry points: `src/web_search_mcp/app.py` (Starlette app) and `src/web_search_mcp/server.py` (FastMCP server + tool registration).
- Runtime: async Python 3.11, `httpx` for I/O, `anyio` for concurrency, `structlog` for logging.

**Architecture**
- HTTP layer: `src/web_search_mcp/app.py` mounts the FastMCP streamable HTTP app and provides health endpoints.
- MCP/tool layer: `src/web_search_mcp/tools/*.py` defines `web_search`, `scrape_url`, `batch_scrape`, `discover_urls`, `map_urls`.
- Provider layer: `src/web_search_mcp/providers/*.py` implements search backends behind a protocol interface.
- Scraper layer: `src/web_search_mcp/scrapers/*.py` implements extraction backends behind a protocol interface.
- Shared services: `src/web_search_mcp/utils/cache.py`, `src/web_search_mcp/utils/content_extractor.py`, `src/web_search_mcp/utils/rate_limiter.py`.

**Request Flow**
- Starlette request → FastMCP tool → `AppContext` from lifespan → provider or scraper → cache → response.
- `web_search` can optionally attach scrapes with bounded concurrency.

**Providers**
- Provider order is defined in `src/web_search_mcp/server.py:create_providers`.
- Current order: Tavily → DuckDuckGo → SerpAPI → Brave, with exponential backoff on failures in `src/web_search_mcp/providers/registry.py`.
- `is_configured` is the gate for API-key providers; DuckDuckGo is always available.

**Scrapers**
- `create_scraper` uses Crawl4AI when available, otherwise Trafilatura.
- `ScrapeOptions.apply_defaults()` pulls server defaults for formats and main-content filtering.
- Content extraction favors trafilatura and falls back to readability; see `src/web_search_mcp/utils/content_extractor.py`.

**Caching**
- `ResponseCache` is an in-memory LRU with TTL. Keys are parameterized and order-normalized.
- Tools add a `cached` field on cache hits.

**Configuration**
- All env vars are prefixed with `WEBSEARCH_` and loaded from `.env`.
- Canonical config lives in `src/web_search_mcp/config/settings.py` and `.env.example`.

**Gotchas**
- Provider order in docs may differ from `create_providers`; treat `src/web_search_mcp/server.py` as source of truth.
- `MultiProviderRateLimiter` is created in the app context but is not yet enforced in provider calls.
- Jina Reader scraper exists but is not wired into `create_scraper`.

**Common Commands**
```bash
# Install deps
uv sync --all-extras

# Run server
uv run python -m web_search_mcp

# Tests
uv run pytest
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/
uv run pytest tests/docker/ -m docker

# Quality
uv run ruff format .
uv run ruff check .
uv run mypy src/
```

**Conventions**
- Keep I/O async; prefer `anyio` task groups for concurrency.
- Favor small, typed Pydantic models for tool inputs/outputs.
- When adding providers or scrapers, implement the protocol in `src/web_search_mcp/providers/base.py` or `src/web_search_mcp/scrapers/base.py` and register in `src/web_search_mcp/server.py`.
