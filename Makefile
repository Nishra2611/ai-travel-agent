.PHONY: install dev test test-unit lint format hello-apis

install:
	poetry install

dev:
	poetry run uvicorn src.api.main:app --reload --port 8000

test:
	poetry run pytest tests/ -v --cov=src --cov-report=html

test-unit:
	poetry run pytest tests/unit/ -v

lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/

format:
	poetry run black src/ tests/
	poetry run ruff check --fix src/ tests/

hello-apis:
	poetry run python scripts/test_all_apis.py
