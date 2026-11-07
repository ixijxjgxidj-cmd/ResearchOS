# ResearchOS MCP Server Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

# Copy all repository source files
COPY . ./

# Install project and dependencies into system Python
RUN uv pip install --system --no-cache .

# Pre-create /data/vault directory with correct ownership for persistent storage
RUN mkdir -p /data/vault && chown -R user:user /app /data

USER user

# Default settings
ENV RESEARCH_VAULT_ROOT=/data/vault
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Start MCP Server with SSE transport
CMD ["python", "-m", "researchos.adapters.mcp_server"]
