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
    headless: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 720,
) -> str:
    """
    Realiza el flujo completo desde la página inicial de Renfe hasta la búsqueda.

    Args:
        origin: Estación de origen
        destination: Estación de destino
        date_out: Fecha de ida (YYYY-MM-DD)
        date_return: Fecha de vuelta opcional (YYYY-MM-DD)
        adults: Número de pasajeros adultos
        headless: Si True, ejecuta sin interfaz gráfica
        viewport_width: Ancho del viewport
        viewport_height: Alto del viewport

    Returns:
        Ruta del archivo de respuesta guardado
    """
    logger.info("[FLOW] Iniciando navegador Chromium desde página inicial")

    async with async_playwright() as p:
        # Configurar args del navegador para modo visible
        browser_args = []
        if not headless:
            browser_args = [
                "--start-maximized",
                f"--window-size={viewport_width},{viewport_height}",
            ]

        browser = await p.chromium.launch(headless=headless, args=browser_args)

        # Configurar contexto con viewport
        context_options = {}
        if not headless:
            context_options = {
                "viewport": {"width": viewport_width, "height": viewport_height},
                "no_viewport": False,
            }

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        try:
            # Navegar a la página inicial de Renfe
            logger.info("[FLOW] Navegando a página inicial de Renfe")
            await page.goto(
                "https://www.renfe.com/es/es", wait_until="domcontentloaded"
            )

            # Esperar un momento para que cargue la página
            await page.wait_for_timeout(2000)

            # Aceptar cookies si aparece el popup
            logger.info("[FLOW] Verificando popup de cookies")
            try:
                # Intentar múltiples selectores para el botón de aceptar cookies
                cookie_selectors = [
                    "button#onetrust-accept-btn-handler",
                    "button.onetrust-close-btn-handler",
                    "button:has-text('Aceptar')",
                    "button:has-text('Aceptar todas')",
                    "button:has-text('Accept')",
                    ".cookies-banner button",
                    "#cookies-accept-btn",
                ]

                clicked_cookies = False
                for selector in cookie_selectors:
                    try:
                        cookie_btn = page.locator(selector).first
                        if await cookie_btn.is_visible(timeout=2000):
                            await cookie_btn.click()
                            await page.wait_for_timeout(1000)
                            logger.info(
                                f"[FLOW] Cookies aceptadas con selector: {selector}"
                            )
                            clicked_cookies = True
                            break
                    except Exception:
                        continue

                if not clicked_cookies:
                    logger.info(
                        "[FLOW] No se encontró popup de cookies o ya fue aceptado"
                    )
            except Exception as e:
                logger.warning(f"[FLOW] Error manejando cookies: {e}")

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

            # Interactuar con el date picker de Renfe correctamente
            logger.info(f"[FLOW] Configurando fecha de ida: {date_out_formatted}")

            try:
                # Hacer clic en el campo de fecha de ida para abrir el date picker
                await page.click("#first-input", timeout=5000)
                await page.wait_for_timeout(1000)

                # Usar JavaScript para establecer la fecha y disparar eventos
                await page.evaluate(f"""
                    const firstInput = document.querySelector('#first-input');
                    if (firstInput) {{
                        firstInput.value = '{date_out_formatted}';
                        firstInput.setAttribute('aria-label', 'Fecha ida {date_out_formatted}');
                        firstInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        firstInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        firstInput.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    }}
                    const fechaIdaField = document.querySelector('input[name="FechaIdaSel"]');
                    if (fechaIdaField) {{ fechaIdaField.value = '{date_out_formatted}'; }}
                """)

                await page.wait_for_timeout(500)

                # Cerrar el date picker presionando Escape
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)

                logger.info(f"[FLOW] Fecha de ida configurada: {date_out_formatted}")

                # Si hay fecha de vuelta, configurarla
                if date_return_formatted:
                    logger.info(
                        f"[FLOW] Configurando fecha de vuelta: {date_return_formatted}"
                    )

                    await page.click("#second-input", timeout=5000)
                    await page.wait_for_timeout(1000)

                    await page.evaluate(f"""
                        const secondInput = document.querySelector('#second-input');
                        if (secondInput) {{
                            secondInput.value = '{date_return_formatted}';
                            secondInput.setAttribute('aria-label', 'Fecha vuelta {date_return_formatted}');
                            secondInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            secondInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            secondInput.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        }}
                        const fechaVueltaField = document.querySelector('input[name="FechaVueltaSel"]');
                        if (fechaVueltaField) {{ fechaVueltaField.value = '{date_return_formatted}'; }}
                    """)

                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)

                    logger.info(
                        f"[FLOW] Fecha de vuelta configurada: {date_return_formatted}"
                    )

                # Verificar que los campos tienen las fechas
                fecha_ida_value = await page.input_value("#first-input")
                logger.info(f"[FLOW DEBUG] Fecha ida en input: {fecha_ida_value}")

                if date_return_formatted:
                    fecha_vuelta_value = await page.input_value("#second-input")
                    logger.info(
                        f"[FLOW DEBUG] Fecha vuelta en input: {fecha_vuelta_value}"
                    )

            except Exception as e:
                logger.error(f"[FLOW] Error configurando fechas: {e}")
                try:
                    error_screenshot = os.path.join(
                        RESPONSES_DIR, "debug_datepicker_error.png"
                    )
                    await page.screenshot(path=error_screenshot)
                    logger.error("[FLOW] Screenshot error: debug_datepicker_error.png")
                except Exception:
                    pass
                raise

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
            logger.info("[FLOW] Buscando botón de buscar billetes")

            # Intentar múltiples selectores para el botón de buscar
            search_selectors = [
                "button[type='submit']",
                "button:has-text('Buscar')",
                "button:has-text('Buscar billetes')",
                ".rf-btn--submit",
                "input[type='submit']",
                "button.btn-search",
            ]

            clicked_search = False
            for selector in search_selectors:
                try:
                    search_btn = page.locator(selector).first
                    if await search_btn.is_visible(timeout=2000):
                        logger.info(
                            f"[FLOW DEBUG] Encontrado botón de buscar con selector: {selector}"
                        )
                        await search_btn.click()
                        clicked_search = True
                        logger.info("[FLOW] Click en buscar billetes exitoso")
                        break
                except Exception as e:
                    logger.debug(
                        f"[FLOW DEBUG] Selector de botón '{selector}' falló: {e}"
                    )
                    continue

            if not clicked_search:
                logger.error("[FLOW DEBUG] No se encontró botón de buscar")
                # Intentar hacer submit del formulario directamente
                try:
                    await page.evaluate("""
                        const form = document.querySelector('form');
                        if (form) {
                            form.submit();
                        }
                    """)
                    logger.info("[FLOW] Submit del formulario ejecutado con JavaScript")
                except Exception as e:
                    logger.error(f"[FLOW] Error haciendo submit del formulario: {e}")
                    raise Exception(
                        "No se pudo hacer clic en buscar ni submit del formulario"
                    )

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
