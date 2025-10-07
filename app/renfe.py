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


class TrainModel(BaseModel):
    service: str
    departure: str
    arrival: str
    duration: str
    fare_from: Optional[float] = None
    currency: Optional[str] = None


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
    trains: List[TrainModel] = []
    logger.info("[SCRAPER] Esperando carga de resultados...")
    await page.wait_for_load_state("networkidle")

    # Intentar varios selectores para las tarjetas de tren
    cards = page.locator(
        '.trayecto-datos, .resultado-tren, [class*="trayecto"], [class*="resultado"]'
    )
    count = await cards.count()
    logger.info(f"[SCRAPER] Extrayendo datos de {count} trenes encontrados")

    for i in range(count):
        card = cards.nth(i)
        try:
            # Intentar extraer tipo de servicio
            service = "tren"
            try:
                service_elem = (
                    await card.locator('[class*="tipo"], [class*="servicio"]')
                    .first()
                    .text_content()
                )
                if service_elem:
                    service = service_elem.strip()
            except Exception:
                pass

            # Horarios
            dep = arr = ""
            try:
                times = await card.locator(
                    '[class*="hora"], time, [class*="salida"], [class*="llegada"]'
                ).all_text_content()
                if len(times) >= 2:
                    dep = times[0].strip()
                    arr = times[1].strip()
            except Exception:
                pass

            # Duración
            duration = ""
            try:
                duration_elem = (
                    await card.locator('[class*="duracion"], [class*="duration"]')
                    .first()
                    .text_content()
                )
                if duration_elem:
                    duration = duration_elem.strip()
            except Exception:
                pass

            # Precio
            fare = None
            currency = None
            try:
                price_text = (
                    await card.locator('[class*="precio"], [class*="price"], .importe')
                    .first()
                    .text_content()
                )
                if price_text and "€" in price_text:
                    currency = "EUR"
                    import re

                    txt = price_text.replace(" ", "").replace(",", ".")
                    m = re.search(r"(\d+\.?\d*)", txt)
                    if m:
                        fare = float(m.group(1))
            except Exception:
                pass

            trains.append(
                TrainModel(
                    service=service,
                    departure=dep,
                    arrival=arr,
                    duration=duration,
                    fare_from=fare,
                    currency=currency,
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
