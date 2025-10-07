"""
Parser para extraer información de trenes desde el HTML de Renfe
"""

from typing import List
from bs4 import BeautifulSoup
import re
import logging

from .renfe import TrainModel, FareOption

logger = logging.getLogger(__name__)


def parse_train_list_html(html_content: str) -> List[TrainModel]:
    """
    Parsea el contenido HTML de una lista de trenes de Renfe (ida o vuelta)

    Args:
        html_content: Contenido HTML del div con clase "container box-target-principal"
                     que contiene la lista de trenes (puede ser ida o vuelta)

    Returns:
        Lista de objetos TrainModel con todos los detalles de cada tren
    """
    trains: List[TrainModel] = []

    try:
        soup = BeautifulSoup(html_content, "html.parser")

        # Buscar todas las filas de trenes
        train_rows = soup.find_all("div", class_="selectedTren", role="listitem")
        logger.info(f"[PARSER] Encontradas {len(train_rows)} filas de trenes")

        for i, row in enumerate(train_rows):
            try:
                # Extraer train_id del atributo id="tren_i_1"
                train_id_attr = row.get("id", "")
                train_id = (
                    train_id_attr.replace("tren_", "")
                    if train_id_attr
                    else f"unknown_{i}"
                )

                # Extraer tipo de servicio de la imagen del tren
                service_type = "Tren"
                img = row.find("img", alt=re.compile(r"Tipo de tren"))
                if img and img.get("alt"):
                    match = re.search(r"Tipo de tren\s+(\w+)", img["alt"])
                    if match:
                        service_type = match.group(1)

                # Extraer horarios de los h5
                departure_time = ""
                arrival_time = ""
                h5_elements = row.find_all("h5", {"aria-hidden": "true"})
                if len(h5_elements) >= 2:
                    departure_time = (
                        h5_elements[0].get_text(strip=True).replace(" h", "")
                    )
                    arrival_time = h5_elements[1].get_text(strip=True).replace(" h", "")

                # Extraer duración
                duration = ""
                duration_elem = row.find("span", class_="text-number")
                if duration_elem:
                    duration = duration_elem.get_text(strip=True)

                # Extraer precio mínimo
                price_from = 0.0
                precio_elem = row.find("span", class_="precio-final")
                if precio_elem and precio_elem.get("title"):
                    match = re.search(r"([\d,]+)", precio_elem["title"])
                    if match:
                        price_from = float(match.group(1).replace(",", "."))

                # Extraer badges (etiquetas especiales)
                badges = []
                badge_elements = row.find_all(
                    class_=["badge-amarillo-junto", "badge-azul-junto"]
                )
                badges = [
                    badge.get_text(strip=True)
                    for badge in badge_elements
                    if badge.get_text(strip=True)
                ]

                # Extraer tarifas disponibles
                fares = []
                # Las tarifas están en divs con múltiples clases, buscamos por la clase base
                fare_cards = row.find_all(
                    "div",
                    class_=lambda x: x
                    and "seleccion-resumen-bottom" in x
                    and "card" in x,
                )

                for j, fare_card in enumerate(fare_cards):
                    try:
                        # Nombre de la tarifa
                        fare_name = "Desconocida"
                        header = fare_card.find("div", class_="card-header")
                        if header:
                            # Buscar el span sin clase de precio
                            name_span = header.find(
                                "span", style=lambda x: x and "padding-right" in x
                            )
                            if name_span:
                                fare_name = name_span.get_text(strip=True)
                            else:
                                # Fallback: extraer texto antes del precio
                                header_text = header.get_text(strip=True)
                                # Separar por el símbolo € o números
                                match = re.match(r"^([^\d€]+)", header_text)
                                if match:
                                    fare_name = match.group(1).strip()

                        # Precio de la tarifa
                        fare_price = 0.0
                        if fare_card.get("data-precio-tarifa"):
                            fare_price = float(
                                fare_card["data-precio-tarifa"].replace(",", ".")
                            )

                        # Código de tarifa
                        fare_code = fare_card.get("data-cod-tarifa")
                        tp_enlace = fare_card.get("data-cod-tpenlacesilencio")

                        # Prestaciones/características
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
                        logger.warning(
                            f"[PARSER] Error extrayendo tarifa {j} del tren {train_id}: {e}"
                        )
                        continue

                # Verificar accesibilidad y eco-friendly
                accessible = False
                eco_friendly = False
                info_varios = row.find("div", class_="info-varios")
                if info_varios:
                    info_text = info_varios.get_text()
                    accessible = "Plaza H disponible" in info_text
                    eco_friendly = "Cero emisiones" in info_text

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
                logger.warning(f"[PARSER] Error extrayendo tren {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"[PARSER] Error parseando HTML: {e}")

    return trains
