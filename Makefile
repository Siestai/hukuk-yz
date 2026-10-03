COMPOSE = docker compose --env-file .env -f infra/compose/docker-compose.yml
DASHBOARD_PORT = $(or $(shell sed -n 's/^DASHBOARD_HOST_PORT=//p' .env 2>/dev/null),3000)

.PHONY: install lint typecheck test up down migrate migration db-reset env dev user load-archive demo-data web-dev e2e

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy services packages

test:
	uv run pytest

env:
	@test -f .env || cp .env.example .env

up: env
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

migrate: env
	$(COMPOSE) run --rm app alembic upgrade head

# Autogenerate a draft migration against the DB in .env; review and hand-edit before committing.
migration: env
	@test -n "$(name)" || { echo "usage: make migration name=<slug>"; exit 1; }
	set -a && . ./.env && set +a && cd services/app && uv run alembic revision --autogenerate -m "$(name)"

# Destroys the local database volume.
db-reset: env
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build postgres
	$(MAKE) migrate

# Whole stack for local use (docs/local-dev.md): postgres, migrations, app, worker, dashboard-web.
dev: env
	@infra/scripts/dev-env.sh
	$(COMPOSE) up -d --build
	@echo "Dashboard: http://localhost:$(DASHBOARD_PORT)  (next: make user ..., then make demo-data or make load-archive)"

# Interactive on purpose: the password is asked on the terminal.
user: env
	@test -n "$(email)" -a -n "$(name)" -a -n "$(role)" || { echo "usage: make user email=a@b.c name='Ad Soyad' role=reviewer|admin"; exit 1; }
	$(COMPOSE) exec app python -m app.users create --email "$(email)" --name "$(name)" --role "$(role)"

# The private Drive copy (data/drive) into the review queue. Scan and parse run on the host (uv;
# they write data/extracted and data/work, both gitignored), the load runs in the app container
# against the compose database. The scan skips OCR (the decision PDFs have a text layer).
# Exit code 1 of scan/parse means "finished, some files had errors" (see the printed summary).
load-archive: env
	@test -d data/drive || { echo "data/drive is missing: copy the Drive folder there first (docs/local-dev.md)"; exit 1; }
	infra/scripts/set-env.sh ARCHIVE_HOST_DIR ../../data/drive
	$(COMPOSE) up -d app
	mkdir -p data/work
	uv run hukuk-ingest scan data/drive --out data/work/scan --text-cache data/extracted --no-ocr || [ $$? -eq 1 ]
	uv run hukuk-ingest decisions parse --scan-report data/work/scan/files.jsonl --text-cache data/extracted --out data/work/decisions || [ $$? -eq 1 ]
	$(COMPOSE) run --rm -v "$(CURDIR)/data/work:/work:ro" app python -m app.loaders.decisions /work/decisions/decisions.jsonl --files /work/scan/files.jsonl

# The synthetic fixture (infra/demo/README.md): no private data needed. Points the app's /archive
# mount at the demo PDFs, so the PDF tab works.
demo-data: env
	infra/scripts/set-env.sh ARCHIVE_HOST_DIR ../../infra/demo/archive
	$(COMPOSE) up -d app
	$(COMPOSE) run --rm -v "$(CURDIR)/infra/demo:/demo:ro" app python -m app.loaders.decisions /demo/decisions.jsonl --files /demo/files.jsonl

# UI work on the host (hot reload) against the compose app on :8000. Port 3001 so it can run next
# to the dashboard-web container; log in with a user created by `make user`.
web-dev:
	pnpm install
	APP_API_URL=http://localhost:8000 pnpm --filter dashboard-web exec next dev -p $(or $(WEB_DEV_PORT),3001)

# Playwright against a running stack with demo data (services/dashboard-web/e2e/README.md).
e2e:
	@test -n "$$E2E_EMAIL" -a -n "$$E2E_PASSWORD" || { echo "set E2E_EMAIL and E2E_PASSWORD (a reviewer of the demo database)"; exit 1; }
	BASE_URL=$${BASE_URL:-http://localhost:$(DASHBOARD_PORT)} pnpm --filter dashboard-web e2e
