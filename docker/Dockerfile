# Production Dockerfile for Web Search MCP
# Multi-stage build for minimal image size

# ─── Builder Stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Create lock file and install dependencies
RUN uv lock --no-cache
RUN uv sync --frozen --no-dev --no-editable

# Copy source code
COPY src/ ./src/

# Install the package
RUN uv sync --frozen --no-dev


# ─── Runtime Stage ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install runtime dependencies for Playwright/Crawl4AI
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # Fonts
    fonts-liberation \
    fonts-noto-color-emoji \
    # Networking
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Copy virtual environment from builder
COPY --from=builder --chown=app:app /app/.venv /home/app/.venv

# Copy source code
COPY --from=builder --chown=app:app /app/src /home/app/src

# Set environment variables
ENV PATH="/home/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH="/home/app/src"

# Default configuration
ENV WEBSEARCH_HOST=0.0.0.0
ENV WEBSEARCH_PORT=8000
ENV WEBSEARCH_LOG_LEVEL=INFO
ENV WEBSEARCH_DEBUG=false

# Install Playwright browsers (Chromium only for smaller size)
RUN playwright install chromium || echo "Playwright install skipped"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "web_search_mcp.app:app", "--host", "0.0.0.0", "--port", "8000"]
