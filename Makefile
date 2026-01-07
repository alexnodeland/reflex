.PHONY: dev test lint type-check format clean logs shell ci

# CI - Emulate GitHub Actions pipeline locally
ci:
	@echo "=== Running CI Pipeline ==="
	@echo "\n--- Lint Check ---"
	python -m ruff check src tests
	@echo "\n--- Format Check ---"
	python -m ruff format --check src tests
	@echo "\n--- Type Check ---"
	python -m pyright src
	@echo "\n--- Tests ---"
	python -m pytest -v
	@echo "\n=== CI Pipeline Complete ==="

# Development
dev:
	docker compose up

dev-build:
	docker compose up --build

dev-down:
	docker compose down

logs:
	docker compose logs -f app

shell:
	docker compose exec app bash

db-shell:
	docker compose exec db psql -U reflex

# Testing
test:
	docker compose run --rm app pytest -v

test-cov:
	docker compose run --rm app pytest --cov=reflex --cov-report=html

# Code quality
lint:
	ruff check src tests

lint-fix:
	ruff check --fix src tests

format:
	ruff format src tests

type-check:
	pyright src

check: lint type-check test

# Database
migrate:
	docker compose run --rm app python scripts/migrate.py

# Utilities
replay:
	docker compose run --rm app python scripts/replay.py $(ARGS)

dlq:
	docker compose run --rm app python scripts/dlq.py

# Cleanup
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
