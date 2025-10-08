# Renfe Navigation API

FastAPI service exposing a GET endpoint that uses Playwright to fetch available trains from Renfe given origin, destination, and outbound/return dates.

## Estructura del Proyecto

```
renfe-navigation/
├── app/
│   ├── main.py              # FastAPI app y endpoint /trains
│   ├── renfe.py             # Scraper con Playwright
│   ├── parser.py            # Parser HTML independiente
│   └── resources/
│       └── estaciones.json  # Catálogo de estaciones
├── tests/
│   ├── conftest.py                      # Configuración de pytest
│   ├── test_fixed_parser_train_lists.py # Tests del parser HTML
│   └── fixtures/
│       └── train_list_sample.html       # Datos de prueba
├── pytest.ini               # Configuración de pytest
├── Makefile                 # Comandos útiles
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps
```

O con Make:

```bash
make install
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

O con Make:

```bash
make run
```

## Endpoints

### GET /trains
Realiza una búsqueda directa de trenes usando la API interna de Renfe.

- GET /trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1

Dates must be ISO format YYYY-MM-DD.

### GET /trains-flow
Realiza el flujo completo desde la página inicial de Renfe, rellenando el formulario y haciendo clic en buscar.

- GET /trains-flow?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1

Dates must be ISO format YYYY-MM-DD.

**Nota:** Este endpoint guarda automáticamente la respuesta HTML en el directorio `responses/` con el formato `[AAMMDD_HH24MISS]_[Status code]_buscarTrenFlow.do.log`.

### Estructura de Respuesta

Cada tren incluye:
- `train_id`: Identificador único del tren
- `service_type`: Tipo de servicio (AVE, AVLO, ALVIA, etc.)
- `departure_time`, `arrival_time`: Horarios
- `duration`: Duración del trayecto
- `price_from`: Precio mínimo desde
- `fares[]`: Array de tarifas disponibles con:
  - `name`: Nombre de la tarifa (Básico, Elige, Prémium, etc.)
  - `price`: Precio de la tarifa
  - `code`: Código de tarifa
  - `tp_enlace`: Código de enlace
  - `features[]`: Lista de prestaciones incluidas
- `badges[]`: Etiquetas especiales (Precio más bajo, Más rápido)
- `accessible`: Plaza H disponible
- `eco_friendly`: Cero emisiones

### Logging de Respuestas

Cada búsqueda guarda automáticamente la respuesta HTML de Renfe en el directorio `responses/` con el formato:

```
[AAMMDD_HHMMSS]_[StatusCode]_buscarTren.do.log
```

Ejemplo: `251007_143022_200_buscarTren.do.log`

## Pruebas con curl

El scraper usa la API directa de Renfe: `https://venta.renfe.com/vol/buscarTren.do?Idioma=es&Pais=ES`

Las estaciones se resuelven automáticamente desde `app/resources/estaciones.json`.

### Ejemplo 1: Ourense -> Madrid (ida y vuelta)
```bash
curl -s "http://localhost:8000/trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1" | jq
```

### Ejemplo 2: Barcelona -> Madrid (solo ida)
```bash
curl -s "http://localhost:8000/trains?origin=BARCELONA&destination=MADRID&date_out=2025-10-20&adults=2" | jq
```

### Ejemplo 3: Madrid -> Sevilla (ida y vuelta)
```bash
curl -s "http://localhost:8000/trains?origin=MADRID&destination=SEVILLA&date_out=2025-11-01&date_return=2025-11-03&adults=1" | jq
```

### Ejemplo 4: Valencia -> Alicante (solo ida, 4 pasajeros)
```bash
curl -s "http://localhost:8000/trains?origin=VALENCIA&destination=ALICANTE&date_out=2025-10-25&adults=4" | jq
```

### Ejemplo 5: Bilbao -> San Sebastián (ida y vuelta)
```bash
curl -s "http://localhost:8000/trains?origin=BILBAO&destination=SAN%20SEBASTIAN&date_out=2025-11-10&date_return=2025-11-12&adults=2" | jq
```

**Nota:** Puedes usar nombres de estaciones como aparecen en `estaciones.json`. El sistema buscará coincidencias automáticamente.

### Ejemplos con /trains-flow

Estos ejemplos utilizan el flujo completo desde la página inicial de Renfe:

#### Ejemplo 6: Ourense -> Madrid (ida y vuelta) usando flujo completo
```bash
curl -s "http://localhost:8000/trains-flow?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1"
```

#### Ejemplo 7: Barcelona -> Madrid (solo ida) usando flujo completo
```bash
curl -s "http://localhost:8000/trains-flow?origin=BARCELONA&destination=MADRID&date_out=2025-10-20&adults=2"
```

**Nota:** Los endpoints `/trains-flow` generan archivos de respuesta en `responses/` con el formato `[AAMMDD_HH24MISS]_[Status code]_buscarTrenFlow.do.log`.

## Testing

El proyecto utiliza **pytest** para los tests unitarios y de integración.

### Ejecutar todos los tests

```bash
pytest
# o
make test
```

O con más detalle:

```bash
pytest -v
# o
make test-verbose
```

### Ejecutar tests específicos

```bash
# Solo tests del parser
pytest tests/test_fixed_parser_train_lists.py -v

# Un test específico
pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_extracts_fares -v

# Tests con salida detallada (útil para debugging)
pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_display_results -v -s
```

### Cobertura de Tests

El proyecto usa `pytest-cov` para analizar la cobertura de código. Hay varias formas de ver la cobertura:

```bash
# Ver cobertura en terminal con líneas no cubiertas
make test-cov

# Generar reporte HTML interactivo
make test-html  # Abre htmlcov/index.html

# Re-ejecutar solo tests fallidos
make test-failed
```

#### Estado actual de cobertura:

| Módulo | Cobertura | Descripción |
|--------|-----------|-------------|
| `app/parser.py` | 90% | Parser HTML independiente y testeado |
| `app/main.py` | 87% | Endpoint FastAPI con tests de integración |
| `app/renfe.py` | 24% | Scraper Playwright (necesita más tests) |

Los tests se enfocan en:
- ✓ Parsing correcto de HTML de trenes
- ✓ Estructura de datos de trenes y tarifas
- ✓ Integración del endpoint FastAPI
- ✓ Validación de parámetros requeridos

### Tests disponibles

#### `test_fixed_parser_train_lists.py`

Tests del parser de HTML de Renfe (`app/parser.py`) con datos fixture fijos:

- ✓ Parsea correctamente la estructura de trenes
- ✓ Extrae información básica (horarios, duración, precios)
- ✓ Extrae tarifas múltiples con prestaciones
- ✓ Extrae badges y etiquetas
- ✓ Identifica accesibilidad y características eco
- ✓ Reconoce diferentes tipos de servicio
- ✓ Serializa correctamente a JSON

Los tests utilizan fixtures de datos reales en `tests/fixtures/train_list_sample.html`

#### `test_api_endpoint.py`

Tests del endpoint FastAPI (`/trains`) usando fixtures de respuestas reales:

- ✓ Verifica estructura de respuesta del endpoint
- ✓ Valida número de trenes parseados
- ✓ Comprueba estructura de datos de trenes
- ✓ Prueba endpoint con fecha de vuelta
- ✓ Valida parámetros requeridos

Los tests utilizan mocks y fixtures en `tests/fixtures/renfe_response_sample.html`

### Parser independiente

El parser (`app/parser.py`) con la función `parse_train_list_html()` es independiente y puede usarse para parsear HTML de Renfe sin necesidad de Playwright. Es agnóstico de si es ida o vuelta.

### Limpieza

Para limpiar archivos temporales y caches:

```bash
make clean  # Limpia __pycache__, .pytest_cache, htmlcov, etc.
```
