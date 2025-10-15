"""
End-to-end tests for the complete train search flow.

These tests use Playwright to verify the real flow by navigating
Renfe's page, filling the form, and getting results.

NOTE: These tests run with a VISIBLE browser by default
      thanks to the configuration in conftest.py
"""

import pytest
import os

from app.renfe import search_trains_flow


@pytest.mark.asyncio
async def test_search_trains_flow_ourense_madrid(playwright_config):
    """
    Full flow test: Ourense -> Madrid (one way).

    Verifies:
    - Navigate to homepage
    - Accept cookies
    - Fill form
    - Successful search
    - Response saved
    """
    print("\n🚂 Test: Ourense -> Madrid (one way)")

    # Ejecutar el flujo (usará configuración de conftest.py)
    filepath = await search_trains_flow(
        origin="OURENSE",
        destination="MADRID",
        date_out="2025-10-14",
        date_return=None,
        adults=1,
        playwright=playwright_config,
    )

    # Assertions
    assert filepath is not None, "Flow must return a file path"
    assert os.path.exists(filepath), f"File must exist: {filepath}"
    assert "buscarTrenFlow.do.log" in filepath, (
        "File must have the correct name"
    )

    # Verify file is not empty
    file_size = os.path.getsize(filepath)
    assert file_size > 1000, (
        f"File must have content (size: {file_size} bytes)"
    )

    print(f"✅ Response saved: {filepath}")
    print(f"📊 Size: {file_size / 1024:.2f} KB")


@pytest.mark.asyncio
async def test_search_trains_flow_barcelona_madrid_roundtrip(playwright_config):
    """
    Full flow test: Barcelona -> Madrid (round trip).

    Verifies:
    - Fill with return date
    - Round trip search
    """
    print("\n🚂 Test: Barcelona -> Madrid (round trip)")

    filepath = await search_trains_flow(
        origin="BARCELONA",
        destination="MADRID",
        date_out="2025-10-20",
        date_return="2025-12-22",
        adults=2,
        playwright=playwright_config,
    )

    assert filepath is not None
    assert os.path.exists(filepath)
    assert "200" in filepath, "Must be successful response (200 code)"

    print(f"✅ Response saved: {filepath}")


@pytest.mark.asyncio
async def test_search_trains_flow_multiple_passengers(playwright_config):
    """
    Test with multiple passengers: Madrid -> Sevilla.

    Verifies:
    - Configure 4 passengers
    - Successful search
    """
    print("\n🚂 Test: Madrid -> Sevilla (4 passengers)")

    filepath = await search_trains_flow(
        origin="MADRID",
        destination="SEVILLA",
        date_out="2025-11-01",
        date_return=None,
        adults=4,
        playwright=playwright_config,
    )

    assert filepath is not None
    assert os.path.exists(filepath)

    print(f"✅ Response saved: {filepath}")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_search_trains_flow_valencia_alicante(playwright_config):
    """
    Additional test: Valencia -> Alicante.

    Marked as 'slow' for optional execution.
    """
    print("\n🚂 Test: Valencia -> Alicante")

    filepath = await search_trains_flow(
        origin="VALENCIA",
        destination="ALICANTE",
        date_out="2025-10-25",
        date_return=None,
        adults=1,
        playwright=playwright_config,
    )

    assert filepath is not None
    assert os.path.exists(filepath)

    print(f"✅ Response saved: {filepath}")


if __name__ == "__main__":
    # Allow running tests directly
    print("Running Playwright tests...")
    pytest.main([__file__, "-v", "-s"])
