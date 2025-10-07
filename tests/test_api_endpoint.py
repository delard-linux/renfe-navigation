"""
Tests del endpoint de la API usando respuestas fixture de Renfe

Ejecutar con: pytest tests/test_api_endpoint.py -v
O todos los tests: pytest tests/ -v
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def renfe_response_html():
    """Fixture que carga una respuesta HTML real de Renfe"""
    fixture_file = Path(__file__).parent / "fixtures" / "renfe_response_sample.html"
    with open(fixture_file, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def client():
    """Fixture que proporciona un cliente de prueba de FastAPI"""
    return TestClient(app)


@pytest.mark.asyncio
async def test_endpoint_returns_train_list(client, renfe_response_html):
    """Test que verifica que el endpoint devuelve una lista de trenes correcta"""

    # Mock de search_trains para evitar llamadas reales a Renfe
    mock_trains = []
    from app.parser import parse_train_list_html

    # Parsear el HTML de fixture para obtener trenes reales
    trains = parse_train_list_html(renfe_response_html)

    with patch("app.main.search_trains", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = (trains, None)

        # Hacer la petición al endpoint
        response = client.get(
            "/trains",
            params={
                "origin": "OURENSE",
                "destination": "MADRID",
                "date_out": "2025-10-14",
                "adults": 1,
            },
        )

        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()

        # Verificar estructura básica
        assert "origin" in data
        assert "destination" in data
        assert "trains_out" in data
        assert "trains_return" in data

        # Verificar parámetros
        assert data["origin"] == "OURENSE"
        assert data["destination"] == "MADRID"
        assert data["date_out"] == "2025-10-14"
        assert data["adults"] == 1

        # Verificar que hay trenes
        assert isinstance(data["trains_out"], list)
        assert len(data["trains_out"]) > 0, "Debe devolver al menos un tren"

        # Verificar estructura básica de un tren
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
    """Test que verifica el número de trenes parseados"""

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

        # Verificar que el número de trenes coincide con el fixture
        assert len(data["trains_out"]) == len(trains)
        print(f"\nTrenes encontrados en el endpoint: {len(data['trains_out'])}")


@pytest.mark.asyncio
async def test_endpoint_train_data_structure(client, renfe_response_html):
    """Test que verifica la estructura de datos de los trenes"""

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

        # Verificar que todos los trenes tienen los campos requeridos
        for train in data["trains_out"]:
            assert train["train_id"] != "", "train_id no debe estar vacío"
            assert train["service_type"] != "", "service_type no debe estar vacío"
            assert train["departure_time"] != "", "departure_time no debe estar vacío"
            assert train["arrival_time"] != "", "arrival_time no debe estar vacío"
            assert train["price_from"] > 0, "price_from debe ser mayor que 0"
            assert isinstance(train["fares"], list), "fares debe ser una lista"


@pytest.mark.asyncio
async def test_endpoint_with_return_date(client, renfe_response_html):
    """Test que verifica el endpoint con fecha de vuelta"""

    from app.parser import parse_train_list_html

    trains_out = parse_train_list_html(renfe_response_html)
    trains_ret = parse_train_list_html(
        renfe_response_html
    )  # Mismo HTML para simplicidad

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
    """Test que verifica la validación de parámetros requeridos"""

    # Sin origen
    response = client.get(
        "/trains",
        params={
            "destination": "MADRID",
            "date_out": "2025-10-14",
            "adults": 1,
        },
    )
    assert response.status_code == 422  # Unprocessable Entity

    # Sin destino
    response = client.get(
        "/trains",
        params={
            "origin": "OURENSE",
            "date_out": "2025-10-14",
            "adults": 1,
        },
    )
    assert response.status_code == 422

    # Sin fecha
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
    # Permitir ejecución directa del test para debugging
    pytest.main([__file__, "-v", "-s"])
