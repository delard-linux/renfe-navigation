"""
Test unitario para el parser de trenes de Renfe

Ejecutar con: pytest tests/test_parser.py -v
O todos los tests: pytest tests/ -v
"""

import json
from pathlib import Path

import pytest

from app.parser import parse_train_list_html
from app.renfe import TrainModel


@pytest.fixture
def train_list_html():
    """Fixture que carga el HTML de ejemplo de lista de trenes"""
    fixture_file = Path(__file__).parent / "fixtures" / "train_list_sample.html"
    with open(fixture_file, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_train_list_html_returns_trains(train_list_html):
    """Test que verifica que se parsean trenes correctamente"""
    trains = parse_train_list_html(train_list_html)

    assert len(trains) > 0, "Debe parsear al menos un tren"
    assert isinstance(trains[0], TrainModel), "Debe devolver objetos TrainModel"


def test_parse_train_list_html_extracts_basic_info(train_list_html):
    """Test que verifica que se extrae la información básica de los trenes"""
    trains = parse_train_list_html(train_list_html)

    first_train = trains[0]

    # Verificar que se extrae la información básica
    assert first_train.train_id != "", "Debe tener ID"
    assert first_train.service_type != "", "Debe tener tipo de servicio"
    assert first_train.departure_time != "", "Debe tener hora de salida"
    assert first_train.arrival_time != "", "Debe tener hora de llegada"
    assert first_train.duration != "", "Debe tener duración"
    assert first_train.price_from > 0, "Debe tener precio"
    assert first_train.currency == "EUR", "La moneda debe ser EUR"


def test_parse_train_list_html_extracts_fares(train_list_html):
    """Test que verifica que se extraen las tarifas correctamente"""
    trains = parse_train_list_html(train_list_html)

    # Buscar un tren con múltiples tarifas (típicamente los AVE)
    train_with_fares = None
    for train in trains:
        if len(train.fares) > 1:
            train_with_fares = train
            break

    assert train_with_fares is not None, (
        "Debe haber al menos un tren con múltiples tarifas"
    )

    # Verificar estructura de tarifas
    fare = train_with_fares.fares[0]
    assert fare.name != "", "La tarifa debe tener nombre"
    assert fare.price > 0, "La tarifa debe tener precio"
    assert fare.currency == "EUR", "La moneda debe ser EUR"
    assert fare.code is not None, "La tarifa debe tener código"
    assert len(fare.features) > 0, "La tarifa debe tener prestaciones"


def test_parse_train_list_html_extracts_badges(train_list_html):
    """Test que verifica que se extraen los badges correctamente"""
    trains = parse_train_list_html(train_list_html)

    # Buscar un tren con badges
    train_with_badges = None
    for train in trains:
        if len(train.badges) > 0:
            train_with_badges = train
            break

    assert train_with_badges is not None, "Debe haber al menos un tren con badges"
    assert isinstance(train_with_badges.badges, list), "Los badges deben ser una lista"
    assert len(train_with_badges.badges[0]) > 0, "Los badges no deben estar vacíos"


def test_parse_train_list_html_extracts_accessibility(train_list_html):
    """Test que verifica que se extraen las características de accesibilidad y eco"""
    trains = parse_train_list_html(train_list_html)

    # Debe haber al menos un tren accesible
    accessible_trains = [t for t in trains if t.accessible]
    assert len(accessible_trains) > 0, "Debe haber trenes accesibles"

    # Debe haber al menos un tren eco-friendly
    eco_trains = [t for t in trains if t.eco_friendly]
    assert len(eco_trains) > 0, "Debe haber trenes eco-friendly"


def test_parse_train_list_html_service_types(train_list_html):
    """Test que verifica que se reconocen diferentes tipos de servicio"""
    trains = parse_train_list_html(train_list_html)

    service_types = {train.service_type for train in trains}

    # Debe haber múltiples tipos de servicio
    assert len(service_types) > 1, "Debe haber más de un tipo de servicio"

    # Tipos conocidos de Renfe
    known_types = {"AVE", "AVLO", "ALVIA", "AVANT", "MD", "Intercity"}
    assert len(service_types & known_types) > 0, (
        "Debe reconocer tipos de servicio conocidos"
    )


def test_parse_train_list_html_price_range(train_list_html):
    """Test que verifica el rango de precios"""
    trains = parse_train_list_html(train_list_html)

    prices = [train.price_from for train in trains]

    assert min(prices) > 0, "El precio mínimo debe ser mayor que 0"
    assert max(prices) > min(prices), "Debe haber variación en los precios"


def test_parse_train_list_html_fare_features(train_list_html):
    """Test que verifica que las tarifas tienen prestaciones detalladas"""
    trains = parse_train_list_html(train_list_html)

    # Encontrar una tarifa con features
    all_features = []
    for train in trains:
        for fare in train.fares:
            all_features.extend(fare.features)

    assert len(all_features) > 0, "Debe haber prestaciones en las tarifas"

    # Verificar que las features no están vacías
    non_empty_features = [f for f in all_features if f.strip()]
    assert len(non_empty_features) == len(all_features), (
        "Las features no deben estar vacías"
    )


def test_parse_train_list_html_json_serializable(train_list_html):
    """Test que verifica que los trenes se pueden serializar a JSON"""
    trains = parse_train_list_html(train_list_html)

    # Intentar serializar el primer tren
    train_dict = trains[0].model_dump()
    json_str = json.dumps(train_dict, ensure_ascii=False)

    assert len(json_str) > 0, "Debe poder serializar a JSON"

    # Intentar deserializar
    parsed = json.loads(json_str)
    assert parsed["train_id"] == trains[0].train_id, (
        "Debe mantener los datos al serializar"
    )


# Test principal que se puede ejecutar directamente para mostrar resultados
def test_parse_train_list_html_display_results(train_list_html, capsys):
    """Test que parsea y muestra resultados detallados (solo cuando se ejecuta con -v)"""
    trains = parse_train_list_html(train_list_html)

    print(f"\n{'=' * 80}")
    print("RESULTADOS DEL PARSING")
    print(f"{'=' * 80}\n")
    print(f"✓ Trenes encontrados: {len(trains)}\n")

    # Mostrar resumen del primer tren
    if trains:
        train = trains[0]
        print(f"Ejemplo - Tren #{train.train_id}:")
        print(f"  Tipo:       {train.service_type}")
        print(f"  Salida:     {train.departure_time}")
        print(f"  Llegada:    {train.arrival_time}")
        print(f"  Duración:   {train.duration}")
        print(f"  Precio:     {train.price_from} {train.currency}")
        print(f"  Tarifas:    {len(train.fares)}")
        print(f"  Accesible:  {train.accessible}")
        print(f"  Eco:        {train.eco_friendly}")

        if train.fares:
            print(
                f"\n  Primera tarifa: {train.fares[0].name} - {train.fares[0].price} EUR"
            )  # noqa: F541

    # Estadísticas
    print(f"\n{'=' * 80}")
    print("ESTADÍSTICAS")
    print(f"{'=' * 80}")
    print(f"Total trenes:           {len(trains)}")
    print(f"Precio mínimo:          {min(t.price_from for t in trains)} EUR")
    print(f"Precio máximo:          {max(t.price_from for t in trains)} EUR")

    service_types = {}
    for train in trains:
        service_types[train.service_type] = service_types.get(train.service_type, 0) + 1

    print("\nTipos de servicio:")
    for service, count in service_types.items():
        print(f"  - {service}: {count} trenes")

    total_fares = sum(len(t.fares) for t in trains)
    print(f"\nTotal tarifas:          {total_fares}")
    print(f"Promedio tarifas/tren:  {total_fares / len(trains):.1f}")

    accessible_count = sum(1 for t in trains if t.accessible)
    eco_count = sum(1 for t in trains if t.eco_friendly)

    print(
        f"\nTrenes accesibles:      {accessible_count} ({accessible_count / len(trains) * 100:.1f}%)"
    )
    print(f"Trenes eco-friendly:    {eco_count} ({eco_count / len(trains) * 100:.1f}%)")
    print(f"\n{'=' * 80}\n")

    # Aserciones finales
    assert len(trains) == 11, "El archivo de ejemplo debe tener 11 trenes"
    assert total_fares > 0, "Debe haber tarifas parseadas"


if __name__ == "__main__":
    # Permitir ejecución directa del test para debugging
    pytest.main([__file__, "-v", "-s"])
