# Test Fixtures

Este directorio contiene datos de prueba estáticos para los tests unitarios.

## Archivos

### `train_list_sample.html`

Respuesta HTML real de Renfe con la lista de trenes de ejemplo.

- **Origen:** OURENSE
- **Destino:** MADRID
- **Fecha:** 14/10/2025
- **Trenes:** 11 trenes (AVLO, AVE, ALVIA)
- **Uso:** Test del parser `parse_train_list_html()`

Este archivo es agnóstico de si es ida o vuelta, ya que el parser extrae la estructura independientemente de la dirección del viaje.

