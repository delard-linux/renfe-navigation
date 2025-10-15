"""
API endpoint tests using Renfe fixture responses

Run: pytest tests/test_api_endpoint.py -v
Or all tests: pytest tests/ -v
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def renfe_response_html():
    """Fixture that loads a real Renfe HTML response"""
    fixture_file = Path(__file__).parent / "fixtures" / "renfe_response_sample.html"
    with open(fixture_file, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def client():
    """Fixture that provides a FastAPI test client"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_endpoint_returns_train_list(client, renfe_response_html):
    """Test that verifies the endpoint returns a correct list of trains"""

    # Mock search_trains to avoid real calls to Renfe
    mock_trains = []
    from app.parser import parse_train_list_html

    # Parse fixture HTML to get real trains
    trains = parse_train_list_html(renfe_response_html)

    with patch("app.main.search_trains", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (trains, None)

        # Make request to endpoint
        response = client.get(
            "/trains",
            params={
                "origin": "OURENSE",
                "destination": "MADRID",
                "date_out": "2025-10-14",
                "adults": 1,
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Verify basic structure
        assert "origin" in data
        assert "destination" in data
        assert "trains_out" in data
        assert "trains_return" in data

        # Verify parameters
        assert data["origin"] == "OURENSE"
        assert data["destination"] == "MADRID"
        assert data["date_out"] == "2025-10-14"
        assert data["adults"] == 1

        # Verify there are trains
        assert isinstance(data["trains_out"], list)
        assert len(data["trains_out"]) > 0, "Must return at least one train"

        # Verify basic structure of a train
        first_train = data["trains_out"][0]
        assert "train_id" in first_train
        assert "service_type" in first_train
        assert "departure_time" in first_train
        assert "arrival_time" in first_train
        assert "duration" in first_train
        assert "price_from" in first_train
        assert "fares" in first_train


@pytest.mark.asyncio
async def test_endpoint_trains_count(client, renfe_response_html):
    """Test that verifies the number of parsed trains"""

    from app.parser import parse_train_list_html

    trains = parse_train_list_html(renfe_response_html)

    with patch("app.main.search_trains", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (trains, None)

        response = client.get(
            "/trains",
            params={
                "origin": "OURENSE",
                "destination": "MADRID",
                "date_out": "2025-10-14",
                "adults": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify that the number of trains matches the fixture
        assert len(data["trains_out"]) == len(trains)
        print(f"\nTrains found in endpoint: {len(data['trains_out'])}")


@pytest.mark.asyncio
async def test_endpoint_train_data_structure(client, renfe_response_html):
    """Test that verifies the train data structure"""

    from app.parser import parse_train_list_html

    trains = parse_train_list_html(renfe_response_html)

    with patch("app.main.search_trains", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (trains, None)

        response = client.get(
            "/trains",
            params={
                "origin": "OURENSE",
                "destination": "MADRID",
                "date_out": "2025-10-14",
                "adults": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all trains have required fields
        for train in data["trains_out"]:
            assert train["train_id"] != "", "train_id must not be empty"
            assert train["service_type"] != "", "service_type must not be empty"
            assert train["departure_time"] != "", "departure_time must not be empty"
            assert train["arrival_time"] != "", "arrival_time must not be empty"
            assert train["price_from"] > 0, "price_from must be greater than 0"
            assert isinstance(train["fares"], list), "fares must be a list"


@pytest.mark.asyncio
async def test_endpoint_with_return_date(client, renfe_response_html):
    """Test that verifies the endpoint with a return date"""

    from app.parser import parse_train_list_html

    trains_out = parse_train_list_html(renfe_response_html)
    trains_ret = parse_train_list_html(
        renfe_response_html
    )  # Same HTML for simplicity

    with patch("app.main.search_trains", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (trains_out, trains_ret)

        response = client.get(
            "/trains",
            params={
                "origin": "OURENSE",
                "destination": "MADRID",
                "date_out": "2025-10-14",
                "date_return": "2025-10-20",
                "adults": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["date_return"] == "2025-10-20"
        assert data["trains_return"] is not None
        assert isinstance(data["trains_return"], list)
        assert len(data["trains_return"]) > 0


@pytest.mark.asyncio
async def test_endpoint_validates_required_params(client):
    """Test that verifies validation of required parameters"""

    # Missing origin
    response = client.get(
        "/trains",
        params={
            "destination": "MADRID",
            "date_out": "2025-10-14",
            "adults": 1,
        },
    )
    assert response.status_code == 422  # Unprocessable Entity

    # Missing destination
    response = client.get(
        "/trains",
        params={
            "origin": "OURENSE",
            "date_out": "2025-10-14",
            "adults": 1,
        },
    )
    assert response.status_code == 422

    # Missing date_out
    response = client.get(
        "/trains",
        params={
            "origin": "OURENSE",
            "destination": "MADRID",
            "adults": 1,
        },
    )
    assert response.status_code == 422


if __name__ == "__main__":
    # Allow direct execution for debugging
    pytest.main([__file__, "-v", "-s"])
