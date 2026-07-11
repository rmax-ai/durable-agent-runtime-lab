.PHONY: help install dev-install format lint type-check test test-all test-unit test-integration clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync

dev-install: ## Install including dev dependencies
	uv sync --extra dev

format: ## Format code with ruff
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

lint: ## Lint with ruff
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

type-check: ## Type check with mypy
	uv run mypy src/

test: ## Run unit tests
	uv run pytest tests/unit/ -v

test-all: ## Run all tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests
	uv run pytest tests/integration/ -v -m "not docker"

test-property: ## Run property-based tests
	uv run pytest tests/property/ -v

test-recovery: ## Run recovery tests
	uv run pytest tests/recovery/ -v

test-security: ## Run security tests
	uv run pytest tests/security/ -v

test-experiments: ## Run experiment tests
	uv run pytest tests/experiments/ -v

test-cov: ## Run tests with coverage
	uv run pytest tests/ --cov --cov-report=term-missing --cov-report=html

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
