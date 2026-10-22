# syntax=docker/dockerfile:1.7
# ReBo image, built for fast rebuilds and fast, offline-capable starts:
#   * dependencies, the embedding model and the web app are separate cached layers; a source change
#     only rebuilds the small source layer
#   * BuildKit caches for npm and uv
#   * the local embedding model is baked in: a new container downloads nothing (works without internet)
#   * runtime has no uv and no build caches, and runs as a non-root user

ARG EMBED_MODEL=snowflake/snowflake-arctic-embed-s

# ---- the product UI (web/dist) ----
FROM node:25-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

# ---- Python dependencies only (no project): changes only with uv.lock ----
FROM python:3.13-slim AS deps
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra embed --extra postgres --extra otel

# ---- the embedding model (tests/test_settings.py checks EMBED_MODEL matches rebo.retrieval) ----
FROM deps AS model
ARG EMBED_MODEL
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBED_MODEL}', cache_dir='/opt/models')" \
 && chmod -R a+rX /opt/models

# ---- runtime ----
FROM python:3.13-slim
RUN useradd --create-home --uid 10001 rebo && mkdir -p /data && chown rebo /data \
 && printf '#!/bin/sh\nexec python -m rebo.cli "$@"\n' > /usr/local/bin/rebo && chmod +x /usr/local/bin/rebo
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY --from=model /opt/models /opt/models
COPY --from=web /web/dist /app/web/dist
COPY src /app/src
RUN python -m compileall -q /app/src
ENV PATH=/app/.venv/bin:$PATH PYTHONPATH=/app/src PYTHONUNBUFFERED=1 REBO_STATE_DIR=/data \
    FASTEMBED_CACHE_PATH=/opt/models HF_HUB_OFFLINE=1
USER rebo
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4).status != 200)"
CMD ["rebo", "serve", "--host", "0.0.0.0", "--port", "8080"]
