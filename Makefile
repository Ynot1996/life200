WHAT ?= junior software engineer
WHERE ?= London
PAGES ?= 1

.PHONY: up down install dev app admin refresh sponsors migrate fetch test lint fmt typecheck check

up:          ## Start Postgres + Redis
	docker compose up -d
down:
	docker compose down
install:     ## Install backend deps
	cd backend && uv sync
dev:         ## Run API with hot reload
	cd backend && uv run uvicorn life200.main:app --reload
app:         ## Open the app in the browser (log in first)
	cd backend && uv run streamlit run src/life200/ui/app.py --server.address localhost
admin:       ## Create your login: make admin EMAIL=you@example.com
	cd backend && uv run python -m life200.cli admin "$(EMAIL)"
refresh:     ## Sponsor register + UK, Singapore, Japan, Taiwan searches + tagging
	cd backend && uv run python -m life200.cli refresh
sponsors:    ## Download the latest sponsor register
	cd backend && uv run python -m life200.cli sponsors
migrate:     ## Apply database migrations
	cd backend && uv run alembic upgrade head
fetch:       ## Fetch jobs from Adzuna. Override: make fetch WHAT="data analyst" PAGES=3
	cd backend && uv run python -m life200.cli fetch "$(WHAT)" --where "$(WHERE)" --pages $(PAGES)
test:
	cd backend && uv run pytest
lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
typecheck:
	cd backend && uv run mypy src
check: lint typecheck test   ## What CI runs
