# ResearchOS Remote MCP Server Dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency specifications first for caching
COPY pyproject.toml README.md uv.lock* ./

# Install dependencies into system Python
RUN uv pip install --system --no-cache -e .

# Copy application source code and assets
COPY src/ ./src/
COPY schemas/ ./schemas/
COPY templates/ ./templates/
COPY skills/ ./skills/
COPY AGENTS.md ./AGENTS.md

# Set default ResearchVault path inside the container
ENV RESEARCH_VAULT_ROOT=/data/vault
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV PORT=8000

# Mountable volume for Markdown ResearchVault
VOLUME ["/data/vault"]

EXPOSE 8000

# Start MCP Server with SSE/HTTP transport for remote agent hosting
CMD ["python", "-m", "researchos.adapters.mcp_server"]
