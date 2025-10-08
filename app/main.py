from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime
import json

try:
    from .renfe import search_trains, search_trains_flow
except ImportError:
    from renfe import search_trains, search_trains_flow

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Renfe Navigation API")


class FareOption(BaseModel):
    """Tarifa individual de un tren"""

    name: str
    price: float
    currency: str = "EUR"
    code: Optional[str] = None
    tp_enlace: Optional[str] = None
    features: List[str] = []


class Train(BaseModel):
    """Tren con todas sus tarifas y detalles"""

    train_id: str
    service_type: str
    departure_time: str
    arrival_time: str
    duration: str
    price_from: float
    currency: str = "EUR"
    fares: List[FareOption] = []
    badges: List[str] = []
    accessible: bool = False
    eco_friendly: bool = False


class TrainsResponse(BaseModel):
    origin: str
    destination: str
    date_out: str
    date_return: Optional[str] = None
    adults: int
    trains_out: List[Train]
    trains_return: Optional[List[Train]] = None


@app.get("/trains", response_model=TrainsResponse)
async def get_trains(
    origin: str = Query(..., description="Station origin, e.g. OURENSE"),
    destination: str = Query(..., description="Station destination, e.g. MADRID"),
    date_out: str = Query(..., description="Outbound date YYYY-MM-DD"),
    date_return: Optional[str] = Query(None, description="Return date YYYY-MM-DD"),
    adults: int = Query(1, ge=1, le=8, description="Number of adult passengers"),
):
    start_time = datetime.now()
    logger.info(
        f"[REQUEST] Iniciando búsqueda: {origin} -> {destination}, Salida: {date_out}, Vuelta: {date_return}, Pasajeros: {adults}"
    )

    try:
        trains_out, trains_ret = await search_trains(
            origin=origin,
            destination=destination,
            date_out=date_out,
            date_return=date_return,
            adults=adults,
        )

        # Mapear modelos del scraper (TrainModel) al modelo API (Train)
        trains_out_api = [
            Train(**t.model_dump()) if hasattr(t, "model_dump") else Train(**t)
            for t in trains_out
        ]
        trains_ret_api = None
        if trains_ret is not None:
            trains_ret_api = [
                Train(**t.model_dump()) if hasattr(t, "model_dump") else Train(**t)
                for t in trains_ret
            ]

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"[SUCCESS] Búsqueda completada en {elapsed:.2f}s - Trenes ida: {len(trains_out_api)}, Trenes vuelta: {len(trains_ret_api) if trains_ret_api else 0}"
        )

        payload = TrainsResponse(
            origin=origin,
            destination=destination,
            date_out=date_out,
            date_return=date_return,
            adults=adults,
            trains_out=trains_out_api,
            trains_return=trains_ret_api,
        )

        # Log del JSON de salida en formato pretty
        payload_json = payload.model_dump()
        logger.info(
            f"[RESPONSE] JSON de salida:\n{json.dumps(payload_json, indent=2, ensure_ascii=False)}"
        )

        return JSONResponse(content=payload_json)
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[ERROR] Búsqueda falló después de {elapsed:.2f}s: {str(e)}")
        raise


@app.get("/trains-flow")
async def get_trains_flow(
    origin: str = Query(..., description="Station origin, e.g. OURENSE"),
    destination: str = Query(..., description="Station destination, e.g. MADRID"),
    date_out: str = Query(..., description="Outbound date YYYY-MM-DD"),
    date_return: Optional[str] = Query(None, description="Return date YYYY-MM-DD"),
    adults: int = Query(1, ge=1, le=8, description="Number of adult passengers"),
):
    """Endpoint que realiza el flujo completo desde la página inicial de Renfe hasta la búsqueda de trenes"""
    start_time = datetime.now()
    logger.info(
        f"[FLOW REQUEST] Iniciando flujo: {origin} -> {destination}, Salida: {date_out}, Vuelta: {date_return}, Pasajeros: {adults}"
    )

    try:
        filepath = await search_trains_flow(
            origin=origin,
            destination=destination,
            date_out=date_out,
            date_return=date_return,
            adults=adults,
            playwright={},  # usa config por defecto; se puede parametrizar por env
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"[FLOW SUCCESS] Flujo completado en {elapsed:.2f}s - Archivo guardado: {filepath}"
        )

        return {"message": "Flujo completado exitosamente", "filepath": filepath}

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[FLOW ERROR] Flujo falló después de {elapsed:.2f}s: {str(e)}")
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
