"""
Configuración de pytest para tests de Playwright.

Este archivo configura pytest específicamente para tests end-to-end
que usan Playwright, habilitando el modo debug por defecto.
"""

import pytest
import os
import sys
import logging

# Configurar logging para tests de Playwright
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Forzar reconfiguración del logging
)

# Configuración estándar de Playwright para todos los tests E2E
PLAYWRIGHT_CONFIG = {
    "headless": False,
    "viewport_width": 1920,
    "viewport_height": 1080,
    "slow_mo": 2000,
}


@pytest.fixture(scope="session", autouse=True)
def configure_playwright_debug():
    """
    Fixture que configura el logging para tests de Playwright.

    Se ejecuta automáticamente antes de todos los tests en esta carpeta.
    """
    # Configurar logging específico para tests
    logger = logging.getLogger("app.renfe")
    logger.setLevel(logging.INFO)

    # Limpiar handlers existentes para evitar duplicados
    logger.handlers.clear()
    logger.propagate = False  # Evitar que se propague al logger raíz

    # Añadir handler único para consola
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    print("\n" + "=" * 60)
    print("🎭 PLAYWRIGHT DEBUG MODE ACTIVADO")
    print("=" * 60)
    print(f"⚙️  headless: {PLAYWRIGHT_CONFIG['headless']} ({'navegador oculto' if PLAYWRIGHT_CONFIG['headless'] else 'navegador visible'})")
    print(f"⚙️  slow_mo: {PLAYWRIGHT_CONFIG['slow_mo']}ms")
    print("⚙️  logging: INFO level activado")
    print(f"⚙️  viewport: {PLAYWRIGHT_CONFIG['viewport_width']}x{PLAYWRIGHT_CONFIG['viewport_height']}")
    print("=" * 60 + "\n")


@pytest.fixture(scope="session")
def playwright_config():
    """
    Fixture que proporciona la configuración completa de Playwright para los tests.

    Returns:
        dict: Configuración de Playwright con headless, viewport y slow_mo
    """
    return PLAYWRIGHT_CONFIG.copy()
