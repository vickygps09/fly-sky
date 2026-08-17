"""Flights router — Search, seat map, flight status, airports, baggage info."""

from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import FlightSearch, FlightOut, SeatOut, AirportOut, FlightStatusOut
from chatbot.tools import search_flights, get_seat_map, get_flight_status, get_baggage_info
from cache import cache_get, cache_set

router = APIRouter(prefix="/api/flights", tags=["Flights"])


@router.get("/airports", response_model=list[AirportOut])
def list_airports(db: Session = Depends(get_db)):
    cached = cache_get("airports:all")
    if cached:
        return cached
    airports = db.query(models.Airport).all()
    cache_set("airports:all", [AirportOut.model_validate(a).model_dump() for a in airports], ttl=600)
    return airports


@router.post("/search", response_model=list[FlightOut])
def search(data: FlightSearch, db: Session = Depends(get_db)):
    results = search_flights(
        db=db,
        departure_city=data.departure_city,
        arrival_city=data.arrival_city,
        travel_date=data.departure_date,
        passengers=data.passengers,
        cabin_class=data.cabin_class,
        return_date=data.return_date,
    )

    if isinstance(results, dict) and "error" in results:
        raise HTTPException(status_code=404, detail=results["error"])

    outbound = results.get("outbound_flights", [])
    return [FlightOut(**f) for f in outbound]


@router.get("/{flight_id}/seats", response_model=list[SeatOut])
def get_seats(flight_id: str, db: Session = Depends(get_db)):
    flight = db.query(models.Flight).filter(models.Flight.id == flight_id).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    seats = get_seat_map(db, flight_id)
    return [SeatOut(**s) for s in seats]


@router.get("/status/{flight_number}", response_model=FlightStatusOut)
def flight_status(flight_number: str, db: Session = Depends(get_db)):
    result = get_flight_status(db, flight_number)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return FlightStatusOut(**result)


@router.get("/baggage/{cabin_class}")
def baggage_info(cabin_class: str):
    cache_key = f"baggage:{cabin_class}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = get_baggage_info(cabin_class)
    cache_set(cache_key, result, ttl=3600)
    return result
