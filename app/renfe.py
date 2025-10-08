from typing import List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import os

from playwright.async_api import async_playwright
import importlib
import sys

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


# Helper para cargar el parser de forma robusta, evitando imports relativos
_def_parse_train_list_html = None


def _get_parse_train_list_html():
    global _def_parse_train_list_html
    if _def_parse_train_list_html is not None:
        return _def_parse_train_list_html

    # Asegurar que el directorio app esté en sys.path
    app_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(app_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # Intentar diferentes formas de importar el parser
    import_attempts = [
        "app.parser",  # Cuando se ejecuta desde el directorio raíz
        ".parser",  # Import relativo cuando se ejecuta como módulo
    ]

    errors = []
    for module_name in import_attempts:
        try:
            if module_name.startswith("."):
                # Para imports relativos, necesitamos especificar el package
                module = importlib.import_module(module_name, package="app")
            else:
                module = importlib.import_module(module_name)
            func = getattr(module, "parse_train_list_html", None)
            if callable(func):
                _def_parse_train_list_html = func
                logger.info(f"[IMPORT] Parser cargado desde: {module_name}")
                return _def_parse_train_list_html
        except Exception as e:
            errors.append(f"{module_name}: {e}")
            continue

    # Fallback: intentar importar directamente desde el archivo
    try:
        parser_path = os.path.join(os.path.dirname(__file__), "parser.py")
        if os.path.exists(parser_path):
            spec = importlib.util.spec_from_file_location("parser_module", parser_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            func = getattr(module, "parse_train_list_html", None)
            if callable(func):
                _def_parse_train_list_html = func
                logger.info(f"[IMPORT] Parser cargado desde archivo: {parser_path}")
                return _def_parse_train_list_html
    except Exception as e:
        errors.append(f"file_location: {e}")

    error_msg = (
        f"No se pudo importar parse_train_list_html. Intentos: {'; '.join(errors)}"
    )
    logger.error(f"[IMPORT] {error_msg}")
    raise ImportError(error_msg)


def _ensure_responses_dir():
    """Crea el directorio responses si no existe"""
    os.makedirs(RESPONSES_DIR, exist_ok=True)


def _save_response(
    content: str, status_code: int = 200, filename_suffix: str = "buscarTren.do.log"
):
    """Guarda la respuesta HTML con el formato [AAMMDD_HH24MISS]_[Status code]_[filename_suffix]"""
    _ensure_responses_dir()
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_{status_code}_{filename_suffix}"
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
    """Extrae el contenido HTML y lo parsea con el parser independiente testeado."""
    # Nota para mantenedores: Toda la lógica de parsing de HTML está centralizada
    # en app/parser.py (función parse_train_list_html). Este scraper solo obtiene
    # el HTML con Playwright y delega el análisis al parser probado por tests.
    logger.info("[SCRAPER] Esperando carga de resultados...")
    await page.wait_for_load_state("networkidle")
    html = await page.content()
    try:
        parse_train_list_html = _get_parse_train_list_html()
        trains = parse_train_list_html(html)
        logger.info(f"[SCRAPER] Trenes extraídos: {len(trains)}")
        return trains
    except Exception as e:
        logger.error(f"[SCRAPER] Error parseando HTML de resultados: {e}")
        return []


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


async def search_trains_flow(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> str:
    """Realiza el flujo completo desde la página inicial de Renfe hasta la búsqueda"""
    logger.info("[FLOW] Iniciando navegador Chromium desde página inicial")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navegar a la página inicial de Renfe
            logger.info("[FLOW] Navegando a página inicial de Renfe")
            await page.goto(
                "https://www.renfe.com/es/es", wait_until="domcontentloaded"
            )

            # Buscar estaciones en el catálogo
            origin_station = _find_station(origin)
            dest_station = _find_station(destination)

            logger.info(
                f"[FLOW] Origen: {origin_station.get('desgEstacion', origin)} - Clave: {origin_station.get('clave')}"
            )
            logger.info(
                f"[FLOW] Destino: {dest_station.get('desgEstacion', destination)} - Clave: {dest_station.get('clave')}"
            )

            # Convertir fechas de YYYY-MM-DD a DD/MM/YYYY
            date_out_obj = datetime.strptime(date_out, "%Y-%m-%d")
            date_out_formatted = date_out_obj.strftime("%d/%m/%Y")

            date_return_formatted = ""
            if date_return:
                date_return_obj = datetime.strptime(date_return, "%Y-%m-%d")
                date_return_formatted = date_return_obj.strftime("%d/%m/%Y")

            # Esperar a que cargue el formulario
            await page.wait_for_selector("#origin", timeout=10000)

            # Rellenar campo origen
            logger.info(f"[FLOW] Rellenando origen: {origin}")
            await page.fill("#origin", origin_station.get("desgEstacion", origin))
            await page.wait_for_timeout(500)

            # Rellenar campo destino
            logger.info(f"[FLOW] Rellenando destino: {destination}")
            await page.fill(
                "#destination", dest_station.get("desgEstacion", destination)
            )
            await page.wait_for_timeout(500)

            # Rellenar fecha de ida usando el date picker
            logger.info(
                f"[FLOW] Abriendo date picker para fecha ida: {date_out_formatted}"
            )
            await page.click("#first-input")
            await page.wait_for_timeout(1000)  # Esperar a que aparezca el calendario

            # Seleccionar la fecha en el date picker
            # Primero, verificar si necesitamos cambiar de mes
            logger.info("[FLOW] Seleccionando fecha de ida en el calendario")

            # Extraer día, mes y año de la fecha
            day_out = date_out_obj.day
            month_out = date_out_obj.month
            year_out = date_out_obj.year

            # Navegar hasta el mes correcto si es necesario
            # El calendario muestra el mes actual por defecto
            current_date = datetime.now()
            months_diff = (year_out - current_date.year) * 12 + (
                month_out - current_date.month
            )

            if months_diff > 0:
                # Hacer clic en el botón de siguiente mes las veces necesarias
                for _ in range(months_diff):
                    next_month_btn = (
                        page.locator("button[aria-label*='next']")
                        .or_(page.locator("button.rf-daterange-alternative__btn--next"))
                        .first
                    )
                    await next_month_btn.click()
                    await page.wait_for_timeout(300)

            # Hacer clic en el día específico
            # Buscar el día en el calendario que está visible
            try:
                # Intentar diferentes selectores para el día
                day_button = page.locator(f"td button:has-text('{day_out}')").first
                await day_button.click()
                await page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(
                    "[FLOW] No se pudo hacer clic en el día %d, intentando selector alternativo: %s",
                    day_out,
                    e,
                )
                # Alternativa: buscar por texto exacto
                day_button = page.locator("button").filter(has_text=str(day_out)).first
                await day_button.click()
                await page.wait_for_timeout(500)

            # Rellenar fecha de vuelta si existe
            if date_return_formatted:
                logger.info(
                    f"[FLOW] Abriendo date picker para fecha vuelta: {date_return_formatted}"
                )

                # Si ya está en modo "ida y vuelta", el calendario debería estar visible
                # Si no, hacer clic en el radio button de "Viaje de ida y vuelta"
                try:
                    return_radio = (
                        page.locator("input[value='roundtrip']")
                        .or_(page.locator("label:has-text('Viaje de ida y vuelta')"))
                        .first
                    )
                    await return_radio.click()
                    await page.wait_for_timeout(500)
                except Exception:
                    logger.info(
                        "[FLOW] Ya está en modo ida y vuelta o no se pudo cambiar"
                    )

                # Extraer día, mes y año de la fecha de vuelta
                day_return = date_return_obj.day
                month_return = date_return_obj.month
                year_return = date_return_obj.year

                # Navegar hasta el mes correcto para la vuelta
                months_diff_return = (year_return - year_out) * 12 + (
                    month_return - month_out
                )

                if months_diff_return > 0:
                    for _ in range(months_diff_return):
                        next_month_btn = (
                            page.locator("button[aria-label*='next']")
                            .or_(
                                page.locator(
                                    "button.rf-daterange-alternative__btn--next"
                                )
                            )
                            .first
                        )
                        await next_month_btn.click()
                        await page.wait_for_timeout(300)

                # Hacer clic en el día de vuelta
                try:
                    day_button_return = page.locator(
                        f"td button:has-text('{day_return}')"
                    ).last
                    await day_button_return.click()
                    await page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(
                        "[FLOW] No se pudo hacer clic en el día de vuelta %d: %s",
                        day_return,
                        e,
                    )
                    day_button_return = (
                        page.locator("button").filter(has_text=str(day_return)).last
                    )
                    await day_button_return.click()
                    await page.wait_for_timeout(500)

                # Hacer clic en el botón "Aceptar" del date picker
                logger.info("[FLOW] Confirmando selección de fechas")
                accept_btn = (
                    page.locator("button:has-text('Aceptar')")
                    .or_(page.locator("button.rf-daterange-alternative__btn-accept"))
                    .first
                )
                await accept_btn.click()
                await page.wait_for_timeout(500)

            # Configurar número de pasajeros
            logger.info(f"[FLOW] Configurando pasajeros: {adults}")
            # El campo de pasajeros puede no ser directamente editable, verificar
            try:
                await page.fill("#adultos_", str(adults))
            except Exception:
                logger.info(
                    "[FLOW] No se pudo rellenar pasajeros directamente, usando valor por defecto"
                )

            # Hacer clic en el botón de buscar
            logger.info("[FLOW] Haciendo clic en buscar billetes")
            search_button = page.locator("button[type='submit']").first
            await search_button.click()

            # Esperar a que cargue la página de resultados
            await page.wait_for_load_state("networkidle")

            # Obtener el contenido HTML de la página de resultados
            response_content = await page.content()

            # Guardar la respuesta con el formato específico
            filepath = _save_response(
                response_content,
                status_code=200,
                filename_suffix="buscarTrenFlow.do.log",
            )

            logger.info("[FLOW] Flujo completado exitosamente")
            return filepath

        except Exception as e:
            logger.error(f"[FLOW] Error en el flujo: {e}")
            # Intentar guardar la respuesta de error
            try:
                response_content = await page.content()
                _save_response(
                    response_content,
                    status_code=500,
                    filename_suffix="buscarTrenFlow.do.log",
                )
            except Exception:
                pass
            raise
        finally:
            logger.info("[FLOW] Cerrando navegador")
            await context.close()
            await browser.close()
