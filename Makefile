.PHONY: up down install dev test lint fmt typecheck check

up:          ## Start Postgres + Redis
	docker compose up -d
down:
	docker compose down
install:     ## Install backend deps
	cd backend && uv sync
dev:         ## Run API with hot reload
	cd backend && uv run uvicorn life200.main:app --reload
test:
	cd backend && uv run pytest
lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
fmt:
	cd backend && uv run ruff check --fix . && uv run ruff format .
typecheck:
	cd backend && uv run mypy src
check: lint typecheck test   ## What CI runs
