"""
Configuración de Playwright para tests end-to-end.

Establece configuraciones globales para pruebas de navegador:
- headless: Por defecto True, se puede cambiar con PLAYWRIGHT_HEADLESS=false
- slowmo: Ralentización de acciones para debug
- screenshots: Capturas automáticas en fallos
- videos: Grabación de videos de tests
"""

import os

# Configuración global de Playwright
PLAYWRIGHT_CONFIG = {
    # Modo headless: True por defecto, False para debug visual
    "headless": os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false",
    # Ralentización de acciones en milisegundos (útil para debug)
    "slow_mo": int(os.getenv("PLAYWRIGHT_SLOWMO", "0")),
    # Timeout global para operaciones (en milisegundos)
    "timeout": int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000")),
    # Directorio para screenshots
    "screenshot_dir": "test_results/screenshots",
    # Directorio para videos
    "video_dir": "test_results/videos",
    # Capturar screenshot en fallo
    "screenshot_on_failure": True,
    # Grabar video de tests
    "record_video": os.getenv("PLAYWRIGHT_VIDEO", "false").lower() == "true",
    # Viewport size
    "viewport": {
        "width": int(os.getenv("PLAYWRIGHT_WIDTH", "2560")),
        "height": int(os.getenv("PLAYWRIGHT_HEIGHT", "1440")),
    },
}


def get_browser_options():
    """Retorna las opciones de configuración del navegador para Playwright."""
    return {
        "headless": PLAYWRIGHT_CONFIG["headless"],
        "slow_mo": PLAYWRIGHT_CONFIG["slow_mo"],
    }


def get_context_options():
    """Retorna las opciones de contexto del navegador."""
    options = {
        "viewport": PLAYWRIGHT_CONFIG["viewport"],
    }

    if PLAYWRIGHT_CONFIG["record_video"]:
        options["record_video_dir"] = PLAYWRIGHT_CONFIG["video_dir"]

    return options
