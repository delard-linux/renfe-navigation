"""
Pytest configuration for Playwright tests.

This file configures pytest specifically for end-to-end tests
that use Playwright, enabling debug mode by default.
"""

import pytest
import os
import sys
import logging

# Configure logging for Playwright tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Force logging reconfiguration
)

# Standard Playwright configuration for all E2E tests
PLAYWRIGHT_CONFIG = {
    "headless": False,
    "viewport_width": 1920,
    "viewport_height": 1080,
    "slow_mo": 2000,
}


@pytest.fixture(scope="session", autouse=True)
def configure_playwright_debug():
    """
    Fixture that configures logging for Playwright tests.

    Runs automatically before all tests in this folder.
    """
    # Configure test-specific logging
    logger = logging.getLogger("app.renfe")
    logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    logger.propagate = False  # Avoid propagation to root logger

    # Add single console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    print("\n" + "=" * 60)
    print("🎭 PLAYWRIGHT DEBUG MODE ENABLED")
    print("=" * 60)
    print(f"⚙️  headless: {PLAYWRIGHT_CONFIG['headless']} ({'headless' if PLAYWRIGHT_CONFIG['headless'] else 'visible browser'})")
    print(f"⚙️  slow_mo: {PLAYWRRIGHT_CONFIG['slow_mo']}ms")
    print("⚙️  logging: INFO level enabled")
    print(f"⚙️  viewport: {PLAYWRIGHT_CONFIG['viewport_width']}x{PLAYWRIGHT_CONFIG['viewport_height']}")
    print("=" * 60 + "\n")


@pytest.fixture(scope="session")
def playwright_config():
    """
    Fixture that provides the complete Playwright configuration for tests.

    Returns:
        dict: Playwright configuration with headless, viewport and slow_mo
    """
    return PLAYWRIGHT_CONFIG.copy()
