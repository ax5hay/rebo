FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra embed
ENV REPORTSBOT_STATE_DIR=/data
EXPOSE 8080
CMD ["uv", "run", "--no-sync", "reportsbot", "serve", "--host", "0.0.0.0", "--port", "8080"]
