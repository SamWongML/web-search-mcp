"""Health check utilities for the server."""

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from web_search_mcp.config import settings


@dataclass
class HealthStatus:
    """Health status of a component."""

    name: str
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """
    Health checker for the application.

    Checks various components and returns overall health status.
    """

    async def check_http_client(self) -> HealthStatus:
        """Check if HTTP client can make requests."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                verify=settings.get_ssl_context(),
            ) as client:
                response = await client.head("https://www.google.com")
                latency_ms = (time.monotonic() - start) * 1000

                return HealthStatus(
                    name="http_client",
                    healthy=response.status_code < 500,
                    message=f"HTTP client working, status {response.status_code}",
                    latency_ms=latency_ms,
                )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return HealthStatus(
                name="http_client",
                healthy=False,
                message=f"HTTP client error: {e!s}",
                latency_ms=latency_ms,
            )

    async def check_providers_configured(self) -> HealthStatus:
        """Check if at least one search provider is configured."""
        configured_providers = []

        if settings.is_serpapi_configured():
            configured_providers.append("serpapi")
        if settings.is_tavily_configured():
            configured_providers.append("tavily")
        if settings.is_brave_configured():
            configured_providers.append("brave")

        # DuckDuckGo always available (no API key required)
        configured_providers.append("duckduckgo")

        return HealthStatus(
            name="providers",
            healthy=len(configured_providers) > 0,
            message=f"Configured providers: {', '.join(configured_providers)}",
            details={"providers": configured_providers},
        )

    async def check_all(self) -> dict[str, Any]:
        """
        Run all health checks and return overall status.

        Returns:
            Dictionary with health status information
        """
        checks = [
            await self.check_providers_configured(),
        ]

        all_healthy = all(check.healthy for check in checks)

        return {
            "healthy": all_healthy,
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": {
                check.name: {
                    "healthy": check.healthy,
                    "message": check.message,
                    "latency_ms": check.latency_ms,
                    "details": check.details,
                }
                for check in checks
            },
            "version": "0.1.0",
        }

    async def check_readiness(self) -> dict[str, Any]:
        """
        Check if the server is ready to accept requests.

        This is a lightweight check for Kubernetes readiness probes.

        Returns:
            Dictionary with readiness status
        """
        # Basic readiness - just check that we have providers
        providers_check = await self.check_providers_configured()

        return {
            "ready": providers_check.healthy,
            "status": "ready" if providers_check.healthy else "not_ready",
            "providers": providers_check.details.get("providers", []),
        }

    async def check_liveness(self) -> dict[str, Any]:
        """
        Check if the server is alive.

        This is a minimal check for Kubernetes liveness probes.

        Returns:
            Dictionary with liveness status
        """
        return {
            "alive": True,
            "status": "alive",
        }
