from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from .renfe import search_trains

app = FastAPI(title="Renfe Navigation API")


class Train(BaseModel):
    service: str
    departure: str
    arrival: str
    duration: str
    fare_from: Optional[float] = None
    currency: Optional[str] = None


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
    trains_out, trains_ret = await search_trains(
        origin=origin,
        destination=destination,
        date_out=date_out,
        date_return=date_return,
        adults=adults,
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
