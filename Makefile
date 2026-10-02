COMPOSE = docker compose --env-file .env -f infra/compose/docker-compose.yml

.PHONY: install lint typecheck test up down migrate migration db-reset env

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
