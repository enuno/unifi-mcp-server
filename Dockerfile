# Multi-stage build for UniFi MCP Server
# Using Alpine Linux for minimal attack surface and reduced CVEs

FROM python:3.13-alpine AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies (removed after build)
RUN apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    cargo \
    rust

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

# Final stage - minimal runtime image
FROM python:3.13-alpine

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies (no build tools)
RUN apk add --no-cache \
    libffi \
    openssl \
    ca-certificates && \
    # Remove apk cache
    rm -rf /var/cache/apk/*

# Create non-root user
RUN addgroup -S mcp && \
    adduser -S -G mcp -u 1000 -s /sbin/nologin -D mcp

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

# Expose MCP server port (if applicable)
# EXPOSE 8000

# Default command - run via FastMCP
CMD ["python", "-m", "src.main"]
