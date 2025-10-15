"""
Service for direct train search using Renfe's internal API.

This service sends a direct POST request to Renfe's search endpoint
without navigating through the UI.
"""

from typing import List, Optional, Tuple
import logging
import json

from playwright.async_api import async_playwright

from .renfe_common import (
    TrainModel,
    RENFE_SEARCH_URL,
    find_station,
    format_date,
    save_response,
    parse_and_save_trains_json,
)

logger = logging.getLogger(__name__)


async def extract_results(page) -> List[TrainModel]:
    """Extract page HTML content and parse it using the independent parser."""
    # Maintainers: All HTML parsing logic is centralized in app/parser.py
    # (function parse_train_list_html). This scraper only fetches HTML with
    # Playwright and delegates analysis to the tested parser.
    logger.info("[SCRAPER] Waiting for results to load...")
    await page.wait_for_load_state("networkidle")
    html = await page.content()
    
    # Use centralized method for parsing and saving
    trains, _ = parse_and_save_trains_json(html, 200, "buscarTren.do.log")
    return trains


async def search_trains(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> Tuple[List[TrainModel], Optional[List[TrainModel]]]:
    """
    Perform a direct train search using Renfe's API.

    Args:
        origin: Origin station name
        destination: Destination station name
        date_out: Outbound date (YYYY-MM-DD)
        date_return: Optional return date (YYYY-MM-DD)
        adults: Number of adult passengers

    Returns:
        Tuple with (outbound_trains, return_trains)
    """
    logger.info("[SCRAPER] Starting Chromium browser")

    # Find stations in catalog
    origin_station = find_station(origin)
    dest_station = find_station(destination)

    logger.info(
        f"[SCRAPER] Origin: {origin_station.get('desgEstacion', origin)} - Key: {origin_station.get('clave')}"
    )
    logger.info(
        f"[SCRAPER] Destination: {dest_station.get('desgEstacion', destination)} - Key: {dest_station.get('clave')}"
    )

    # Convert dates from YYYY-MM-DD to DD/MM/YYYY
    date_out_formatted = format_date(date_out)

    date_return_formatted = ""
    if date_return:
        date_return_formatted = format_date(date_return)

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
        f"[SCRAPER] Search parameters: {date_out_formatted} -> {date_return_formatted if date_return else 'One way only'}"
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
        save_response(response_content, status_code=200)

        logger.info("[SCRAPER] Extracting outbound results")
        trains_out = await extract_results(page)
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
                    trains_ret = await extract_results(page)
            except Exception as e:
                logger.warning(
                    f"[SCRAPER] Could not extract return trains: {e}"
                )
                trains_ret = None

        logger.info("[SCRAPER] Closing browser")
        await context.close()
        await browser.close()

        return trains_out, trains_ret

