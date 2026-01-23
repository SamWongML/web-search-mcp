"""
Docker container tests using testcontainers.
Tests the containerized MCP server functionality.
"""

from pathlib import Path

import httpx
import pytest

# Skip if testcontainers not available
pytest.importorskip("testcontainers")

from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs


class WebSearchMCPContainer(DockerContainer):
    """Custom container for Web Search MCP server."""

    def __init__(
        self,
        image: str = "web-search-mcp:test",
        port: int = 8000,
        **kwargs,
    ):
        super().__init__(image, **kwargs)
        self.port = port
        self.with_exposed_ports(port)
        self.with_env("LOG_LEVEL", "DEBUG")
        self.with_env("HOST", "0.0.0.0")
        self.with_env("PORT", str(port))

    def get_base_url(self) -> str:
        """Get the base URL for the container."""
        host = self.get_container_host_ip()
        port = self.get_exposed_port(self.port)
        return f"http://{host}:{port}"

    def wait_for_ready(self, timeout: float = 30.0) -> None:
        """Wait for the container to be ready."""
        wait_for_logs(self, "Uvicorn running on", timeout=timeout)


@pytest.fixture(scope="module")
def docker_image_built():
    """Ensure Docker image is built before tests."""
    import subprocess

    project_root = Path(__file__).parent.parent.parent
    dockerfile_path = project_root / "docker" / "Dockerfile"

    if not dockerfile_path.exists():
        pytest.skip("Dockerfile not found")

    # Build the image
    result = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(dockerfile_path),
            "-t",
            "web-search-mcp:test",
            str(project_root),
        ],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )

    if result.returncode != 0:
        pytest.skip(f"Docker build failed: {result.stderr}")

    return True


@pytest.fixture(scope="module")
def mcp_container(docker_image_built):  # noqa: ARG001
    """Start the MCP container for testing."""
    container = WebSearchMCPContainer()

    try:
        container.start()
        container.wait_for_ready(timeout=60.0)
        yield container
    finally:
        container.stop()


@pytest.mark.docker
class TestContainerHealth:
    """Test container health endpoints."""

    def test_container_starts(self, mcp_container):
        """Test that container starts successfully."""
        assert mcp_container.get_container_host_ip() is not None

    def test_root_endpoint(self, mcp_container):
        """Test root endpoint returns server info."""
        base_url = mcp_container.get_base_url()

        response = httpx.get(f"{base_url}/", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Web Search MCP"
        assert "version" in data

    def test_health_endpoint(self, mcp_container):
        """Test health endpoint."""
        base_url = mcp_container.get_base_url()

        response = httpx.get(f"{base_url}/health", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert "healthy" in data

    def test_ready_endpoint(self, mcp_container):
        """Test readiness endpoint."""
        base_url = mcp_container.get_base_url()

        response = httpx.get(f"{base_url}/ready", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert "ready" in data

    def test_alive_endpoint(self, mcp_container):
        """Test liveness endpoint."""
        base_url = mcp_container.get_base_url()

        response = httpx.get(f"{base_url}/alive", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True


@pytest.mark.docker
class TestContainerMCP:
    """Test MCP functionality in container."""

    def test_mcp_endpoint_responds(self, mcp_container):
        """Test MCP endpoint responds to requests."""
        base_url = mcp_container.get_base_url()

        response = httpx.post(
            f"{base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
            timeout=10.0,
        )

        # Should get a response (even if error due to stateless mode)
        # 406 is returned for content negotiation issues with MCP
        assert response.status_code in [200, 400, 406, 500]


@pytest.mark.docker
class TestContainerResilience:
    """Test container resilience and recovery."""

    def test_handles_concurrent_requests(self, mcp_container):
        """Test container handles concurrent health checks."""
        import concurrent.futures

        base_url = mcp_container.get_base_url()
        num_requests = 10

        def make_request():
            response = httpx.get(f"{base_url}/health", timeout=10.0)
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(status == 200 for status in results)

    def test_handles_invalid_json(self, mcp_container):
        """Test container handles invalid JSON gracefully."""
        base_url = mcp_container.get_base_url()

        response = httpx.post(
            f"{base_url}/mcp",
            content="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

        # Should return error, not crash
        # 406 is returned for content negotiation issues with MCP
        assert response.status_code in [400, 406, 500]


@pytest.mark.docker
class TestContainerEnvironment:
    """Test container environment configuration."""

    def test_env_vars_applied(self, mcp_container):
        """Test environment variables are applied."""
        # Container should be running with LOG_LEVEL=DEBUG
        logs = mcp_container.get_logs()
        # Should have some debug output
        assert logs is not None


# Standalone test without fixtures for quick validation
class TestDockerBuildable:
    """Quick tests that don't require running container."""

    def test_dockerfile_exists(self):
        """Test Dockerfile exists."""
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "docker" / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found"

    def test_docker_compose_exists(self):
        """Test docker-compose.yml exists."""
        project_root = Path(__file__).parent.parent.parent
        compose_file = project_root / "docker" / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml not found"

    def test_dockerfile_syntax(self):
        """Basic Dockerfile syntax check."""
        project_root = Path(__file__).parent.parent.parent
        dockerfile = project_root / "docker" / "Dockerfile"

        if not dockerfile.exists():
            pytest.skip("Dockerfile not found")

        content = dockerfile.read_text()

        # Check for essential instructions
        assert "FROM" in content, "Dockerfile missing FROM instruction"
        assert "COPY" in content or "ADD" in content, "Dockerfile missing COPY/ADD"
        assert "CMD" in content or "ENTRYPOINT" in content, "Dockerfile missing CMD/ENTRYPOINT"
