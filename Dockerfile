# Multi-stage build for UniFi MCP Server
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install uv for faster dependency management
RUN pip install uv

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml README.md ./
COPY src ./src

# Install dependencies and build package
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache .

# Final stage
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r mcp && \
    useradd -r -g mcp -u 1000 -s /sbin/nologin -c "MCP Server User" mcp

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=mcp:mcp src ./src
COPY --chown=mcp:mcp pyproject.toml README.md ./

# Create directories for logs and config
RUN mkdir -p /app/logs /app/config && \
    chown -R mcp:mcp /app

# Switch to non-root user
USER mcp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from src.config import Settings; Settings(); sys.exit(0)" || exit 1

# Default command - run via FastMCP
CMD ["python", "-m", "src.main"]
