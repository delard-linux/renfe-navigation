.PHONY: help test test-verbose test-display test-cov test-html test-failed test-playwright test-playwright-one run clean

help:
	@echo "Available commands:"
	@echo "  make test               - Run all tests"
	@echo "  make test-verbose       - Run tests with detailed output"
	@echo "  make test-display       - Run test with result visualization"
	@echo "  make test-cov           - Run tests with coverage report"
	@echo "  make test-html          - Run tests with HTML coverage report"
	@echo "  make test-failed        - Re-run only failed tests"
	@echo "  make test-playwright    - Run E2E tests with Playwright (visible browser)"
	@echo "  make test-playwright-one - Run a single Playwright test"
	@echo "  make run                - Run the FastAPI server"
	@echo "  make clean              - Clean temporary files"

test:
	poetry run pytest

test-verbose:
	poetry run pytest -v

test-display:
	poetry run pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_display_results -v -s

test-cov:
	poetry run pytest --cov=app tests/ --cov-report=term-missing

test-html:
	poetry run pytest --cov=app tests/ --cov-report=html
	@echo "Reporte HTML generado en htmlcov/index.html"

test-failed:
	poetry run pytest --lf -v

test-playwright:
	poetry run pytest tests_playwright/ -v -s

test-playwright-onetrip:
	poetry run pytest tests_playwright/test_search_flow.py::test_search_trains_flow_ourense_madrid -v -s

test-playwright-roundtrip:
	poetry run pytest tests_playwright/test_search_flow.py::test_search_trains_flow_barcelona_madrid_roundtrip -v -s

run:
	poetry run python -m app.main

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name test_results -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf responses/*.* 2>/dev/null || true

