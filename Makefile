.PHONY: help install dev dev-backend dev-frontend test lint typecheck ci-local seed seed-status seed-reset eval eval-mock eval-latest

help:
	@echo "StudyMate AI - common commands"
	@echo ""
	@echo "  install       install backend (uv sync) and frontend (pnpm install) deps"
	@echo "  dev           start backend and frontend concurrently (Ctrl-C stops both)"
	@echo "  dev-backend   start only the backend (uvicorn, port 8000)"
	@echo "  dev-frontend  start only the frontend (next dev, port 3000)"
	@echo "  test          run backend pytest"
	@echo "  lint          run ruff + ruff format check + frontend lint"
	@echo "  typecheck     run mypy + frontend typecheck"
	@echo "  ci-local      run the same checks CI runs"
	@echo "  seed          ingest data/raw/*.pdf into the RAG store"
	@echo "  seed-status   show chunk count in the RAG collection"
	@echo "  seed-reset    drop and recreate the RAG collection"
	@echo "  eval          run eval with real Anthropic + RAG (costs ~$$0.50)"
	@echo "  eval-mock     run eval with fake grader + retriever (no API)"
	@echo "  eval-latest   print latest history.csv row"

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

seed:
	cd backend && uv run python -m scripts.seed all

seed-status:
	cd backend && uv run python -m scripts.seed status

seed-reset:
	cd backend && uv run python -m scripts.seed reset

eval:
	cd backend && uv run python -m scripts.eval run

eval-mock:
	cd backend && uv run python -m scripts.eval mock

eval-latest:
	cd backend && uv run python -m scripts.eval show-latest

# Run both concurrently. Ctrl-C kills the make process which terminates children
# via the shell. The `wait` keeps make alive while children run.
dev:
	@echo "Starting backend (8000) and frontend (3000). Ctrl-C to stop both."
	@$(MAKE) -j2 dev-backend dev-frontend

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && pnpm lint

typecheck:
	cd backend && uv run mypy app tests
	cd frontend && pnpm typecheck

ci-local: lint typecheck test
	cd backend && uv run lint-imports --config .importlinter
	cd frontend && pnpm build
