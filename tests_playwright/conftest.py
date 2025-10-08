"""
Configuración de pytest para tests de Playwright.

Este archivo configura pytest específicamente para tests end-to-end
que usan Playwright, habilitando el modo debug por defecto.
"""

import pytest
import sys
import os

# Añadir directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Importar configuración de Playwright
import playwright_config as pw_config


@pytest.fixture(scope="session", autouse=True)
def configure_playwright_debug():
    """
    Fixture que configura Playwright en modo debug para estos tests.

    Se ejecuta automáticamente antes de todos los tests en esta carpeta.
    """
    # Activar modo debug (headless=False) para tests_playwright
    os.environ["PLAYWRIGHT_HEADLESS"] = "false"
    os.environ["PLAYWRIGHT_SLOWMO"] = "500"  # Ralentizar 500ms por acción

    print("\n" + "=" * 60)
    print("🎭 PLAYWRIGHT DEBUG MODE ACTIVADO")
    print("=" * 60)
    print("⚙️  headless: False (navegador visible)")
    print("⚙️  slow_mo: 500ms")
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
