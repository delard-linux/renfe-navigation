.PHONY: help install test test-verbose test-display run clean

help:
	@echo "Comandos disponibles:"
	@echo "  make install       - Instalar dependencias"
	@echo "  make test          - Ejecutar todos los tests"
	@echo "  make test-verbose  - Ejecutar tests con salida detallada"
	@echo "  make test-display  - Ejecutar test con visualización de resultados"
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

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf responses/*.log 2>/dev/null || true

