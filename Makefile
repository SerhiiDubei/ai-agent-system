.PHONY: help install dev test test-int test-cov lint format type migrate migrate-create up down logs ps clean

# Default target
help:
	@echo "Targets:"
	@echo "  install      Install dev deps locally"
	@echo "  dev          Run app locally (assumes Postgres up)"
	@echo "  up           docker compose up (full stack)"
	@echo "  down         docker compose down"
	@echo "  logs         tail app logs"
	@echo "  ps           list compose services"
	@echo "  test         pytest unit tests only"
	@echo "  test-int     pytest з integration tests (Testcontainers)"
	@echo "  test-cov     full coverage report"
	@echo "  lint         ruff check"
	@echo "  format       ruff format"
	@echo "  type         mypy strict"
	@echo "  migrate      alembic upgrade head"
	@echo "  migrate-create m=NAME    alembic create migration"
	@echo "  clean        remove __pycache__ + caches"

install:
	pip install -e ".[dev,benchmark]"

dev:
	uvicorn ai_agent_system.main:app --reload --host 0.0.0.0 --port 8001

up:
	docker compose up -d --build

down:
	docker compose down

down-volumes:
	docker compose down -v  # ⚠️ wipes Postgres data

logs:
	docker compose logs -f app

ps:
	docker compose ps

test:
	pytest -m "not integration and not e2e and not slow"

test-int:
	pytest -m "integration"

test-cov:
	pytest --cov=ai_agent_system --cov-report=html --cov-report=term-missing

lint:
	ruff check src tests

format:
	ruff format src tests

type:
	mypy src

migrate:
	alembic upgrade head

migrate-create:
	@if [ -z "$(m)" ]; then echo "Usage: make migrate-create m='describe migration'"; exit 1; fi
	alembic revision --autogenerate -m "$(m)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
