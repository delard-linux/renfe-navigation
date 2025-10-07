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

## Prueba rápida

```bash
# Ida y vuelta
curl -s "http://localhost:8000/trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1" | jq

# Solo ida
curl -s "http://localhost:8000/trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&adults=1" | jq
```
