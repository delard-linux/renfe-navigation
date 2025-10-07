from typing import List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import os

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

RENFE_SEARCH_URL = "https://venta.renfe.com/vol/buscarTren.do?Idioma=es&Pais=ES"
RESPONSES_DIR = os.path.join(os.path.dirname(__file__), "..", "responses")


class FareOption(BaseModel):
    """Tarifa individual de un tren"""

    name: str  # Básico, Elige, Elige Confort, Prémium, Básica
    price: float
    currency: str = "EUR"
    code: Optional[str] = None  # data-cod-tarifa
    tp_enlace: Optional[str] = None  # data-cod-tpenlacesilencio
    features: List[str] = []  # Lista de prestaciones


class TrainModel(BaseModel):
    """Tren individual con todas sus tarifas"""

    train_id: str  # ID del tren (e.g., "i_1")
    service_type: str  # AVE, AVLO, ALVIA, etc.
    departure_time: str  # Hora de salida (e.g., "06:24")
    arrival_time: str  # Hora de llegada (e.g., "08:49")
    duration: str  # Duración (e.g., "2 horas 25 minutos")
    price_from: float  # Precio mínimo
    currency: str = "EUR"
    fares: List[FareOption] = []  # Lista de tarifas disponibles
    badges: List[str] = []  # Etiquetas (Precio más bajo, Más rápido, etc.)
    accessible: bool = False  # Plaza H disponible
    eco_friendly: bool = False  # Cero emisiones


def _ensure_responses_dir():
    """Crea el directorio responses si no existe"""
    os.makedirs(RESPONSES_DIR, exist_ok=True)


def _save_response(content: str, status_code: int = 200):
    """Guarda la respuesta HTML con el formato [AAMMDD_HH24MISS]_[Status code]_buscarTren.do.log"""
    _ensure_responses_dir()
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_{status_code}_buscarTren.do.log"
    filepath = os.path.join(RESPONSES_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[SCRAPER] Respuesta guardada en: {filename}")
        return filepath
    except Exception as e:
        logger.error(f"[SCRAPER] Error guardando respuesta: {e}")
        return None


def _load_stations():
    """Carga el catálogo de estaciones desde el JSON"""
    stations_path = os.path.join(
        os.path.dirname(__file__), "resources", "estaciones.json"
    )
    try:
        with open(stations_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"No se pudo cargar estaciones.json: {e}")
        return []


def _find_station(station_name: str) -> dict:
    """Busca una estación por nombre en el catálogo"""
    stations = _load_stations()
    station_upper = station_name.upper()

    # Buscar coincidencia exacta primero
    for station in stations:
        if station.get("desgEstacionPlano", "").upper() == station_upper:
            return station
        if station.get("cdgoEstacion", "").upper() == station_upper:
            return station

    # Buscar coincidencia parcial
    for station in stations:
        plano = station.get("desgEstacionPlano", "").upper()
        if station_upper in plano or plano.startswith(station_upper):
            return station

    # Si no se encuentra, devolver datos genéricos
    logger.warning(
        f"Estación '{station_name}' no encontrada en catálogo, usando búsqueda genérica"
    )
    return {
        "cdgoEstacion": station_name.upper()[:5],
        "cdgoAdmon": "0071",
        "desgEstacion": station_name.upper(),
        "clave": f"0071,{station_name.upper()[:5]},null",
    }


async def _extract_results(page) -> List[TrainModel]:
    """Extrae los trenes con todas sus tarifas del HTML de Renfe"""
    trains: List[TrainModel] = []
    logger.info("[SCRAPER] Esperando carga de resultados...")
    await page.wait_for_load_state("networkidle")

    # Buscar el contenedor principal con ID listaTrenesTBodyIda o listaTrenesTBodyVuelta
    train_rows = page.locator("div.row.selectedTren")
    count = await train_rows.count()
    logger.info(f"[SCRAPER] Extrayendo datos de {count} trenes encontrados")

    import re

    for i in range(count):
        row = train_rows.nth(i)
        try:
            # Extraer train_id del atributo id="tren_i_1"
            train_id_attr = await row.get_attribute("id")
            train_id = (
                train_id_attr.replace("tren_", "") if train_id_attr else f"unknown_{i}"
            )

            # Extraer tipo de servicio de la imagen del tren
            service_type = "Tren"
            try:
                img_alt = (
                    await row.locator('img[alt*="Tipo de tren"]')
                    .first()
                    .get_attribute("alt")
                )
                if img_alt:
                    # Extraer el tipo del alt: "Imagen de Tren. Tipo de tren AVE"
                    match = re.search(r"Tipo de tren\s+(\w+)", img_alt)
                    if match:
                        service_type = match.group(1)
            except Exception:
                pass

            # Extraer horarios de los h5
            departure_time = ""
            arrival_time = ""
            try:
                times = await row.locator('h5[aria-hidden="true"]').all_text_content()
                if len(times) >= 2:
                    departure_time = times[0].replace(" h", "").strip()
                    arrival_time = times[1].replace(" h", "").strip()
            except Exception:
                pass

            # Extraer duración
            duration = ""
            try:
                duration_text = await row.locator(".text-number").first().text_content()
                if duration_text:
                    duration = duration_text.strip()
            except Exception:
                pass

            # Extraer precio mínimo
            price_from = 0.0
            try:
                price_text = (
                    await row.locator(".precio-final").first().get_attribute("title")
                )
                if price_text:
                    # "Precio desde 49,00"
                    match = re.search(r"([\d,]+)", price_text)
                    if match:
                        price_from = float(match.group(1).replace(",", "."))
            except Exception:
                pass

            # Extraer badges (etiquetas especiales)
            badges = []
            try:
                badge_elements = await row.locator(
                    ".badge-amarillo-junto, .badge-azul-junto"
                ).all_text_content()
                badges = [b.strip() for b in badge_elements if b.strip()]
            except Exception:
                pass

            # Extraer tarifas disponibles
            fares = []
            try:
                fare_cards = row.locator(".seleccion-resumen-bottom.card")
                fare_count = await fare_cards.count()

                for j in range(fare_count):
                    fare_card = fare_cards.nth(j)
                    try:
                        # Nombre de la tarifa
                        fare_name_elem = (
                            await fare_card.locator(".card-header")
                            .first()
                            .text_content()
                        )
                        fare_name_parts = fare_name_elem.split()
                        fare_name = (
                            fare_name_parts[0] if fare_name_parts else "Desconocida"
                        )

                        # Precio de la tarifa
                        fare_price = 0.0
                        try:
                            fare_price_attr = await fare_card.get_attribute(
                                "data-precio-tarifa"
                            )
                            if fare_price_attr:
                                fare_price = float(fare_price_attr.replace(",", "."))
                        except Exception:
                            pass

                        # Código de tarifa
                        fare_code = await fare_card.get_attribute("data-cod-tarifa")
                        tp_enlace = await fare_card.get_attribute(
                            "data-cod-tpenlacesilencio"
                        )

                        # Prestaciones/características
                        features = []
                        try:
                            feature_items = await fare_card.locator(
                                ".lista-opciones li"
                            ).all_text_content()
                            features = [f.strip() for f in feature_items if f.strip()]
                        except Exception:
                            pass

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
                            f"[SCRAPER] Error extrayendo tarifa {j} del tren {train_id}: {e}"
                        )
                        continue
            except Exception as e:
                logger.warning(
                    f"[SCRAPER] Error extrayendo tarifas del tren {train_id}: {e}"
                )

            # Verificar accesibilidad y eco-friendly
            accessible = False
            eco_friendly = False
            try:
                info_varios = await row.locator(".info-varios").first().text_content()
                if info_varios:
                    accessible = "Plaza H disponible" in info_varios
                    eco_friendly = "Cero emisiones" in info_varios
            except Exception:
                pass

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
            logger.warning(f"[SCRAPER] Error extrayendo tren {i}: {e}")
            continue

    return trains


async def search_trains(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> Tuple[List[TrainModel], Optional[List[TrainModel]]]:
    logger.info("[SCRAPER] Iniciando navegador Chromium")

    # Buscar estaciones en el catálogo
    origin_station = _find_station(origin)
    dest_station = _find_station(destination)

    logger.info(
        f"[SCRAPER] Origen: {origin_station.get('desgEstacion', origin)} - Clave: {origin_station.get('clave')}"
    )
    logger.info(
        f"[SCRAPER] Destino: {dest_station.get('desgEstacion', destination)} - Clave: {dest_station.get('clave')}"
    )

    # Convertir fechas de YYYY-MM-DD a DD/MM/YYYY
    date_out_obj = datetime.strptime(date_out, "%Y-%m-%d")
    date_out_formatted = date_out_obj.strftime("%d/%m/%Y")

    date_return_formatted = ""
    if date_return:
        date_return_obj = datetime.strptime(date_return, "%Y-%m-%d")
        date_return_formatted = date_return_obj.strftime("%d/%m/%Y")

    # Construir form data
    form_data = {
        "tipoBusqueda": "autocomplete",
        "currenLocation": "menuBusqueda",
        "vengoderenfecom": "SI",
        "desOrigen": origin_station.get("desgEstacion", origin),
        "desDestino": dest_station.get("desgEstacion", destination),
        "cdgoOrigen": origin_station.get("clave", f"0071,{origin},null"),
        "cdgoDestino": dest_station.get("clave", f"0071,{destination},null"),
        "idiomaBusqueda": "ES",
        "FechaIdaSel": date_out_formatted,
        "FechaVueltaSel": date_return_formatted if date_return else "",
        "_fechaIdaVisual": date_out_formatted,
        "_fechaVueltaVisual": date_return_formatted if date_return else "",
        "minPriceDeparture": "false",
        "minPriceReturn": "false",
        "adultos_": str(adults),
        "ninos_": "0",
        "ninosMenores": "0",
        "codPromocional": "",
        "plazaH": "false",
        "sinEnlace": "false",
        "conMascota": "false",
        "conBicicleta": "false",
        "asistencia": "false",
        "franjaHoraI": "",
        "franjaHoraV": "",
        "Idioma": "es",
        "Pais": "ES",
    }

    logger.info(
        f"[SCRAPER] Parámetros de búsqueda: {date_out_formatted} -> {date_return_formatted if date_return else 'Solo ida'}"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES")
        page = await context.new_page()

        logger.info(f"[SCRAPER] Enviando POST a {RENFE_SEARCH_URL}")

        # Navegar directamente con POST
        await page.goto(RENFE_SEARCH_URL, wait_until="domcontentloaded")

        # Enviar el formulario con JavaScript
        await page.evaluate(f"""
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '{RENFE_SEARCH_URL}';
            
            const params = {json.dumps(form_data)};
            for (const [key, value] of Object.entries(params)) {{
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = key;
                input.value = value;
                form.appendChild(input);
            }}
            
            document.body.appendChild(form);
            form.submit();
        """)

        logger.info("[SCRAPER] Esperando respuesta del servidor...")
        await page.wait_for_load_state("networkidle", timeout=30000)

        # Guardar la respuesta HTML
        response_content = await page.content()
        _save_response(response_content, status_code=200)

        logger.info("[SCRAPER] Extrayendo resultados de ida")
        trains_out = await _extract_results(page)
        trains_ret: Optional[List[TrainModel]] = None

        if date_return and trains_out:
            try:
                # Intentar buscar pestaña o sección de vuelta
                logger.info("[SCRAPER] Buscando resultados de vuelta")
                vuelta_tab = page.locator(
                    '[id*="vuelta"], [class*="vuelta"], a:has-text("Vuelta")'
                )
                if await vuelta_tab.count() > 0:
                    await vuelta_tab.first().click()
                    await page.wait_for_timeout(500)
                    logger.info("[SCRAPER] Extrayendo resultados de vuelta")
                    trains_ret = await _extract_results(page)
            except Exception as e:
                logger.warning(
                    f"[SCRAPER] No se pudieron extraer trenes de vuelta: {e}"
                )
                trains_ret = None

        logger.info("[SCRAPER] Cerrando navegador")
        await context.close()
        await browser.close()

        return trains_out, trains_ret
