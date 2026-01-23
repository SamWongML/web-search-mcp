"""
Starlette ASGI application with FastMCP server mounted.

Designed for multi-client access via Streamable HTTP transport.
"""

import contextlib
from collections.abc import AsyncIterator

import structlog
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from web_search_mcp.config import settings
from web_search_mcp.server import mcp
from web_search_mcp.utils.health import HealthChecker

logger = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette) -> AsyncIterator[None]:
    """
    Application lifespan manager.

    Initializes shared resources on startup, cleans up on shutdown.
    """
    logger.info(
        "starting_http_server",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
    )

    # MCP server has its own lifespan, managed via session_manager
    async with mcp.session_manager.run():
        yield

    logger.info("http_server_shutdown")


async def health_check(_request: Request) -> JSONResponse:
    """
    Kubernetes-compatible health check endpoint.

    Returns 200 if healthy, 503 if unhealthy.
    """
    checker = HealthChecker()
    status = await checker.check_all()

    http_status = 200 if status["healthy"] else 503
    return JSONResponse(status, status_code=http_status)


async def readiness_check(_request: Request) -> JSONResponse:
    """
    Readiness probe - checks if server can accept requests.

    Returns 200 if ready, 503 if not ready.
    """
    checker = HealthChecker()
    status = await checker.check_readiness()

    http_status = 200 if status["ready"] else 503
    return JSONResponse(status, status_code=http_status)


async def liveness_check(_request: Request) -> JSONResponse:
    """
    Liveness probe - minimal check that server is alive.

    Always returns 200 if the server is running.
    """
    checker = HealthChecker()
    status = await checker.check_liveness()

    return JSONResponse(status, status_code=200)


async def root(_request: Request) -> JSONResponse:
    """Root endpoint with server information."""
    return JSONResponse(
        {
            "name": "Web Search MCP",
            "version": "0.1.0",
            "description": "A lightweight MCP server for web search and scraping",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
                "ready": "/ready",
                "alive": "/alive",
            },
            "tools": [
                "web_search",
                "scrape_url",
                "batch_scrape",
                "discover_urls",
            ],
        }
    )


# Define middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],  # Required for MCP sessions
    ),
]

# Build Starlette application
app = Starlette(
    debug=settings.debug,
    routes=[
        # Root endpoint
        Route("/", root, methods=["GET"]),
        # Health endpoints
        Route("/health", health_check, methods=["GET"]),
        Route("/ready", readiness_check, methods=["GET"]),
        Route("/alive", liveness_check, methods=["GET"]),
        # MCP endpoint - Streamable HTTP
        Mount("/mcp", app=mcp.streamable_http_app()),
    ],
    middleware=middleware,
    lifespan=lifespan,
)
