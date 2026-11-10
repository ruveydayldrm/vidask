.PHONY: help install dev api web test lint format eval eval-fast warmup up down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync --extra vision
	cd frontend && npm install

dev: ## Run API (:8000) and web (:3000) together
	$(MAKE) -j2 api web

api: ## Run the FastAPI backend with reload
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web: ## Run the Next.js frontend
	cd frontend && npm run dev

warmup: ## Pre-download embedding + reranker models
	cd backend && uv run python scripts/warmup.py

test: ## Backend + frontend tests
	cd backend && uv run pytest -q
	cd frontend && npm test

lint: ## Linters, formatters and type checks
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run typecheck

format: ## Auto-format everything
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

eval: ## Full evaluation (retrieval ablation + QA with LLM judge) → eval/results/
	cd backend && uv run python ../eval/run_eval.py

eval-fast: ## Retrieval ablation only (no LLM)
	cd backend && uv run python ../eval/run_eval.py --retrieval-only

up: ## docker compose up (CPU)
	docker compose up --build

down: ## Stop containers
	docker compose down
