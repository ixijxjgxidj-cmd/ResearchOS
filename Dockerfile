# ResearchOS MCP Server Dockerfile for Hugging Face Spaces & Container Cloud
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set up standard non-root user (UID 1000) for Hugging Face Spaces
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

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

# Pre-create /data/vault directory with correct ownership for HF Persistent Storage
RUN mkdir -p /data/vault && chown -R user:user /app /data

USER user

# Default Hugging Face Spaces settings
ENV RESEARCH_VAULT_ROOT=/data/vault
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV PORT=7860

EXPOSE 7860

# Start MCP Server with SSE transport
CMD ["python", "-m", "researchos.adapters.mcp_server"]
