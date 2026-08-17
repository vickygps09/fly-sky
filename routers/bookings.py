"""Bookings router — Create, view, modify, cancel, check-in, boarding pass."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_user, require_user
from schemas import BookingCreate, BookingOut, BookingModify, BookingCancel, CheckInRequest, BoardingPass
from chatbot.tools import (
    create_booking, get_booking_by_pnr, get_user_bookings,
    cancel_booking, modify_booking, web_check_in, get_boarding_pass,
)
from cache import cache_get, cache_set, cache_delete

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("/", response_model=dict)
def create(data: BookingCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    passengers = [p.model_dump() for p in data.passengers]
    result = create_booking(
        db=db,
        flight_id=data.flight_id,
        passengers=passengers,
        cabin_class=data.cabin_class,
        trip_type=data.trip_type,
        return_flight_id=data.return_flight_id,
        user_id=user.id if user else None,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if user:
        cache_delete(f"bookings:user:{user.id}")
    return result


@router.get("/{pnr}", response_model=BookingOut)
def get_booking(pnr: str, db: Session = Depends(get_db)):
    cache_key = f"booking:pnr:{pnr.upper()}"
    cached = cache_get(cache_key)
    if cached:
        return BookingOut(**cached)
    booking = get_booking_by_pnr(db, pnr)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    dep_time = datetime.fromisoformat(booking["departure_time"])
    arr_time = datetime.fromisoformat(booking["arrival_time"])
    out = BookingOut(
        id=booking["id"],
        pnr=booking["pnr"],
        flight_number=booking["flight_number"],
        airline_name=booking["airline_name"],
        departure_city=booking["departure_city"],
        arrival_city=booking["arrival_city"],
        departure_time=dep_time.strftime("%B %d, %Y at %H:%M"),
        arrival_time=arr_time.strftime("%H:%M"),
        trip_type=booking["trip_type"],
        cabin_class=booking["cabin_class"],
        passenger_count=booking["passenger_count"],
        total_amount=booking["total_amount"],
        booking_status=booking["booking_status"],
        check_in_status=booking["check_in_status"],
        passengers=booking["passengers"],
        created_at=booking.get("created_at", ""),
    )
    cache_set(cache_key, out.model_dump(), ttl=300)
    return out


@router.get("/user/{user_id}", response_model=list[BookingOut])
def list_user_bookings(user_id: str, db: Session = Depends(get_db)):
    cache_key = f"bookings:user:{user_id}"
    cached = cache_get(cache_key)
    if cached:
        return [BookingOut(**b) for b in cached]
    bookings = get_user_bookings(db, user_id)
    result = []
    for b in bookings:
        if not b:
            continue
        dep_time = datetime.fromisoformat(b["departure_time"])
        arr_time = datetime.fromisoformat(b["arrival_time"])
        result.append(BookingOut(
            id=b["id"], pnr=b["pnr"], flight_number=b["flight_number"],
            airline_name=b["airline_name"], departure_city=b["departure_city"],
            arrival_city=b["arrival_city"],
            departure_time=dep_time.strftime("%B %d, %Y at %H:%M"),
            arrival_time=arr_time.strftime("%H:%M"),
            trip_type=b["trip_type"], cabin_class=b["cabin_class"],
            passenger_count=b["passenger_count"], total_amount=b["total_amount"],
            booking_status=b["booking_status"], check_in_status=b["check_in_status"],
            passengers=b["passengers"], created_at=b.get("created_at", ""),
        ))
    cache_set(cache_key, [b.model_dump() for b in result], ttl=120)
    return result


@router.put("/{pnr}/modify", response_model=dict)
def modify(pnr: str, data: BookingModify, db: Session = Depends(get_db)):
    result = modify_booking(db, pnr, data.new_flight_id, data.new_seat_numbers)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    cache_delete(f"booking:pnr:{pnr.upper()}")
    return result


@router.post("/{pnr}/cancel", response_model=dict)
def cancel(pnr: str, data: BookingCancel, db: Session = Depends(get_db)):
    result = cancel_booking(db, pnr, data.reason)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    cache_delete(f"booking:pnr:{pnr.upper()}")
    return result


@router.post("/check-in", response_model=dict)
def check_in(data: CheckInRequest, db: Session = Depends(get_db)):
    result = web_check_in(db, data.pnr, data.seat_number)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/boarding-pass/{pnr}", response_model=BoardingPass)
def boarding_pass(pnr: str, db: Session = Depends(get_db)):
    result = get_boarding_pass(db, pnr)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    dep_time = datetime.fromisoformat(result["departure_time"])
    board_time = datetime.fromisoformat(result["boarding_time"])
    return BoardingPass(
        pnr=result["pnr"],
        passenger_name=result["passenger_name"],
        flight_number=result["flight_number"],
        departure_city=result["departure_city"],
        arrival_city=result["arrival_city"],
        departure_time=dep_time.strftime("%B %d, %Y at %H:%M"),
        gate=result["gate"],
        seat=result["seat"],
        boarding_time=board_time.strftime("%H:%M"),
    )
