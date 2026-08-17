"""Admin router — Dashboard, manage flights, airports, bookings, refunds, users, reports, analytics."""

from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from auth import require_admin
import models
from schemas import FlightCreate, AnalyticsOut, PromotionCreate, CouponCreate, AirportCreate

router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])


# ── Dashboard ──────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=AnalyticsOut)
def dashboard(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    total_bookings = db.query(models.Booking).count()
    total_revenue = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.payment_status == models.PaymentStatus.SUCCESS
    ).scalar() or 0.0
    total_cancellations = db.query(models.Booking).filter(
        models.Booking.booking_status == models.BookingStatus.CANCELLED
    ).count()
    total_refunds = db.query(func.sum(models.Refund.refund_amount)).scalar() or 0.0
    active_flights = db.query(models.Flight).filter(models.Flight.is_active == True).count()
    total_users = db.query(models.User).count()

    # Popular routes
    popular = (
        db.query(
            models.Flight.departure_airport_id,
            models.Flight.arrival_airport_id,
            func.count(models.Booking.id).label("booking_count"),
        )
        .join(models.Booking, models.Booking.flight_id == models.Flight.id)
        .group_by(models.Flight.departure_airport_id, models.Flight.arrival_airport_id)
        .order_by(func.count(models.Booking.id).desc())
        .limit(5)
        .all()
    )
    popular_routes = []
    for dep_id, arr_id, count in popular:
        dep = db.query(models.Airport).filter(models.Airport.id == dep_id).first()
        arr = db.query(models.Airport).filter(models.Airport.id == arr_id).first()
        if dep and arr:
            popular_routes.append({
                "route": f"{dep.city} → {arr.city}",
                "bookings": count,
            })

    # Booking trends (last 7 days)
    today = date.today()
    trends = []
    for i in range(7):
        d = today - timedelta(days=6 - i)
        count = db.query(models.Booking).filter(
            func.date(models.Booking.created_at) == d
        ).count()
        trends.append({"date": d.isoformat(), "bookings": count})

    return AnalyticsOut(
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        total_cancellations=total_cancellations,
        total_refunds=total_refunds,
        active_flights=active_flights,
        total_users=total_users,
        popular_routes=popular_routes,
        booking_trends=trends,
    )


# ── Manage Flights ─────────────────────────────────────────────────────────

@router.get("/flights", response_model=list[dict])
def list_flights(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    flights = db.query(models.Flight).order_by(models.Flight.departure_time.desc()).all()
    return [
        {
            "id": f.id,
            "flight_number": f.flight_number,
            "airline_name": f.airline_name,
            "route": f"{f.departure_airport.city} → {f.arrival_airport.city}",
            "departure_time": f.departure_time.isoformat(),
            "status": f.status.value,
            "is_active": f.is_active,
        }
        for f in flights
    ]


@router.post("/flights", response_model=dict)
def create_flight(data: FlightCreate, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    dep = db.query(models.Airport).filter(models.Airport.code.ilike(data.departure_airport_code)).first()
    arr = db.query(models.Airport).filter(models.Airport.code.ilike(data.arrival_airport_code)).first()
    if not dep or not arr:
        raise HTTPException(status_code=400, detail="Airport code not found")

    flight = models.Flight(
        flight_number=data.flight_number,
        airline_name=data.airline_name,
        airline_code=data.airline_code,
        departure_airport_id=dep.id,
        arrival_airport_id=arr.id,
        departure_time=datetime.fromisoformat(data.departure_time),
        arrival_time=datetime.fromisoformat(data.arrival_time),
        duration_minutes=data.duration_minutes,
        aircraft=data.aircraft,
        total_seats=data.total_seats,
        price_economy=data.price_economy,
        price_premium_economy=data.price_premium_economy,
        price_business=data.price_business,
        price_first=data.price_first,
        cabin_baggage_kg=data.cabin_baggage_kg,
        checked_baggage_kg=data.checked_baggage_kg,
        seat_rows=data.seat_rows,
        seat_cols=data.seat_cols,
    )
    db.add(flight)
    db.flush()

    # Generate seats
    _generate_seats(db, flight)

    db.commit()
    return {"success": True, "flight_id": flight.id, "flight_number": flight.flight_number}


@router.put("/flights/{flight_id}/status", response_model=dict)
def update_flight_status(
    flight_id: str,
    status: str = Query(...),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    flight = db.query(models.Flight).filter(models.Flight.id == flight_id).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    valid_statuses = [s.value for s in models.FlightStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {valid_statuses}")
    flight.status = models.FlightStatus(status)
    db.commit()
    return {"success": True, "flight_id": flight_id, "status": status}


@router.delete("/flights/{flight_id}", response_model=dict)
def delete_flight(flight_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    flight = db.query(models.Flight).filter(models.Flight.id == flight_id).first()
    if not flight:
        raise HTTPException(status_code=404, detail="Flight not found")

    # Cascade: cancel all active bookings for this flight
    cancelled_count = 0
    refund_total = 0.0
    active_bookings = db.query(models.Booking).filter(
        models.Booking.flight_id == flight_id,
        models.Booking.booking_status.in_([
            models.BookingStatus.PENDING,
            models.BookingStatus.CONFIRMED,
            models.BookingStatus.MODIFIED,
        ]),
    ).all()

    for b in active_bookings:
        b.booking_status = models.BookingStatus.CANCELLED
        cancelled_count += 1

        # Full refund for flight cancellation
        refund = models.Refund(
            booking_id=b.id,
            refund_amount=b.total_amount,
            refund_status=models.RefundStatus.COMPLETED,
            reason=f"Flight {flight.flight_number} cancelled by admin",
        )
        db.add(refund)
        refund_total += b.total_amount

        # Free up seats
        for p in b.passengers:
            if p.seat_number:
                seat = db.query(models.Seat).filter(
                    models.Seat.flight_id == flight_id,
                    models.Seat.seat_number == p.seat_number,
                ).first()
                if seat:
                    seat.is_occupied = False

    flight.is_active = False
    flight.status = models.FlightStatus.CANCELLED
    db.commit()
    return {
        "success": True,
        "message": f"Flight deactivated. {cancelled_count} bookings cancelled, ₹{refund_total:,.0f} refunded.",
        "cancelled_bookings": cancelled_count,
        "refund_total": refund_total,
    }


# ── Manage Bookings ────────────────────────────────────────────────────────

@router.get("/bookings", response_model=list[dict])
def list_all_bookings(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    bookings = db.query(models.Booking).order_by(models.Booking.created_at.desc()).all()
    result = []
    for b in bookings:
        # Build passenger details with validation status
        passengers = []
        for p in b.passengers:
            validations = []
            # Name validation
            if p.full_name and len(p.full_name) >= 2:
                validations.append({"field": "name", "valid": True, "message": "OK"})
            else:
                validations.append({"field": "name", "valid": False, "message": "Name too short or missing"})
            # Age validation
            if p.age is not None and 1 <= p.age <= 120:
                validations.append({"field": "age", "valid": True, "message": "OK"})
            else:
                validations.append({"field": "age", "valid": False, "message": "Age missing or out of range"})
            # Gender validation
            if p.gender and p.gender in ("male", "female", "other"):
                validations.append({"field": "gender", "valid": True, "message": "OK"})
            else:
                validations.append({"field": "gender", "valid": False, "message": "Gender not specified"})
            # Seat validation
            if p.seat_number:
                validations.append({"field": "seat", "valid": True, "message": f"Seat {p.seat_number}"})
            else:
                validations.append({"field": "seat", "valid": False, "message": "No seat selected"})
            # Meal validation
            if p.meal_preference and p.meal_preference != "none":
                validations.append({"field": "meal", "valid": True, "message": p.meal_preference})
            else:
                validations.append({"field": "meal", "valid": False, "message": "No meal preference"})
            # Passport validation (optional but flagged)
            if p.passport_number:
                validations.append({"field": "passport", "valid": True, "message": "Provided"})
            else:
                validations.append({"field": "passport", "valid": False, "message": "Not provided (optional)"})

            all_valid = all(v["valid"] for v in validations if v["field"] != "passport")
            passengers.append({
                "id": p.id,
                "full_name": p.full_name,
                "age": p.age,
                "gender": p.gender,
                "seat_number": p.seat_number,
                "meal_preference": p.meal_preference,
                "passport_number": p.passport_number,
                "is_primary": p.is_primary,
                "validations": validations,
                "all_valid": all_valid,
            })

        # Contact validation
        contact_validations = []
        import re as _re
        if b.contact_email and _re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', b.contact_email):
            contact_validations.append({"field": "email", "valid": True, "message": b.contact_email})
        else:
            contact_validations.append({"field": "email", "valid": False, "message": "Invalid or missing"})
        if b.contact_phone and _re.match(r'^\+?\d{10,15}$', b.contact_phone):
            contact_validations.append({"field": "phone", "valid": True, "message": b.contact_phone})
        else:
            contact_validations.append({"field": "phone", "valid": False, "message": "Invalid or missing"})

        result.append({
            "id": b.id,
            "pnr": b.pnr,
            "flight_number": b.flight.flight_number,
            "route": f"{b.flight.departure_airport.city} → {b.flight.arrival_airport.city}",
            "passenger_count": b.passenger_count,
            "total_amount": b.total_amount,
            "booking_status": b.booking_status.value,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "contact_email": b.contact_email,
            "contact_phone": b.contact_phone,
            "travel_insurance": b.travel_insurance,
            "extra_baggage_kg": b.extra_baggage_kg,
            "cabin_class": b.cabin_class.value if b.cabin_class else "economy",
            "passengers": passengers,
            "contact_validations": contact_validations,
            "all_valid": all(p["all_valid"] for p in passengers) and all(v["valid"] for v in contact_validations),
        })
    return result


@router.put("/bookings/{booking_id}/status", response_model=dict)
def update_booking_status(
    booking_id: str,
    status: str = Query(...),
    reason: str = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Update booking status. If cancelling, create refund and free seats."""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    valid_statuses = [s.value for s in models.BookingStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {valid_statuses}")

    old_status = booking.booking_status.value
    booking.booking_status = models.BookingStatus(status)

    # If cancelling, create refund and free seats
    if status == "cancelled" and old_status != "cancelled":
        fee_map = {"economy": 500, "premium_economy": 750, "business": 1000, "first": 1500}
        fee = fee_map.get(booking.cabin_class.value, 500)
        refund_amount = max(0, booking.total_amount - fee)
        refund = models.Refund(
            booking_id=booking.id,
            refund_amount=refund_amount,
            refund_status=models.RefundStatus.PROCESSING,
            reason=reason or f"Cancelled by admin (was {old_status})",
        )
        db.add(refund)
        # Free seats
        for p in booking.passengers:
            if p.seat_number:
                seat = db.query(models.Seat).filter(
                    models.Seat.flight_id == booking.flight_id,
                    models.Seat.seat_number == p.seat_number,
                ).first()
                if seat:
                    seat.is_occupied = False

    # If confirming, mark as confirmed
    if status == "confirmed":
        booking.check_in_status = models.CheckInStatus.NOT_CHECKED_IN

    db.commit()
    return {"success": True, "booking_id": booking_id, "old_status": old_status, "new_status": status}


@router.put("/bookings/{booking_id}/passenger/{passenger_id}", response_model=dict)
def update_passenger(
    booking_id: str,
    passenger_id: str,
    full_name: str = Query(None),
    age: int = Query(None),
    gender: str = Query(None),
    seat_number: str = Query(None),
    meal_preference: str = Query(None),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Update a passenger's details."""
    passenger = db.query(models.Passenger).filter(
        models.Passenger.id == passenger_id,
        models.Passenger.booking_id == booking_id,
    ).first()
    if not passenger:
        raise HTTPException(status_code=404, detail="Passenger not found")

    if full_name is not None:
        passenger.full_name = full_name
    if age is not None:
        passenger.age = age
    if gender is not None:
        passenger.gender = gender
    if seat_number is not None:
        # Free old seat
        if passenger.seat_number:
            old_seat = db.query(models.Seat).filter(
                models.Seat.flight_id == passenger.booking.flight_id,
                models.Seat.seat_number == passenger.seat_number,
            ).first()
            if old_seat:
                old_seat.is_occupied = False
        # Occupy new seat
        if seat_number:
            new_seat = db.query(models.Seat).filter(
                models.Seat.flight_id == passenger.booking.flight_id,
                models.Seat.seat_number == seat_number,
            ).first()
            if new_seat:
                if new_seat.is_occupied:
                    raise HTTPException(status_code=400, detail=f"Seat {seat_number} is already occupied")
                new_seat.is_occupied = True
        passenger.seat_number = seat_number or None
    if meal_preference is not None:
        passenger.meal_preference = meal_preference

    db.commit()
    return {"success": True, "passenger_id": passenger_id}


@router.get("/flights/{flight_id}/seats", response_model=list[dict])
def get_flight_seats(flight_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    """Get all seats for a flight with occupancy status."""
    seats = db.query(models.Seat).filter(models.Seat.flight_id == flight_id).order_by(models.Seat.seat_number).all()
    return [
        {
            "id": s.id,
            "seat_number": s.seat_number,
            "cabin_class": s.cabin_class.value,
            "is_occupied": s.is_occupied,
            "is_window": s.is_window,
            "is_aisle": s.is_aisle,
            "extra_legroom": s.extra_legroom,
            "price": s.price,
        }
        for s in seats
    ]


# ── Manage Refunds ─────────────────────────────────────────────────────────

@router.get("/refunds", response_model=list[dict])
def list_refunds(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    refunds = db.query(models.Refund).order_by(models.Refund.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "booking_pnr": r.booking.pnr,
            "refund_amount": r.refund_amount,
            "refund_status": r.refund_status.value,
            "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in refunds
    ]


@router.put("/refunds/{refund_id}/status", response_model=dict)
def update_refund_status(
    refund_id: str,
    status: str = Query(...),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    refund = db.query(models.Refund).filter(models.Refund.id == refund_id).first()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    valid_statuses = [s.value for s in models.RefundStatus]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {valid_statuses}")
    refund.refund_status = models.RefundStatus(status)
    if status == "completed":
        from datetime import datetime, timezone
        refund.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "refund_id": refund_id, "status": status}


# ── Manage Users ───────────────────────────────────────────────────────────

@router.get("/users", response_model=list[dict])
def list_users(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    users = db.query(models.User).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "phone": u.phone,
            "is_guest": u.is_guest,
            "is_verified": u.is_verified,
            "role": u.role.value,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


# ── Chat History ───────────────────────────────────────────────────────────

@router.get("/chat-history", response_model=list[dict])
def chat_history(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    conversations = db.query(models.Conversation).order_by(models.Conversation.created_at.desc()).limit(50).all()
    return [
        {
            "id": c.id,
            "session_id": c.session_id,
            "is_escalated": c.is_escalated,
            "summary": c.summary,
            "message_count": len(c.messages),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in conversations
    ]


# ── AI Responses ───────────────────────────────────────────────────────────

@router.get("/ai-responses", response_model=list[dict])
def ai_responses(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    messages = db.query(models.Message).filter(models.Message.role == "assistant").order_by(
        models.Message.created_at.desc()
    ).limit(50).all()
    return [
        {
            "id": m.id,
            "intent": m.intent,
            "content": m.content[:200],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]


# ── Helper ─────────────────────────────────────────────────────────────────

def _generate_seats(db: Session, flight: models.Flight):
    """Generate seat records for a flight."""
    cols = "ABCDEF"[:flight.seat_cols]
    for row in range(1, flight.seat_rows + 1):
        for col_idx, col in enumerate(cols):
            seat_num = f"{row}{col}"
            # Determine cabin class by row
            if row <= 2:
                cabin = models.CabinClass.FIRST
                price = 500
            elif row <= 6:
                cabin = models.CabinClass.BUSINESS
                price = 300
            elif row <= 12:
                cabin = models.CabinClass.PREMIUM_ECONOMY
                price = 150
            else:
                cabin = models.CabinClass.ECONOMY
                price = 0

            is_window = col_idx == 0 or col_idx == len(cols) - 1
            is_aisle = col_idx == flight.seat_cols // 2 - 1 or col_idx == flight.seat_cols // 2
            extra_legroom = row == 12 or row == 13

            seat = models.Seat(
                flight_id=flight.id,
                seat_number=seat_num,
                cabin_class=cabin,
                is_occupied=False,
                is_window=is_window,
                is_aisle=is_aisle,
                extra_legroom=extra_legroom,
                price=price,
            )
            db.add(seat)


# ── Manage Airports (CRUD) ──────────────────────────────────────────────────

@router.get("/airports", response_model=list[dict])
def list_airports_admin(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    airports = db.query(models.Airport).order_by(models.Airport.city).all()
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "city": a.city,
            "country": a.country,
            "timezone": a.timezone,
            "terminals": a.terminals,
        }
        for a in airports
    ]


@router.post("/airports", response_model=dict)
def create_airport(data: AirportCreate, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    existing = db.query(models.Airport).filter(models.Airport.code.ilike(data.code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Airport code already exists")
    airport = models.Airport(
        code=data.code.upper(),
        name=data.name,
        city=data.city,
        country=data.country,
        timezone=data.timezone,
        terminals=data.terminals,
    )
    db.add(airport)
    db.commit()
    return {"success": True, "airport_id": airport.id, "code": airport.code}


@router.put("/airports/{airport_id}", response_model=dict)
def update_airport(airport_id: str, data: AirportCreate, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    airport = db.query(models.Airport).filter(models.Airport.id == airport_id).first()
    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")
    airport.code = data.code.upper()
    airport.name = data.name
    airport.city = data.city
    airport.country = data.country
    airport.timezone = data.timezone
    airport.terminals = data.terminals
    db.commit()
    return {"success": True, "airport_id": airport_id}


@router.delete("/airports/{airport_id}", response_model=dict)
def delete_airport(airport_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    airport = db.query(models.Airport).filter(models.Airport.id == airport_id).first()
    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")
    has_flights = db.query(models.Flight).filter(
        (models.Flight.departure_airport_id == airport_id) | (models.Flight.arrival_airport_id == airport_id)
    ).first()
    if has_flights:
        raise HTTPException(status_code=400, detail="Cannot delete airport with associated flights")
    db.delete(airport)
    db.commit()
    return {"success": True, "message": "Airport deleted"}


# ── Manage Promotions ───────────────────────────────────────────────────────

@router.get("/promotions", response_model=list[dict])
def list_promotions(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    promos = db.query(models.Promotion).order_by(models.Promotion.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "discount_type": p.discount_type,
            "discount_value": p.discount_value,
            "promo_code": p.promo_code,
            "valid_from": p.valid_from.isoformat() if p.valid_from else None,
            "valid_until": p.valid_until.isoformat() if p.valid_until else None,
            "is_active": p.is_active,
            "max_uses": p.max_uses,
            "used_count": p.used_count,
        }
        for p in promos
    ]


@router.post("/promotions", response_model=dict)
def create_promotion(data: PromotionCreate, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    existing = db.query(models.Promotion).filter(models.Promotion.promo_code.ilike(data.promo_code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Promo code already exists")
    promo = models.Promotion(
        title=data.title,
        description=data.description,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        promo_code=data.promo_code.upper(),
        valid_from=data.valid_from or date.today(),
        valid_until=data.valid_until,
        max_uses=data.max_uses,
    )
    db.add(promo)
    db.commit()
    return {"success": True, "promotion_id": promo.id, "promo_code": promo.promo_code}


@router.put("/promotions/{promo_id}/toggle", response_model=dict)
def toggle_promotion(promo_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    promo.is_active = not promo.is_active
    db.commit()
    return {"success": True, "is_active": promo.is_active}


@router.delete("/promotions/{promo_id}", response_model=dict)
def delete_promotion(promo_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    promo = db.query(models.Promotion).filter(models.Promotion.id == promo_id).first()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    db.delete(promo)
    db.commit()
    return {"success": True, "message": "Promotion deleted"}


# ── Manage Coupons ──────────────────────────────────────────────────────────

@router.get("/coupons", response_model=list[dict])
def list_coupons(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    coupons = db.query(models.Coupon).order_by(models.Coupon.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "discount_type": c.discount_type,
            "discount_value": c.discount_value,
            "min_booking_amount": c.min_booking_amount,
            "max_discount_amount": c.max_discount_amount,
            "valid_from": c.valid_from.isoformat() if c.valid_from else None,
            "valid_until": c.valid_until.isoformat() if c.valid_until else None,
            "is_active": c.is_active,
            "max_uses": c.max_uses,
            "used_count": c.used_count,
        }
        for c in coupons
    ]


@router.post("/coupons", response_model=dict)
def create_coupon(data: CouponCreate, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    existing = db.query(models.Coupon).filter(models.Coupon.code.ilike(data.code)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")
    coupon = models.Coupon(
        code=data.code.upper(),
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        min_booking_amount=data.min_booking_amount,
        max_discount_amount=data.max_discount_amount,
        valid_from=data.valid_from or date.today(),
        valid_until=data.valid_until,
        max_uses=data.max_uses,
    )
    db.add(coupon)
    db.commit()
    return {"success": True, "coupon_id": coupon.id, "code": coupon.code}


@router.put("/coupons/{coupon_id}/toggle", response_model=dict)
def toggle_coupon(coupon_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    coupon.is_active = not coupon.is_active
    db.commit()
    return {"success": True, "is_active": coupon.is_active}


@router.delete("/coupons/{coupon_id}", response_model=dict)
def delete_coupon(coupon_id: str, db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    coupon = db.query(models.Coupon).filter(models.Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.delete(coupon)
    db.commit()
    return {"success": True, "message": "Coupon deleted"}


# ── CSAT (Customer Satisfaction) ────────────────────────────────────────────

@router.get("/csat", response_model=dict)
def csat_stats(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    total = db.query(models.CSAT).count()
    avg_rating = db.query(func.avg(models.CSAT.rating)).scalar() or 0.0
    distribution = {}
    for i in range(1, 6):
        distribution[i] = db.query(models.CSAT).filter(models.CSAT.rating == i).count()
    recent = db.query(models.CSAT).order_by(models.CSAT.created_at.desc()).limit(20).all()
    recent_list = [
        {
            "id": r.id,
            "session_id": r.session_id,
            "rating": r.rating,
            "feedback": r.feedback,
            "intent": r.intent,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent
    ]
    return {
        "total_ratings": total,
        "average_rating": round(avg_rating, 2),
        "distribution": distribution,
        "recent": recent_list,
    }


# ── Reports ─────────────────────────────────────────────────────────────────

@router.get("/reports/booking-summary", response_model=dict)
def booking_summary_report(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    total = db.query(models.Booking).count()
    by_status = {}
    for s in models.BookingStatus:
        by_status[s.value] = db.query(models.Booking).filter(models.Booking.booking_status == s).count()
    by_cabin = {}
    for c in models.CabinClass:
        by_cabin[c.value] = db.query(models.Booking).filter(models.Booking.cabin_class == c).count()
    revenue_by_cabin = {}
    for c in models.CabinClass:
        revenue = db.query(func.sum(models.Booking.total_amount)).filter(
            models.Booking.cabin_class == c,
            models.Booking.booking_status == models.BookingStatus.CONFIRMED,
        ).scalar() or 0.0
        revenue_by_cabin[c.value] = revenue
    return {
        "total_bookings": total,
        "by_status": by_status,
        "by_cabin_class": by_cabin,
        "revenue_by_cabin": revenue_by_cabin,
    }


@router.get("/reports/cancellation", response_model=dict)
def cancellation_report(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    total_cancelled = db.query(models.Booking).filter(
        models.Booking.booking_status == models.BookingStatus.CANCELLED
    ).count()
    total_refunded = db.query(func.sum(models.Refund.refund_amount)).filter(
        models.Refund.refund_status == models.RefundStatus.COMPLETED
    ).scalar() or 0.0
    pending_refunds = db.query(models.Refund).filter(
        models.Refund.refund_status.in_([models.RefundStatus.REQUESTED, models.RefundStatus.PROCESSING])
    ).count()
    reasons = db.query(
        models.Refund.reason, func.count(models.Refund.id)
    ).group_by(models.Refund.reason).all()
    return {
        "total_cancelled": total_cancelled,
        "total_refunded": round(total_refunded, 2),
        "pending_refunds": pending_refunds,
        "cancellation_reasons": [{"reason": r or "Not specified", "count": c} for r, c in reasons],
    }


@router.get("/reports/revenue", response_model=dict)
def revenue_report(db: Session = Depends(get_db), admin: models.User = Depends(require_admin)):
    total_revenue = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.payment_status == models.PaymentStatus.SUCCESS
    ).scalar() or 0.0
    monthly = []
    for i in range(6):
        m_start = date.today().replace(day=1) - timedelta(days=30 * i)
        m_end = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        rev = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.payment_status == models.PaymentStatus.SUCCESS,
            func.date(models.Transaction.created_at) >= m_start,
            func.date(models.Transaction.created_at) <= m_end,
        ).scalar() or 0.0
        monthly.append({"month": m_start.strftime("%b %Y"), "revenue": round(rev, 2)})
    monthly.reverse()
    return {
        "total_revenue": round(total_revenue, 2),
        "monthly_revenue": monthly,
    }
