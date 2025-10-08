"""
Tests end-to-end para el flujo completo de búsqueda de trenes.

Estos tests usan Playwright para verificar el flujo real navegando por
la página de Renfe, rellenando el formulario y obteniendo resultados.

NOTA: Estos tests se ejecutan con el navegador VISIBLE por defecto
      gracias a la configuración en conftest.py
"""

import pytest
import os
import sys

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.renfe import search_trains_flow


@pytest.mark.asyncio
async def test_search_trains_flow_ourense_madrid(playwright_viewport):
    """
    Test del flujo completo: Ourense -> Madrid (solo ida).

    Verifica:
    - Navegación a la página inicial
    - Aceptación de cookies
    - Rellenado de formulario
    - Búsqueda exitosa
    - Guardado de respuesta
    """
    print("\n🚂 Test: Ourense -> Madrid (solo ida)")

    width, height = playwright_viewport

    # Ejecutar el flujo (usará configuración de conftest.py)
    filepath = await search_trains_flow(
        origin="OURENSE",
        destination="MADRID",
        date_out="2025-10-14",
        date_return=None,
        adults=1,
        headless=False,  # Forzar visible en este test
        viewport_width=width,
        viewport_height=height,
    )

    # Verificaciones
    assert filepath is not None, "El flujo debe retornar una ruta de archivo"
    assert os.path.exists(filepath), f"El archivo debe existir: {filepath}"
    assert "buscarTrenFlow.do.log" in filepath, (
        "El archivo debe tener el nombre correcto"
    )

    # Verificar que el archivo no está vacío
    file_size = os.path.getsize(filepath)
    assert file_size > 1000, (
        f"El archivo debe tener contenido (size: {file_size} bytes)"
    )

    print(f"✅ Respuesta guardada: {filepath}")
    print(f"📊 Tamaño: {file_size / 1024:.2f} KB")


@pytest.mark.asyncio
async def test_search_trains_flow_barcelona_madrid_roundtrip(playwright_viewport):
    """
    Test del flujo completo: Barcelona -> Madrid (ida y vuelta).

    Verifica:
    - Rellenado con fecha de vuelta
    - Búsqueda de viaje redondo
    """
    print("\n🚂 Test: Barcelona -> Madrid (ida y vuelta)")

    width, height = playwright_viewport

    filepath = await search_trains_flow(
        origin="BARCELONA",
        destination="MADRID",
        date_out="2025-10-20",
        date_return="2025-11-22",
        adults=2,
        headless=False,
        viewport_width=width,
        viewport_height=height,
    )

    assert filepath is not None
    assert os.path.exists(filepath)
    assert "200" in filepath, "Debe ser respuesta exitosa (código 200)"

    print(f"✅ Respuesta guardada: {filepath}")


@pytest.mark.asyncio
async def test_search_trains_flow_multiple_passengers(playwright_viewport):
    """
    Test con múltiples pasajeros: Madrid -> Sevilla.

    Verifica:
    - Configuración de 4 pasajeros
    - Búsqueda exitosa
    """
    print("\n🚂 Test: Madrid -> Sevilla (4 pasajeros)")

    width, height = playwright_viewport

    filepath = await search_trains_flow(
        origin="MADRID",
        destination="SEVILLA",
        date_out="2025-11-01",
        date_return=None,
        adults=4,
        headless=False,
        viewport_width=width,
        viewport_height=height,
    )

    assert filepath is not None
    assert os.path.exists(filepath)

    print(f"✅ Respuesta guardada: {filepath}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_search_trains_flow_valencia_alicante(playwright_viewport):
    """
    Test adicional: Valencia -> Alicante.

    Marcado como 'slow' para ejecución opcional.
    """
    print("\n🚂 Test: Valencia -> Alicante")

    width, height = playwright_viewport

    filepath = await search_trains_flow(
        origin="VALENCIA",
        destination="ALICANTE",
        date_out="2025-10-25",
        date_return=None,
        adults=1,
        headless=False,
        viewport_width=width,
        viewport_height=height,
    )

    assert filepath is not None
    assert os.path.exists(filepath)

    print(f"✅ Respuesta guardada: {filepath}")


if __name__ == "__main__":
    # Permitir ejecutar tests directamente
    print("Ejecutando tests de Playwright...")
    pytest.main([__file__, "-v", "-s"])
