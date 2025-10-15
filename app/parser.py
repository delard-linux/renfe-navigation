"""
Parser to extract train information from Renfe HTML.
"""

from typing import List
from bs4 import BeautifulSoup
import re
import logging

from .renfe_common import TrainModel, FareOption

logger = logging.getLogger(__name__)


def parse_train_list_html(html_content: str) -> List[TrainModel]:
    """
    Parse the HTML content of a Renfe train list (outbound or return).

    Args:
        html_content: HTML content of the container that holds the train list.

    Returns:
        List of TrainModel objects with full details for each train.
    """
    trains: List[TrainModel] = []

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Find all train rows
        train_rows = soup.find_all("div", class_="selectedTren", role="listitem")
        logger.info(f"[PARSER] Found {len(train_rows)} train rows")

        for i, row in enumerate(train_rows):
            try:
                # Extract train_id from attribute id="tren_i_1"
                train_id_attr = row.get("id", "")
                train_id = (
                    train_id_attr.replace("tren_", "")
                    if train_id_attr
                    else f"unknown_{i}"
                )

                # Extract service type from train image alt text
                service_type = "Train"
                img = row.find("img", alt=re.compile(r"Tipo de tren"))
                if img and img.get("alt"):
                    match = re.search(r"Tipo de tren\s+(\w+)", img["alt"])
                    if match:
                        service_type = match.group(1)

                # Extract times from h5 elements
                departure_time = ""
                arrival_time = ""
                h5_elements = row.find_all("h5", {"aria-hidden": "true"})
                if len(h5_elements) >= 2:
                    departure_time = (
                        h5_elements[0].get_text(strip=True).replace(" h", "")
                    )
                    arrival_time = h5_elements[1].get_text(strip=True).replace(" h", "")

                # Extract duration
                duration = ""
                duration_elem = row.find("span", class_="text-number")
                if duration_elem:
                    duration = duration_elem.get_text(strip=True)

                # Extract minimum price
                price_from = 0.0
                precio_elem = row.find("span", class_="precio-final")
                if precio_elem and precio_elem.get("title"):
                    match = re.search(r"([\d,]+)", precio_elem["title"])
                    if match:
                        price_from = float(match.group(1).replace(",", "."))

                # Extract badges (special labels)
                badges = []
                badge_elements = row.find_all(
                    class_=["badge-amarillo-junto", "badge-azul-junto"]
                )
                badges = [
                    badge.get_text(strip=True)
                    for badge in badge_elements
                    if badge.get_text(strip=True)
                ]

                # Extract available fares
                fares = []
                # Fares live in cards; match by base class
                fare_cards = row.find_all(
                    "div",
                    class_=lambda x: x
                    and "seleccion-resumen-bottom" in x
                    and "card" in x,
                )

                for j, fare_card in enumerate(fare_cards):
                    try:
                        # Fare name
                        fare_name = "Desconocida"
                        header = fare_card.find("div", class_="card-header")
                        if header:
                            # Find the span that excludes the price
                            name_span = header.find(
                                "span", style=lambda x: x and "padding-right" in x
                            )
                            if name_span:
                                fare_name = name_span.get_text(strip=True)
                            else:
                                # Fallback: extract text before the price
                                header_text = header.get_text(strip=True)
                                # Separar por el símbolo € o números
                                match = re.match(r"^([^\d€]+)", header_text)
                                if match:
                                    fare_name = match.group(1).strip()

                        # Fare price
                        fare_price = 0.0
                        if fare_card.get("data-precio-tarifa"):
                            fare_price = float(
                                fare_card["data-precio-tarifa"].replace(",", ".")
                            )

                        # Fare code
                        fare_code = fare_card.get("data-cod-tarifa")
                        tp_enlace = fare_card.get("data-cod-tpenlacesilencio")

                        # Features / amenities
                        features = []
                        feature_items = fare_card.find_all("li")
                        features = [
                            li.get_text(strip=True)
                            for li in feature_items
                            if li.get_text(strip=True)
                        ]

                        fares.append(
                            FareOption(
                                name=fare_name,
                                price=fare_price,
                                currency="EUR",
                                code=fare_code,
                                tp_enlace=tp_enlace,
                                features=features,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"[PARSER] Error extracting fare {j} for train {train_id}: {e}")
                        continue

                # Check accessibility and eco-friendly flags
                accessible = False
                eco_friendly = False
                info_varios = row.find("div", class_="info-varios")
                if info_varios:
                    info_text = info_varios.get_text()
                    accessible = "Plaza H disponible" in info_text  # leave Spanish literal (source content)
                    eco_friendly = "Cero emisiones" in info_text    # leave Spanish literal (source content)

                trains.append(
                    TrainModel(
                        train_id=train_id,
                        service_type=service_type,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        duration=duration,
                        price_from=price_from,
                        currency="EUR",
                        fares=fares,
                        badges=badges,
                        accessible=accessible,
                        eco_friendly=eco_friendly,
                    )
                )

            except Exception as e:
                logger.warning(f"[PARSER] Error extracting train {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"[PARSER] Error parsing HTML: {e}")

    return trains
