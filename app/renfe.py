"""
Renfe scraping module - Compatibility wrapper.

This module re-exports functionality from the separated services
to maintain backward compatibility with existing code.

New code should import directly from:
- app.search_trains_service for direct API search
- app.search_trains_flow_service for homepage flow
- app.renfe_common for shared utilities
"""

# Re-export models and utilities from common module
from .renfe_common import (
    FareOption,
    TrainModel,
    RENFE_SEARCH_URL,
    RESPONSES_DIR,
    get_parse_train_list_html,
    ensure_responses_dir,
    save_response,
    parse_and_save_trains_json,
    save_trains_json,
    load_stations,
    find_station,
    format_date,
)

# Re-export services
from .search_trains_service import search_trains
from .search_trains_flow_service import search_trains_flow

# Make all exports available at module level
__all__ = [
    # Models
    "FareOption",
    "TrainModel",
    # Constants
    "RENFE_SEARCH_URL",
    "RESPONSES_DIR",
    # Utilities
    "get_parse_train_list_html",
    "ensure_responses_dir",
    "save_response",
    "parse_and_save_trains_json",
    "save_trains_json",
    "load_stations",
    "find_station",
    "format_date",
    # Services
    "search_trains",
    "search_trains_flow",
]
