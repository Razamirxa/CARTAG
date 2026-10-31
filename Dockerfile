# Builds the website, then runs the Python server that serves the API, the scan page and the built website.

FROM node:22-slim AS web
WORKDIR /app
COPY package.json package-lock.json tsconfig.base.json ./
COPY web/package.json web/
RUN npm ci
COPY web/ web/
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY alembic/ alembic/
COPY cartag/ cartag/
COPY --from=web /app/web/dist web/dist
COPY docker-start.sh ./
CMD ["sh", "docker-start.sh"]
