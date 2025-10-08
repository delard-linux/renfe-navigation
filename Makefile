.PHONY: help install test test-verbose test-display test-cov test-html test-failed test-playwright test-playwright-one run clean

help:
	@echo "Comandos disponibles:"
	@echo "  make install            - Instalar dependencias"
	@echo "  make test               - Ejecutar todos los tests"
	@echo "  make test-verbose       - Ejecutar tests con salida detallada"
	@echo "  make test-display       - Ejecutar test con visualización de resultados"
	@echo "  make test-cov           - Ejecutar tests con reporte de cobertura"
	@echo "  make test-html          - Ejecutar tests con reporte HTML de cobertura"
	@echo "  make test-failed        - Re-ejecutar solo los tests que fallaron"
	@echo "  make test-playwright    - Ejecutar tests E2E con Playwright (navegador visible)"
	@echo "  make test-playwright-one - Ejecutar un solo test de Playwright"
	@echo "  make run                - Ejecutar el servidor FastAPI"
	@echo "  make clean              - Limpiar archivos temporales"

install:
	pip install -r requirements.txt
	python -m playwright install --with-deps

test:
	pytest

test-verbose:
	pytest -v

test-display:
	pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_display_results -v -s

test-cov:
	pytest --cov=app tests/ --cov-report=term-missing

test-html:
	pytest --cov=app tests/ --cov-report=html
	@echo "Reporte HTML generado en htmlcov/index.html"

test-failed:
	pytest --lf -v

test-playwright:
	pytest tests_playwright/ -v -s

test-playwright-one:
	pytest tests_playwright/test_search_flow.py::test_search_trains_flow_ourense_madrid -v -s

run:
	python -m app.main

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name test_results -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf responses/*.log 2>/dev/null || true

