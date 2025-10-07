from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime

try:
    from .renfe import search_trains
except ImportError:
    from renfe import search_trains

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

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"[SUCCESS] Búsqueda completada en {elapsed:.2f}s - Trenes ida: {len(trains_out)}, Trenes vuelta: {len(trains_ret) if trains_ret else 0}"
        )

        payload = TrainsResponse(
            origin=origin,
            destination=destination,
            date_out=date_out,
            date_return=date_return,
            adults=adults,
            trains_out=trains_out,
            trains_return=trains_ret,
        )
        return JSONResponse(content=payload.model_dump())
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"[ERROR] Búsqueda falló después de {elapsed:.2f}s: {str(e)}")
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
