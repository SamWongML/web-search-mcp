# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Web Search MCP is a Model Context Protocol server for web search and scraping. It provides four MCP tools: `web_search`, `scrape_url`, `batch_scrape`, and `discover_urls`.

## Commands

```bash
# Install dependencies
uv sync --all-extras

# Run the server
uv run python -m web_search_mcp

# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/
uv run pytest tests/docker/ -m docker

# Run a single test file or test
uv run pytest tests/unit/test_cache.py
uv run pytest tests/unit/test_cache.py::test_cache_set_get

# Code quality
uv run ruff format .
uv run ruff check .
uv run mypy src/
```

## Architecture

The codebase uses a **protocol-based layered architecture**:

1. **HTTP/MCP Layer** (`app.py`, `server.py`) - Starlette ASGI app with FastMCP for MCP protocol handling
2. **Tools Layer** (`tools/`) - MCP tool definitions that orchestrate business logic
3. **Business Logic** - Provider registry with fallback, caching, rate limiting
4. **Provider/Scraper Layer** - Concrete implementations behind protocol interfaces

### Key Design Patterns

**Protocol-based abstractions**: `SearchProvider` and `Scraper` are Python protocols (`providers/base.py`, `scrapers/base.py`). Add new providers/scrapers by implementing these protocols.

**Automatic provider fallback**: `ProviderRegistry` (`providers/registry.py`) tries providers in priority order (SerpAPI → Google CSE → Brave → DuckDuckGo) with exponential backoff for failing providers.

**Lifespan-managed resources**: `AppContext` in `server.py` manages shared resources (HTTP client, cache, rate limiters) via FastMCP's lifespan context.

**Dual rate limiting strategies**: Token bucket for burst control, sliding window for quota enforcement (`utils/rate_limiter.py`).

### Configuration

All settings come from environment variables with `WEBSEARCH_` prefix, managed via Pydantic settings in `config/settings.py`.
