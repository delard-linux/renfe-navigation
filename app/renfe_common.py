"""
Common utilities and models for Renfe scraping services.

This module contains shared functionality used by both search_trains
and search_trains_flow services.
"""

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import json
import os

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


def get_parse_train_list_html():
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


def ensure_responses_dir():
    """Create responses directory if missing"""
    os.makedirs(RESPONSES_DIR, exist_ok=True)


def save_response(
    content: str, status_code: int = 200, filename_suffix: str = "buscarTren.do.log"
):
    """Save HTML response using format [AAMMDD_HH24MISS]_[Status code]_[filename_suffix]"""
    ensure_responses_dir()
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


def parse_and_save_trains_json(
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
    # Save HTML
    html_filepath = save_response(html_content, status_code, filename_suffix)
    
    # Parse trains
    try:
        parse_train_list_html = get_parse_train_list_html()
        trains = parse_train_list_html(html_content)
        logger.info(f"[PARSER] Extracted trains: {len(trains)}")
        
        # Save JSON with pretty print
        if trains:
            json_filepath = save_trains_json(trains, status_code, filename_suffix)
            logger.info(f"[PARSER] JSON saved to: {json_filepath}")
        else:
            logger.warning(f"[PARSER] No trains found in HTML - Status: {status_code}")
            # Save empty JSON for debugging
            save_trains_json([], status_code, filename_suffix)
        
        return trains, html_filepath
        
    except Exception as e:
        logger.error(f"[PARSER] Error parsing results HTML: {e}")
        return [], html_filepath


def save_trains_json(
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
    ensure_responses_dir()
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


def load_stations():
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


def find_station(station_name: str) -> dict:
    """Find a station by name in the catalog"""
    stations = load_stations()
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


def format_date(date_str: str) -> str:
    """Convert date from YYYY-MM-DD to DD/MM/YYYY"""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%d/%m/%Y")


def get_default_playwright_config() -> dict:
    """
    Return default Playwright configuration used by services when no explicit
    configuration is provided by the caller.

    Returns:
        dict: { headless, viewport_width, viewport_height, slow_mo }
    """
    return {
        "headless": True,
        "viewport_width": 1280,
        "viewport_height": 720,
        "slow_mo": 0,
        "locale": "es-ES",
    }

