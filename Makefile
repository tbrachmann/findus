# Makefile for findus development

.PHONY: help install test test-unit test-integration server clean

help:
	@echo "Available commands:"
	@echo "  install          - Install dependencies and set up project"
	@echo "  test             - Run complete test suite (unit + integration)"
	@echo "  test-unit        - Run unit tests only"
	@echo "  test-integration - Run Playwright integration tests only"
	@echo "  server           - Start development server"
	@echo "  migrate          - Run database migrations"
	@echo "  clean            - Clean up temporary files"

install:
	uv sync
	uv run playwright install chromium
	@echo "✅ Installation complete"

test:
	uv run python test_integration.py

test-unit:
	uv run python manage.py test

test-integration:
	uv run python playwright_integration_test.py

server:
	uv run python manage.py runserver

migrate:
	uv run python manage.py migrate

clean:
	rm -rf /tmp/playwright_screenshots/
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
