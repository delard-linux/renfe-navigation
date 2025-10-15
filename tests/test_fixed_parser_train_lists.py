"""
Unit tests for Renfe train list parser using fixed fixtures.

Run: pytest tests/test_fixed_parser_train_lists.py -v
Or all tests: pytest tests/ -v
"""

import json
from pathlib import Path

import pytest

from app.parser import parse_train_list_html
from app.renfe import TrainModel


@pytest.fixture
def train_list_html():
    """Fixture that loads sample train list HTML"""
    fixture_file = Path(__file__).parent / "fixtures" / "train_list_sample.html"
    with open(fixture_file, "r", encoding="utf-8") as f:
        return f.read()


def test_parse_train_list_html_returns_trains(train_list_html):
    """Test that verifies trains are parsed correctly"""
    trains = parse_train_list_html(train_list_html)

    assert len(trains) > 0, "Must parse at least one train"
    assert isinstance(trains[0], TrainModel), "Must return TrainModel objects"


def test_parse_train_list_html_extracts_basic_info(train_list_html):
    """Test that verifies basic train information is extracted"""
    trains = parse_train_list_html(train_list_html)

    first_train = trains[0]

    # Verify basic information is extracted
    assert first_train.train_id != "", "Must have ID"
    assert first_train.service_type != "", "Must have service type"
    assert first_train.departure_time != "", "Must have departure time"
    assert first_train.arrival_time != "", "Must have arrival time"
    assert first_train.duration != "", "Duration must not be empty"
    assert first_train.price_from > 0, "Must have price"
    assert first_train.currency == "EUR", "Currency must be EUR"


def test_parse_train_list_html_extracts_fares(train_list_html):
    """Test that verifies fares are extracted correctly"""
    trains = parse_train_list_html(train_list_html)

    # Find a train with multiple fares (typically AVE)
    train_with_fares = None
    for train in trains:
        if len(train.fares) > 1:
            train_with_fares = train
            break

    assert train_with_fares is not None, (
        "There must be at least one train with multiple fares"
    )

    # Verify fare structure
    fare = train_with_fares.fares[0]
    assert fare.name != "", "Fare must have name"
    assert fare.price > 0, "Fare must have price"
    assert fare.currency == "EUR", "Currency must be EUR"
    assert fare.code is not None, "Fare must have code"
    assert len(fare.features) > 0, "Fare must have features"


def test_parse_train_list_html_extracts_badges(train_list_html):
    """Test that verifies badges are extracted correctly"""
    trains = parse_train_list_html(train_list_html)

    # Find a train with badges
    train_with_badges = None
    for train in trains:
        if len(train.badges) > 0:
            train_with_badges = train
            break

    assert train_with_badges is not None, "There must be at least one train with badges"
    assert isinstance(train_with_badges.badges, list), "Badges must be a list"
    assert len(train_with_badges.badges[0]) > 0, "Badges must not be empty"


def test_parse_train_list_html_extracts_accessibility(train_list_html):
    """Test that verifies accessibility and eco features are extracted"""
    trains = parse_train_list_html(train_list_html)

    # There must be at least one accessible train
    accessible_trains = [t for t in trains if t.accessible]
    assert len(accessible_trains) > 0, "There must be accessible trains"

    # There must be at least one eco-friendly train
    eco_trains = [t for t in trains if t.eco_friendly]
    assert len(eco_trains) > 0, "There must be eco-friendly trains"


def test_parse_train_list_html_service_types(train_list_html):
    """Test that verifies different service types are recognized"""
    trains = parse_train_list_html(train_list_html)

    service_types = {train.service_type for train in trains}

    # There must be multiple service types
    assert len(service_types) > 1, "There must be more than one service type"

    # Known Renfe types
    known_types = {"AVE", "AVLO", "ALVIA", "AVANT", "MD", "Intercity"}
    assert len(service_types & known_types) > 0, (
        "Must recognize known service types"
    )


def test_parse_train_list_html_price_range(train_list_html):
    """Test that verifies price range"""
    trains = parse_train_list_html(train_list_html)

    prices = [train.price_from for train in trains]

    assert min(prices) > 0, "Minimum price must be greater than 0"
    assert max(prices) > min(prices), "There must be price variation"


def test_parse_train_list_html_fare_features(train_list_html):
    """Test that verifies fares have detailed features"""
    trains = parse_train_list_html(train_list_html)

    # Find a fare with features
    all_features = []
    for train in trains:
        for fare in train.fares:
            all_features.extend(fare.features)

    assert len(all_features) > 0, "There must be features in fares"

    # Verify features are not empty
    non_empty_features = [f for f in all_features if f.strip()]
    assert len(non_empty_features) == len(all_features), (
        "Features must not be empty"
    )


def test_parse_train_list_html_json_serializable(train_list_html):
    """Test that verifies trains can be serialized to JSON"""
    trains = parse_train_list_html(train_list_html)

    # Try serializing the first train
    train_dict = trains[0].model_dump()
    json_str = json.dumps(train_dict, ensure_ascii=False)

    assert len(json_str) > 0, "Must be able to serialize to JSON"

    # Try deserializing
    parsed = json.loads(json_str)
    assert parsed["train_id"] == trains[0].train_id, (
        "Must keep data after serialization"
    )


# Main test that can be run directly to display results
def test_parse_train_list_html_display_results(train_list_html, capsys):
    """Test that parses and displays detailed results (only when run with -v)"""
    trains = parse_train_list_html(train_list_html)

    print(f"\n{'=' * 80}")
    print("PARSING RESULTS")
    print(f"{'=' * 80}\n")
    print(f"✓ Trains found: {len(trains)}\n")

    # Mostrar resumen del primer tren
    if trains:
        train = trains[0]
        print(f"Example - Train #{train.train_id}:")
        print(f"  Type:       {train.service_type}")
        print(f"  Departure:  {train.departure_time}")
        print(f"  Arrival:    {train.arrival_time}")
        print(f"  Duration:   {train.duration}")
        print(f"  Price:      {train.price_from} {train.currency}")
        print(f"  Fares:      {len(train.fares)}")
        print(f"  Accessible: {train.accessible}")
        print(f"  Eco:        {train.eco_friendly}")

        if train.fares:
            print(
                f"\n  First fare: {train.fares[0].name} - {train.fares[0].price} EUR"
            )  # noqa: F541

    # Statistics
    print(f"\n{'=' * 80}")
    print("STATISTICS")
    print(f"{'=' * 80}")
    print(f"Total trains:           {len(trains)}")
    print(f"Minimum price:          {min(t.price_from for t in trains)} EUR")
    print(f"Maximum price:          {max(t.price_from for t in trains)} EUR")

    service_types = {}
    for train in trains:
        service_types[train.service_type] = service_types.get(train.service_type, 0) + 1

    print("\nService types:")
    for service, count in service_types.items():
        print(f"  - {service}: {count} trains")

    total_fares = sum(len(t.fares) for t in trains)
    print(f"\nTotal fares:            {total_fares}")
    print(f"Average fares/train:    {total_fares / len(trains):.1f}")

    accessible_count = sum(1 for t in trains if t.accessible)
    eco_count = sum(1 for t in trains if t.eco_friendly)

    print(
        f"\nAccessible trains:      {accessible_count} ({accessible_count / len(trains) * 100:.1f}%)"
    )
    print(f"Eco-friendly trains:    {eco_count} ({eco_count / len(trains) * 100:.1f}%)")
    print(f"\n{'=' * 80}\n")

    # Final assertions
    assert len(trains) == 11, "Sample file must have 11 trains"
    assert total_fares > 0, "Fares must be parsed"


if __name__ == "__main__":
    # Allow direct execution for debugging
    pytest.main([__file__, "-v", "-s"])
