# Build context is the repo root (packages/ is copied into the image):
#   docker build -f services/app/Dockerfile .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
# The venv must be built at the path it runs from: console scripts (alembic, uvicorn) get an
# absolute shebang to the venv python.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/app/pyproject.toml services/app/pyproject.toml
COPY packages/models/pyproject.toml packages/models/pyproject.toml
COPY packages/ingest/pyproject.toml packages/ingest/pyproject.toml
COPY packages/verify/pyproject.toml packages/verify/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package hukuk-app
COPY services/app/app services/app/app
COPY packages/models/hukuk_models packages/models/hukuk_models
COPY packages/ingest/hukuk_ingest packages/ingest/hukuk_ingest
COPY packages/verify/hukuk_verify packages/verify/hukuk_verify
# The uv cache mount persists on the deploy host and keys a local package on its pyproject only:
# without --reinstall-package a source change shipped the previous build (2026-10-08).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package hukuk-app \
        --reinstall-package hukuk-app --reinstall-package hukuk-models \
        --reinstall-package hukuk-ingest --reinstall-package hukuk-verify

FROM python:3.12-slim-bookworm
# No proxy is trusted for X-Forwarded-For unless FORWARDED_ALLOW_IPS names it (login rate limit).
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" FORWARDED_ALLOW_IPS=""
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY services/app/alembic.ini services/app/alembic.ini
COPY services/app/alembic services/app/alembic
WORKDIR /app/services/app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
