.PHONY: help install test test-verbose test-display test-cov test-html test-failed run clean

help:
	@echo "Comandos disponibles:"
	@echo "  make install       - Instalar dependencias"
	@echo "  make test          - Ejecutar todos los tests"
	@echo "  make test-verbose  - Ejecutar tests con salida detallada"
	@echo "  make test-display  - Ejecutar test con visualización de resultados"
	@echo "  make test-cov      - Ejecutar tests con reporte de cobertura"
	@echo "  make test-html     - Ejecutar tests con reporte HTML de cobertura"
	@echo "  make test-failed   - Re-ejecutar solo los tests que fallaron"
	@echo "  make run           - Ejecutar el servidor FastAPI"
	@echo "  make clean         - Limpiar archivos temporales"

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

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf responses/*.log 2>/dev/null || true

