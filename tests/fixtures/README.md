# Test Fixtures

This directory contains static test data for unit tests.

## Archivos

### `train_list_sample.html`

Real Renfe HTML response with the sample train list (only the list div).

- **Origen:** OURENSE
- **Destino:** MADRID
- **Fecha:** 14/10/2025
- **Trenes:** 11 trenes (AVLO, AVE, ALVIA)
- **Uso:** Test del parser `parse_train_list_html()` en `test_fixed_parser_train_lists.py`

This file is agnostic to outbound or return, since the parser extracts the structure regardless of travel direction.

### `renfe_response_sample.html`

Full Renfe HTML response (entire page).

- **Origen:** OURENSE
- **Destino:** MADRID
- **Fecha:** 14/10/2025
- **Trenes:** 11 trenes (AVLO, AVE, ALVIA)
- **Uso:** Test del endpoint API en `test_api_endpoint.py`

This file contains the full Renfe server response, including all page elements.

