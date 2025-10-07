# Renfe Navigation API

FastAPI service exposing a GET endpoint that uses Playwright to fetch available trains from Renfe given origin, destination, and outbound/return dates.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install --with-deps
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoint

- GET /trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1

Dates must be ISO format YYYY-MM-DD.

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
