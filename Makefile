COMPOSE = docker compose --env-file .env -f infra/compose/docker-compose.yml

.PHONY: install lint typecheck test up down migrate env

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
