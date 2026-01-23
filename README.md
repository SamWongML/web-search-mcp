# Web Search MCP

A lightweight, high-performance Model Context Protocol (MCP) server for web search and scraping. Designed as a self-hosted alternative to Firecrawl MCP, supporting multiple search providers with automatic fallback.

## Features

- **Multiple Search Providers**: SerpAPI, Google Custom Search, Brave Search, DuckDuckGo
- **Automatic Fallback**: Seamlessly falls back to next provider on failure
- **Web Scraping**: Extract clean markdown from any webpage
- **Batch Operations**: Scrape multiple URLs concurrently
- **URL Discovery**: Find all links on a webpage
- **Rate Limiting**: Built-in rate limiting per provider
- **Caching**: LRU cache with configurable TTL
- **Docker Ready**: Production-ready containerization
- **Full Test Coverage**: Unit, integration, and E2E tests

## Installation

### Using uv (Recommended)

```bash
# Install dependencies
uv sync

# With dev dependencies
uv sync --all-extras
```

### Using Docker

```bash
cd docker
docker-compose up -d
```

## Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SERPAPI_API_KEY` | - | SerpAPI key (optional) |
| `GOOGLE_API_KEY` | - | Google API key (optional) |
| `GOOGLE_CSE_ID` | - | Google Custom Search Engine ID |
| `BRAVE_API_KEY` | - | Brave Search API key (optional) |
| `SCRAPER_TYPE` | `trafilatura` | Scraper: `trafilatura`, `crawl4ai`, `jina` |
| `CACHE_TTL_SECONDS` | `300` | Cache time-to-live |
| `CACHE_MAX_SIZE` | `1000` | Maximum cache entries |

## Usage

### Running the Server

```bash
# With uv
uv run python -m web_search_mcp

# Or with uvicorn
uv run uvicorn web_search_mcp.app:app --host 0.0.0.0 --port 8000

# Or with Docker
docker-compose -f docker/docker-compose.yml up
```

### MCP Tools

The server exposes four MCP tools:

#### 1. web_search

Search the web using configured providers with automatic fallback.

```json
{
  "query": "python async programming",
  "max_results": 10,
  "provider": null
}
```

#### 2. scrape_url

Scrape a single URL and extract clean markdown content.

```json
{
  "url": "https://example.com/article",
  "include_links": true,
  "include_images": false,
  "max_length": null
}
```

#### 3. batch_scrape

Scrape multiple URLs concurrently.

```json
{
  "urls": [
    "https://example.com/page1",
    "https://example.com/page2"
  ],
  "max_concurrent": 5,
  "include_links": false
}
```

#### 4. discover_urls

Discover all links on a webpage.

```json
{
  "url": "https://example.com",
  "max_urls": 100,
  "same_domain_only": true
}
```

### Connecting from Claude Code

Add to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "web-search": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Health Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Server info and available tools |
| `GET /health` | Detailed health check |
| `GET /ready` | Readiness probe (K8s) |
| `GET /alive` | Liveness probe (K8s) |

## Architecture

```
src/web_search_mcp/
├── config/          # Settings and configuration
├── models/          # Pydantic data models
├── providers/       # Search provider implementations
│   ├── serpapi.py
│   ├── google_cse.py
│   ├── brave.py
│   └── duckduckgo.py
├── scrapers/        # Web scraper implementations
│   ├── trafilatura_scraper.py
│   ├── crawl4ai_scraper.py
│   └── jina_reader.py
├── tools/           # MCP tool definitions
├── utils/           # Utilities (cache, rate limiter)
├── app.py           # Starlette ASGI application
└── server.py        # FastMCP server setup
```

## Provider Priority

Providers are tried in order until one succeeds:

1. **SerpAPI** (requires `SERPAPI_API_KEY`)
2. **Google CSE** (requires `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`)
3. **Brave Search** (requires `BRAVE_API_KEY`)
4. **DuckDuckGo** (no API key required, fallback)

## Development

### Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync all dependencies including dev
uv sync --all-extras
```

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# E2E tests
uv run pytest tests/e2e/

# Docker tests (requires Docker)
uv run pytest tests/docker/ -m docker

# With coverage
uv run pytest --cov=web_search_mcp --cov-report=html
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run mypy src/
```

## Docker

### Development

```bash
cd docker
docker-compose -f docker-compose.yml up --build
```

### Production

```bash
cd docker
docker-compose -f docker-compose.prod.yml up -d
```

### Building Images

```bash
# Development image
docker build -f docker/Dockerfile.dev -t web-search-mcp:dev .

# Production image
docker build -f docker/Dockerfile -t web-search-mcp:latest .
```

## API Limits

| Provider | Free Tier |
|----------|-----------|
| SerpAPI | 100/month |
| Google CSE | 100/day |
| Brave Search | 2000/month |
| DuckDuckGo | Unlimited (unofficial) |

## License

MIT
