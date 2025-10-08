"""
Configuración de pytest para tests de Playwright.

Este archivo configura pytest específicamente para tests end-to-end
que usan Playwright, habilitando el modo debug por defecto.
"""

import pytest
import sys
import os
import logging

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Importar configuración de Playwright
import playwright_config as pw_config

# Configurar logging para tests de Playwright
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Forzar reconfiguración del logging
)


@pytest.fixture(scope="session", autouse=True)
def configure_playwright_debug():
    """
    Fixture que configura Playwright en modo debug para estos tests.

    Se ejecuta automáticamente antes de todos los tests en esta carpeta.
    """
    # Activar modo debug (headless=False) para tests_playwright
    os.environ["PLAYWRIGHT_HEADLESS"] = "false"
    os.environ["PLAYWRIGHT_SLOWMO"] = "2000"  # Ralentizar 2000ms por acción

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
    print("⚙️  headless: False (navegador visible)")
    print("⚙️  slow_mo: 2000ms")
    print("⚙️  logging: INFO level activado")
    print(
        f"⚙️  viewport: {pw_config.PLAYWRIGHT_CONFIG['viewport']['width']}x{pw_config.PLAYWRIGHT_CONFIG['viewport']['height']}"
    )
    print("=" * 60 + "\n")

    yield

    # Cleanup después de los tests
    print("\n" + "=" * 60)
    print("✅ Tests de Playwright completados")
    print("=" * 60 + "\n")


@pytest.fixture(scope="session")
def playwright_viewport():
    """
    Fixture que proporciona la configuración de viewport para los tests.

    Returns:
        tuple: (width, height) del viewport configurado
    """
    return (
        pw_config.PLAYWRIGHT_CONFIG["viewport"]["width"],
        pw_config.PLAYWRIGHT_CONFIG["viewport"]["height"],
    )
