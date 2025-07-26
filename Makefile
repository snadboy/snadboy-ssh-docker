# Makefile for snadboy-ssh-docker

.PHONY: help install install-dev test test-unit test-integration test-slow clean lint format type-check coverage

help:  ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in production mode
	pip install -e .

install-dev:  ## Install package with development dependencies
	pip install -e ".[dev]"

test:  ## Run all tests
	pytest

test-unit:  ## Run only unit tests
	pytest tests/unit/ -v

test-integration:  ## Run only integration tests (requires Docker)
	pytest tests/integration/ -v -m integration

test-slow:  ## Run slow integration tests
	pytest tests/integration/ -v -m "integration and slow"

test-fast:  ## Run fast tests only (skip slow integration tests)
	pytest -m "not slow"

clean:  ## Clean up build artifacts and cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

lint:  ## Run linting with flake8
	flake8 src/ tests/

format:  ## Format code with black and isort
	black src/ tests/
	isort src/ tests/

type-check:  ## Run type checking with mypy
	mypy src/

coverage:  ## Run tests with coverage reporting
	pytest --cov=src/snadboy_ssh_docker --cov-report=html --cov-report=term-missing

coverage-xml:  ## Generate XML coverage report for CI
	pytest --cov=src/snadboy_ssh_docker --cov-report=xml

check:  ## Run all code quality checks
	$(MAKE) format
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test-fast

build:  ## Build distribution packages
	python -m build

publish-test:  ## Publish to test PyPI
	python -m twine upload --repository testpypi dist/*

publish:  ## Publish to PyPI
	python -m twine upload dist/*

docker-test:  ## Run tests in Docker environment
	docker-compose -f tests/fixtures/docker-compose.test.yml up --build --abort-on-container-exit

docker-clean:  ## Clean up Docker test environment
	docker-compose -f tests/fixtures/docker-compose.test.yml down -v
	docker-compose -f tests/fixtures/docker-compose.docker.yml down -v