.PHONY: dev test lint type-check format clean logs shell

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
