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
    """Individual train fare"""

    name: str  # Básico, Elige, Elige Confort, Prémium, Básica
    price: float
    currency: str = "EUR"
    code: Optional[str] = None  # data-cod-tarifa
    tp_enlace: Optional[str] = None  # data-cod-tpenlacesilencio
    features: List[str] = []  # Features list


class TrainModel(BaseModel):
    """Train with all fares and attributes"""

    train_id: str  # Train id (e.g., "i_1")
    service_type: str  # AVE, AVLO, ALVIA, etc.
    departure_time: str  # Departure time (e.g., "06:24")
    arrival_time: str  # Arrival time (e.g., "08:49")
    duration: str  # Duration (e.g., "2 horas 25 minutos")
    price_from: float  # Minimum price
    currency: str = "EUR"
    fares: List[FareOption] = []  # Available fares
    badges: List[str] = []  # Labels (lowest price, fastest, etc.)
    accessible: bool = False  # H seat available
    eco_friendly: bool = False  # Zero emissions


# Helper to load the parser robustly, avoiding relative imports
_def_parse_train_list_html = None


def _get_parse_train_list_html():
    """
    Dynamically obtain the parse_train_list_html function.

    NOTE: This function centralizes the import to avoid circular imports and
    differences across execution contexts.
    """
    global _def_parse_train_list_html
    if _def_parse_train_list_html is not None:
        return _def_parse_train_list_html

    # Now that the package is installed, import directly
    try:
        from app.parser import parse_train_list_html

        _def_parse_train_list_html = parse_train_list_html
        logger.debug("[SCRAPER] Parser imported from app.parser")
        return parse_train_list_html
    except ImportError as e:
        # Fallback: try relative import
        try:
            from .parser import parse_train_list_html

            _def_parse_train_list_html = parse_train_list_html
            logger.debug("[SCRAPER] Parser imported via relative import")
            return parse_train_list_html
        except ImportError as e2:
            error_msg = f"Could not import parse_train_list_html. Errors: {e}, {e2}"
            logger.error(f"[SCRAPER] {error_msg}")
            raise ImportError(error_msg)


def _ensure_responses_dir():
    """Create responses directory if missing"""
    os.makedirs(RESPONSES_DIR, exist_ok=True)


def _save_response(
    content: str, status_code: int = 200, filename_suffix: str = "buscarTren.do.log"
):
    """Save HTML response using format [AAMMDD_HH24MISS]_[Status code]_[filename_suffix]"""
    _ensure_responses_dir()
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    filename = f"{timestamp}_{status_code}_{filename_suffix}"
    filepath = os.path.join(RESPONSES_DIR, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"[SCRAPER] Response saved as: {filename}")
        return filepath
    except Exception as e:
        logger.error(f"[SCRAPER] Error saving response: {e}")
        return None


def _parse_and_save_trains_json(
    html_content: str, 
    status_code: int = 200, 
    filename_suffix: str = "buscarTren.do.log"
) -> tuple[List[TrainModel], str]:
    """
    Parse train results HTML and save both HTML and pretty JSON.

    Args:
        html_content: HTML content of the results page
        status_code: HTTP status code
        filename_suffix: Suffix for output filename

    Returns:
        Tuple with (trains_list, html_filepath)
    """
    # Guardar HTML
    html_filepath = _save_response(html_content, status_code, filename_suffix)
    
    # Parsear trenes
    try:
        parse_train_list_html = _get_parse_train_list_html()
        trains = parse_train_list_html(html_content)
        logger.info(f"[PARSER] Extracted trains: {len(trains)}")
        
        # Guardar JSON con pretty print
        if trains:
            json_filepath = _save_trains_json(trains, status_code, filename_suffix)
            logger.info(f"[PARSER] JSON saved to: {json_filepath}")
        else:
            logger.warning(f"[PARSER] No trains found in HTML - Status: {status_code}")
            # Save empty JSON for debugging
            _save_trains_json([], status_code, filename_suffix)
        
        return trains, html_filepath
        
    except Exception as e:
        logger.error(f"[PARSER] Error parsing results HTML: {e}")
        return [], html_filepath


def _save_trains_json(
    trains: List[TrainModel], 
    status_code: int = 200, 
    filename_suffix: str = "buscarTren.do.log"
) -> str:
    """
    Save train list as pretty-printed JSON.

    Args:
        trains: Parsed train list
        status_code: HTTP status code
        filename_suffix: Suffix for the filename

    Returns:
        Path to the saved JSON file
    """
    _ensure_responses_dir()
    timestamp = datetime.now().strftime("%y%m%d_%H%M%S")
    
    # Build JSON filename
    json_filename = f"{timestamp}_{status_code}_{filename_suffix.replace('.log', '.json')}"
    json_filepath = os.path.join(RESPONSES_DIR, json_filename)
    
    try:
        # Convert to dictionaries for JSON serialization
        trains_data = [train.model_dump() for train in trains]
        
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(trains_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[PARSER] Trains JSON saved as: {json_filename}")
        return json_filepath
        
    except Exception as e:
        logger.error(f"[PARSER] Error saving trains JSON: {e}")
        return None


def _load_stations():
    """Load station catalog from JSON"""
    stations_path = os.path.join(
        os.path.dirname(__file__), "resources", "estaciones.json"
    )
    try:
        with open(stations_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load estaciones.json: {e}")
        return []


def _find_station(station_name: str) -> dict:
    """Find a station by name in the catalog"""
    stations = _load_stations()
    station_upper = station_name.upper()

    # Exact match first
    for station in stations:
        if station.get("desgEstacionPlano", "").upper() == station_upper:
            return station
        if station.get("cdgoEstacion", "").upper() == station_upper:
            return station

    # Partial match
    for station in stations:
        plano = station.get("desgEstacionPlano", "").upper()
        if station_upper in plano or plano.startswith(station_upper):
            return station

    # If not found, return generic data
    logger.warning(
        f"Station '{station_name}' not found in catalog, using generic search"
    )
    return {
        "cdgoEstacion": station_name.upper()[:5],
        "cdgoAdmon": "0071",
        "desgEstacion": station_name.upper(),
        "clave": f"0071,{station_name.upper()[:5]},null",
    }


async def _select_station_from_dropdown(page, selector: str, station_name: str):
    """
    Simulate station selection from autocomplete dropdown.

    Args:
        page: Playwright page
        selector: Input selector (e.g. "#origin", "#destination")
        station_name: Station name to select
    """
    try:
        # 1) Click the field to activate the dropdown
        logger.info(f"[FLOW] Activating dropdown for {selector}")
        await page.click(selector, timeout=5000)
        await page.wait_for_timeout(500)
        
        # 2) Type station name to trigger suggestions
        logger.info(f"[FLOW] Typing '{station_name}' to trigger suggestions")
        await page.fill(selector, station_name)
        await page.wait_for_timeout(1000)
        
        # 3) Press ArrowDown to select first option
        logger.info(f"[FLOW] Pressing ArrowDown to select first option")
        await page.press(selector, "ArrowDown")
        await page.wait_for_timeout(300)
        
        # 4) Press Enter to confirm selection
        logger.info(f"[FLOW] Pressing Enter to confirm selection")
        await page.press(selector, "Enter")
        await page.wait_for_timeout(500)
        
        logger.info(f"[FLOW] Station '{station_name}' selected successfully")
        
    except Exception as e:
        logger.warning(f"[FLOW] Error selecting station '{station_name}': {e}")
        # Fallback: try direct fill
        try:
            await page.fill(selector, station_name)
            await page.press(selector, "Enter")
            logger.info(f"[FLOW] Using direct fill fallback for '{station_name}'")
        except Exception as e2:
            logger.error(f"[FLOW] Fallback also failed for '{station_name}': {e2}")
            raise


async def _extract_results(page) -> List[TrainModel]:
    """Extract page HTML content and parse it using the independent parser."""
    # Maintainers: All HTML parsing logic is centralized in app/parser.py
    # (function parse_train_list_html). This scraper only fetches HTML with
    # Playwright and delegates analysis to the tested parser.
    logger.info("[SCRAPER] Waiting for results to load...")
    await page.wait_for_load_state("networkidle")
    html = await page.content()
    
    # Use centralized method for parsing and saving
    trains, _ = _parse_and_save_trains_json(html, 200, "buscarTren.do.log")
    return trains


async def search_trains(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> Tuple[List[TrainModel], Optional[List[TrainModel]]]:
    logger.info("[SCRAPER] Starting Chromium browser")

    # Find stations in catalog
    origin_station = _find_station(origin)
    dest_station = _find_station(destination)

    logger.info(
        f"[SCRAPER] Origen: {origin_station.get('desgEstacion', origin)} - Clave: {origin_station.get('clave')}"
    )
    logger.info(
        f"[SCRAPER] Destino: {dest_station.get('desgEstacion', destination)} - Clave: {dest_station.get('clave')}"
    )

    # Convert dates from YYYY-MM-DD to DD/MM/YYYY
    date_out_obj = datetime.strptime(date_out, "%Y-%m-%d")
    date_out_formatted = date_out_obj.strftime("%d/%m/%Y")

    date_return_formatted = ""
    if date_return:
        date_return_obj = datetime.strptime(date_return, "%Y-%m-%d")
        date_return_formatted = date_return_obj.strftime("%d/%m/%Y")

    # Build form data
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

        logger.info(f"[SCRAPER] Sending POST to {RENFE_SEARCH_URL}")

        # Navigate directly with POST
        await page.goto(RENFE_SEARCH_URL, wait_until="domcontentloaded")

        # Send form via JavaScript
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

        logger.info("[SCRAPER] Waiting for server response...")
        await page.wait_for_load_state("networkidle", timeout=30000)

        # Save HTML response
        response_content = await page.content()
        _save_response(response_content, status_code=200)

        logger.info("[SCRAPER] Extracting outbound results")
        trains_out = await _extract_results(page)
        trains_ret: Optional[List[TrainModel]] = None

        if date_return and trains_out:
            try:
                # Try to find return tab/section
                logger.info("[SCRAPER] Finding return results")
                vuelta_tab = page.locator(
                    '[id*="vuelta"], [class*="vuelta"], a:has-text("Vuelta")'
                )
                if await vuelta_tab.count() > 0:
                    await vuelta_tab.first().click()
                    await page.wait_for_timeout(500)
                    logger.info("[SCRAPER] Extracting return results")
                    trains_ret = await _extract_results(page)
            except Exception as e:
                logger.warning(
                    f"[SCRAPER] No se pudieron extraer trenes de vuelta: {e}"
                )
                trains_ret = None

        logger.info("[SCRAPER] Closing browser")
        await context.close()
        await browser.close()

        return trains_out, trains_ret


async def search_trains_flow(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
    playwright: Optional[dict] = None,
) -> str:
    """
    Perform the complete flow from Renfe's homepage to search.

    Args:
        origin: Origin station
        destination: Destination station
        date_out: Outbound date (YYYY-MM-DD)
        date_return: Optional return date (YYYY-MM-DD)
        adults: Number of adult passengers
        playwright: Playwright config dict: {
            'headless': bool,
            'viewport_width': int,
            'viewport_height': int,
            'slow_mo': int
        }

    Returns:
        Path to the saved response file
    """
    # Log input parameters
    logger.info(f"[FLOW] Input parameters:")
    logger.info(f"[FLOW]   - Origin: {origin}")
    logger.info(f"[FLOW]   - Destination: {destination}")
    logger.info(f"[FLOW]   - Outbound date: {date_out}")
    logger.info(f"[FLOW]   - Return date: {date_return if date_return else 'Not specified'}")
    logger.info(f"[FLOW]   - Passengers: {adults} adult{'s' if adults > 1 else ''}")
    logger.info(f"[FLOW]   - Playwright config: {playwright}")
    
    logger.info("[FLOW] Starting Chromium browser from homepage")

    async with async_playwright() as p:
        # Extraer configuración de Playwright
        cfg = playwright or {}
        headless = bool(cfg.get("headless", True))
        viewport_width = int(cfg.get("viewport_width", 1280))
        viewport_height = int(cfg.get("viewport_height", 720))
        slow_mo = int(cfg.get("slow_mo", 0))

        # Configurar args del navegador
        browser_args = []
        if not headless:
            browser_args = [
                "--start-maximized",
                f"--window-size={viewport_width},{viewport_height}",
            ]

        browser = await p.chromium.launch(
            headless=headless, args=browser_args, slow_mo=slow_mo
        )

        # Configurar contexto con viewport si no es headless
        context_options = {}
        if not headless:
            context_options = {
                "viewport": {"width": viewport_width, "height": viewport_height},
                "no_viewport": False,
            }

        context = await browser.new_context(**context_options)
        page = await context.new_page()

        try:
            # Navigate to Renfe homepage
            logger.info("[FLOW] Navigating to Renfe homepage")
            await page.goto(
                "https://www.renfe.com/es/es", wait_until="domcontentloaded"
            )

            # Small delay to let the page load widgets
            await page.wait_for_timeout(2000)

            # Accept cookies if popup appears
            logger.info("[FLOW] Checking cookie popup")
            try:
                # Try multiple selectors for the accept cookies button
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
                        if await cookie_btn.is_visible(timeout=1000):
                            await cookie_btn.click()
                            await page.wait_for_timeout(300)
                            logger.info(f"[FLOW] Cookies accepted with selector: {selector}")
                            clicked_cookies = True
                            break
                    except Exception:
                        continue

                if not clicked_cookies:
                    logger.info("[FLOW] No cookie popup found or already accepted")
            except Exception as e:
                logger.warning(f"[FLOW] Error handling cookies: {e}")

            # Find stations in catalog
            origin_station = _find_station(origin)
            dest_station = _find_station(destination)

            logger.info(f"[FLOW] Origin: {origin_station.get('desgEstacion', origin)} - Key: {origin_station.get('clave')}")
            logger.info(f"[FLOW] Destination: {dest_station.get('desgEstacion', destination)} - Key: {dest_station.get('clave')}")

            # Convert dates from YYYY-MM-DD to DD/MM/YYYY
            date_out_obj = datetime.strptime(date_out, "%Y-%m-%d")
            date_out_formatted = date_out_obj.strftime("%d/%m/%Y")

            date_return_formatted = ""
            if date_return:
                date_return_obj = datetime.strptime(date_return, "%Y-%m-%d")
                date_return_formatted = date_return_obj.strftime("%d/%m/%Y")

            # Wait for form to be ready
            await page.wait_for_selector("#origin", timeout=5000)

            # Select origin from dropdown
            logger.info(f"[FLOW] Selecting origin: {origin}")
            await _select_station_from_dropdown(page, "#origin", origin_station.get("desgEstacion", origin))

            # Select destination from dropdown
            logger.info(f"[FLOW] Selecting destination: {destination}")
            await _select_station_from_dropdown(page, "#destination", dest_station.get("desgEstacion", destination))

            # Interact with Renfe date picker correctly
            logger.info(f"[FLOW] Setting outbound date: {date_out_formatted}")

            try:
                # 1) Open date picker by clicking outbound input
                await page.click("#first-input", timeout=5000)
                await page.wait_for_selector("#daterangev2", timeout=5000)
                await page.wait_for_timeout(200)

                # 2) Select one-way / round-trip mode
                if date_return_formatted:
                    # Round-trip
                    vuelta_label = page.locator(
                        ".lightpick__label:has-text('Viaje de ida y vuelta')"
                    ).first
                    try:
                        if await vuelta_label.is_visible(timeout=1000):
                            await vuelta_label.click()
                            await page.wait_for_timeout(150)
                    except Exception:
                        pass
                else:
                    # One-way
                    ida_label = page.locator(
                        ".lightpick__label:has-text('Viaje solo ida')"
                    ).first
                    try:
                        if await ida_label.is_visible(timeout=1000):
                            await ida_label.click()
                            await page.wait_for_timeout(150)
                    except Exception:
                        pass

                # 3) Helpers to navigate months and read visible months
                spanish_months = {
                    1: "Enero",
                    2: "Febrero",
                    3: "Marzo",
                    4: "Abril",
                    5: "Mayo",
                    6: "Junio",
                    7: "Julio",
                    8: "Agosto",
                    9: "Septiembre",
                    10: "Octubre",
                    11: "Noviembre",
                    12: "Diciembre",
                }

                async def get_visible_month_texts() -> tuple[str, Optional[str]]:
                    # Wait for months container to exist
                    await page.wait_for_selector(
                        "#daterangev2 .lightpick__months",
                        timeout=5000,
                    )
                    # Read titles via JS to be resilient to minor structure changes
                    result = await page.evaluate(
                        """
                        (() => {
                          const getTitle = (idx) => {
                            const header = document.querySelector(`#daterangev2 > section > div.lightpick__inner > div.lightpick__months > section:nth-child(${idx}) > header`);
                            if (!header) return '';
                            
                            // Find the specific span containing month and year
                            const monthSpan = header.querySelector('div > span > span:nth-child(1)');
                            if (monthSpan) {
                              return monthSpan.textContent || '';
                            }
                            
                            // Fallback: extract only the first text line
                            const txt = header.textContent || '';
                            const lines = txt.split('\\n').filter(line => line.trim());
                            return lines[0] ? lines[0].trim() : '';
                          };
                          return { m1: getTitle(1), m2: getTitle(2) };
                        })()
                        """
                    )
                    m1_raw = result.get("m1") or ""
                    m2_raw = result.get("m2") or ""
                    
                    # Detailed logging of visible months
                    logger.info(f"[FLOW] 📅 Visible months in date picker:")
                    logger.info(f"[FLOW]   - Month 1: '{m1_raw}'")
                    logger.info(f"[FLOW]   - Month 2: '{m2_raw}'")
                    
                    # Lowercase for comparison
                    m1 = m1_raw.strip().lower()
                    m2 = m2_raw.strip().lower() if m2_raw else None
                    
                    return (m1, m2)

                async def click_next():
                    await page.click("button.lightpick__next-action", timeout=2000)
                    await page.wait_for_timeout(200)

                def month_matches(target_dt: datetime, month_text: str) -> bool:
                    mon = spanish_months[target_dt.month]
                    month_text_lower = (month_text or "").lower()
                    mon_lower = mon.lower()
                    matches = mon_lower in month_text_lower
                    
                    # Detailed logging of month comparison
                    logger.info(f"[FLOW] 🔍 Comparing months:")
                    logger.info(f"[FLOW]   - Target date: {target_dt.strftime('%Y-%m-%d')} (month: {mon})")
                    logger.info(f"[FLOW]   - Visible month: '{month_text}'")
                    logger.info(f"[FLOW]   - Matches? {matches} (searching '{mon_lower}' in '{month_text_lower}')")
                    
                    return matches

                async def select_day_in_panel(panel_index: int, day: int) -> bool:
                    base = f"#daterangev2 > section > div.lightpick__inner > div.lightpick__months > section:nth-child({panel_index})"
                    day_locator = page.locator(
                        base + " div.lightpick__days > div.lightpick__day.is-available",
                        has_text=str(day),
                    )
                    try:
                        if await day_locator.first.is_visible(timeout=2000):
                            await day_locator.first.click()
                            await page.wait_for_timeout(150)
                            return True
                    except Exception:
                        return False
                    return False

                # 4) Navigate until outbound month is visible (1st or 2nd panel)
                max_steps = 18  # safety limit
                steps = 0
                logger.info(f"[FLOW] 🗓️ Navigating to find outbound month: {date_out_obj.strftime('%B %Y')}")
                
                while steps < max_steps:
                    logger.info(f"[FLOW] 📍 Step {steps + 1}/{max_steps} - Checking visible months...")
                    m1, m2 = await get_visible_month_texts()
                    
                    # Check first panel
                    if month_matches(date_out_obj, m1):
                        logger.info(f"[FLOW] ✅ Outbound month found in first panel!")
                        break
                    
                    # Check second panel (if available)
                    if m2 and month_matches(date_out_obj, m2):
                        logger.info(f"[FLOW] ✅ Outbound month found in second panel!")
                        break
                    
                    # If not found, go next
                    logger.info(f"[FLOW] ➡️ Month not found, going next...")
                    await click_next()
                    steps += 1

                # 5) Select outbound day (panel 1 or 2, depending on visibility)
                selected_out = await select_day_in_panel(1, date_out_obj.day)
                if not selected_out and (
                    await page.locator(
                        "#daterangev2 > section > div.lightpick__inner > div.lightpick__months > section:nth-child(2)"
                    ).count()
                ):
                    selected_out = await select_day_in_panel(2, date_out_obj.day)
                if not selected_out:
                    raise Exception("Could not select outbound day in date picker")

                # 6) If return date, navigate and select it as well
                if date_return_formatted:
                    steps = 0
                    while steps < max_steps:
                        m1, m2 = await get_visible_month_texts()
                        if month_matches(date_return_obj, m1) or (
                            m2 and month_matches(date_return_obj, m2)
                        ):
                            break
                        await click_next()
                        steps += 1

                    selected_ret = await select_day_in_panel(1, date_return_obj.day)
                    if not selected_ret and (
                        await page.locator(
                            "#daterangev2 > section > div.lightpick__inner > div.lightpick__months > section:nth-child(2)"
                        ).count()
                    ):
                        selected_ret = await select_day_in_panel(2, date_return_obj.day)
                    if not selected_ret:
                        raise Exception("Could not select return day in date picker")

                # 7) Click Accept
                try:
                    logger.info("[FLOW] Clicking Accept")
                    aceptar_btn = page.locator(
                        "#daterangev2 > section > div.lightpick__footer-buttons > button:nth-child(2), button.lightpick__apply-action-sub"
                    ).first
                    if await aceptar_btn.is_visible(timeout=2000):
                        await aceptar_btn.click()
                        await page.wait_for_timeout(200)
                except Exception:
                    logger.warning("[FLOW] Could not click Accept")
                    pass

                logger.info("[FLOW] Dates selected in date picker")

            except Exception as e:
                logger.error(f"[FLOW] Error configuring dates: {e}")
                try:
                    error_screenshot = os.path.join(
                        RESPONSES_DIR, "debug_datepicker_error.png"
                    )
                    await page.screenshot(path=error_screenshot)
                    logger.error("[FLOW] Screenshot error: debug_datepicker_error.png")
                except Exception:
                    pass
                raise

            # Configure number of passengers
            logger.info(f"[FLOW] Setting passengers: {adults}")
            # Passengers field might not be directly editable, check
            try:
                await page.fill("#adultos_", str(adults))
            except Exception:
                logger.info("[FLOW] Could not fill passengers directly, using default value")

            # Click search button
            logger.info("[FLOW] Finding search button")

            # Try multiple selectors for search button
            search_selectors = [
                "#ticketSearchBt button span:has-text('Buscar billete')",
                "button:has-text('Buscar billete')",
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
                    if await search_btn.is_visible(timeout=1000):
                        logger.info(f"[FLOW DEBUG] Found search button with selector: {selector}")
                        await search_btn.click()
                        clicked_search = True
                        logger.info("[FLOW] Search click successful")
                        break
                except Exception as e:
                    logger.debug(f"[FLOW DEBUG] Button selector '{selector}' failed: {e}")
                    continue

            if not clicked_search:
                logger.error("[FLOW DEBUG] Search button not found")
                # Try submitting the form directly
                try:
                    await page.evaluate("""
                        const form = document.querySelector('form');
                        if (form) {
                            form.submit();
                        }
                    """)
                    logger.info("[FLOW] Form submit executed via JavaScript")
                except Exception as e:
                    logger.error(f"[FLOW] Error submitting form: {e}")
                    raise Exception(
                        "Could not click search nor submit the form"
                    )

            # Wait for results page to load
            await page.wait_for_load_state("networkidle")

            # Get HTML content of results page
            response_content = await page.content()

            # Use centralized method for parsing and saving
            trains, filepath = _parse_and_save_trains_json(
                response_content,
                status_code=200,
                filename_suffix="buscarTrenFlow.do.log",
            )

            logger.info(f"[FLOW] Flow completed successfully - {len(trains)} trains found")
            return filepath

        except Exception as e:
            logger.error(f"[FLOW] Flow error: {e}")
            # Try to save error response
            try:
                response_content = await page.content()
                _, filepath = _parse_and_save_trains_json(
                    response_content,
                    status_code=500,
                    filename_suffix="buscarTrenFlow.do.log",
                )
                return filepath
            except Exception:
                pass
            raise
        finally:
            logger.info("[FLOW] Closing browser")
            await context.close()
            await browser.close()
