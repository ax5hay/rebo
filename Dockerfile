# Stage 1: the product UI (web/dist), served by the bot at /
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

# Stage 2: the bot
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra embed --extra postgres --extra otel
COPY --from=web /web/dist ./web/dist
ENV REBO_STATE_DIR=/data
EXPOSE 8080
CMD ["uv", "run", "--no-sync", "rebo", "serve", "--host", "0.0.0.0", "--port", "8080"]
