# Test Fixtures

Este directorio contiene datos de prueba estáticos para los tests unitarios.

## Archivos

### `train_list_sample.html`

Respuesta HTML real de Renfe con la lista de trenes de ejemplo (solo el div de la lista).

- **Origen:** OURENSE
- **Destino:** MADRID
- **Fecha:** 14/10/2025
- **Trenes:** 11 trenes (AVLO, AVE, ALVIA)
- **Uso:** Test del parser `parse_train_list_html()` en `test_fixed_parser_train_lists.py`

Este archivo es agnóstico de si es ida o vuelta, ya que el parser extrae la estructura independientemente de la dirección del viaje.

### `renfe_response_sample.html`

Respuesta HTML completa de Renfe (página completa).

- **Origen:** OURENSE
- **Destino:** MADRID
- **Fecha:** 14/10/2025
- **Trenes:** 11 trenes (AVLO, AVE, ALVIA)
- **Uso:** Test del endpoint API en `test_api_endpoint.py`

Este archivo contiene la respuesta completa del servidor de Renfe, incluyendo todos los elementos de la página.

