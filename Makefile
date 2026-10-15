PY ?= ./venv/bin/python

.PHONY: help data test lint format type-check run-api run-frontend check hooks

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

data: ## download and verify the large datasets (see data/MANIFEST.json)
	$(PY) scripts/fetch_data.py

test: ## Python tests, then frontend tests
	$(PY) -m pytest
	cd frontend && npm test

lint: ## ruff lint + format check, frontend eslint
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	cd frontend && npm run lint

format: ## apply ruff fixes and formatting
	$(PY) -m ruff check . --fix
	$(PY) -m ruff format .

type-check: ## frontend TypeScript check
	cd frontend && npm run type-check

check: lint type-check test ## everything CI runs

run-api: ## FastAPI on :8000 (from the repo root)
	$(PY) -m uvicorn backend.app.main:app --reload --port 8000

run-frontend: ## Vite dev server
	cd frontend && npm run dev

hooks: ## install the pre-commit hooks
	pre-commit install
