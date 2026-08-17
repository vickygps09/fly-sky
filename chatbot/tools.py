"""Tools/functions available to the airline chatbot agent.

These functions interact with the database to perform real operations:
- Flight search, seat selection, booking creation
- Booking modification, cancellation, refund status
- Flight status, web check-in, boarding pass
- Baggage info, weather, currency conversion
"""

import random
import string
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

import models
from models import (
    Flight, Airport, Seat, Booking, Passenger, Transaction, Refund,
    NotificationLog, CabinClass, TripType, BookingStatus, PaymentStatus,
    RefundStatus, CheckInStatus, FlightStatus, NotificationType,
    Coupon, Promotion,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _generate_pnr() -> str:
    """Generate a 6-character PNR (alphanumeric, uppercase)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _generate_transaction_id() -> str:
    """Generate a mock transaction ID."""
    return "TXN" + ''.join(random.choices(string.digits, k=12))


def _get_airport_by_city(db: Session, city: str) -> Optional[Airport]:
    """Find airport by city name (case-insensitive)."""
    return db.query(Airport).filter(Airport.city.ilike(f"%{city}%")).first()


def _get_airport_by_code(db: Session, code: str) -> Optional[Airport]:
    """Find airport by IATA code (case-insensitive)."""
    return db.query(Airport).filter(Airport.code.ilike(code.strip())).first()


def _flight_to_dict(flight: Flight, cabin_class: str = "economy") -> dict:
    """Convert a Flight ORM object to a serializable dict."""
    price_map = {
        "economy": flight.price_economy,
        "premium_economy": flight.price_premium_economy,
        "business": flight.price_business,
        "first": flight.price_first,
    }
    price = price_map.get(cabin_class, flight.price_economy)

    occupied = db_query_occupied_seats_count(flight)
    available = flight.total_seats - occupied

    return {
        "id": flight.id,
        "flight_number": flight.flight_number,
        "airline_name": flight.airline_name,
        "departure_airport_code": flight.departure_airport.code,
        "departure_airport_city": flight.departure_airport.city,
        "arrival_airport_code": flight.arrival_airport.code,
        "arrival_airport_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
        "arrival_time": flight.arrival_time.isoformat(),
        "duration_minutes": flight.duration_minutes,
        "price": price,
        "cabin_class": cabin_class,
        "available_seats": available,
        "cabin_baggage_kg": flight.cabin_baggage_kg,
        "checked_baggage_kg": flight.checked_baggage_kg,
        "status": flight.status.value,
        "departure_lat": flight.departure_airport.latitude,
        "departure_lon": flight.departure_airport.longitude,
        "arrival_lat": flight.arrival_airport.latitude,
        "arrival_lon": flight.arrival_airport.longitude,
    }


def db_query_occupied_seats_count(flight: Flight) -> int:
    """Count occupied seats for a flight."""
    # Use the SQLAlchemy session from the flight's session
    session = Session.object_session(flight)
    if session is None:
        return 0
    return session.query(Seat).filter(Seat.flight_id == flight.id, Seat.is_occupied == True).count()


# ── Flight Search Tool ─────────────────────────────────────────────────────

def get_available_routes(db: Session) -> list:
    """Get all active flight routes as (departure_city, arrival_city) pairs."""
    from sqlalchemy import text
    result = db.execute(text(
        "SELECT DISTINCT da.city, aa.city "
        "FROM flights f "
        "JOIN airports da ON f.departure_airport_id = da.id "
        "JOIN airports aa ON f.arrival_airport_id = aa.id "
        "WHERE f.is_active = true "
        "ORDER BY da.city, aa.city"
    ))
    return [(r[0], r[1]) for r in result]


def validate_coupon(db: Session, code: str, booking_amount: float) -> dict:
    """Validate a coupon or promo code and return discount details.

    Checks both Coupon and Promotion tables. Returns discount amount and type.
    """
    code = code.strip().upper()

    # Try Coupon table first
    coupon = db.query(Coupon).filter(
        Coupon.code.ilike(code),
        Coupon.is_active == True,
    ).first()

    if coupon:
        # Check validity
        today = date.today()
        if coupon.valid_from and today < coupon.valid_from:
            return {"valid": False, "error": "Coupon is not yet active."}
        if coupon.valid_until and today > coupon.valid_until:
            return {"valid": False, "error": "Coupon has expired."}
        if coupon.used_count >= coupon.max_uses:
            return {"valid": False, "error": "Coupon usage limit reached."}
        if booking_amount < coupon.min_booking_amount:
            return {"valid": False, "error": f"Minimum booking amount is ₹{coupon.min_booking_amount:,}."}

        # Calculate discount
        if coupon.discount_type == "percentage":
            discount = booking_amount * (coupon.discount_value / 100)
            if coupon.max_discount_amount:
                discount = min(discount, coupon.max_discount_amount)
        else:
            discount = coupon.discount_value

        return {
            "valid": True,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": coupon.discount_value,
            "discount_amount": round(discount, 2),
            "final_amount": round(booking_amount - discount, 2),
        }

    # Try Promotion table
    promo = db.query(Promotion).filter(
        Promotion.promo_code.ilike(code),
        Promotion.is_active == True,
    ).first()

    if promo:
        today = date.today()
        if promo.valid_from and today < promo.valid_from:
            return {"valid": False, "error": "Promotion is not yet active."}
        if promo.valid_until and today > promo.valid_until:
            return {"valid": False, "error": "Promotion has expired."}
        if promo.used_count >= promo.max_uses:
            return {"valid": False, "error": "Promotion usage limit reached."}

        if promo.discount_type == "percentage":
            discount = booking_amount * (promo.discount_value / 100)
        else:
            discount = promo.discount_value

        return {
            "valid": True,
            "code": promo.promo_code,
            "discount_type": promo.discount_type,
            "discount_value": promo.discount_value,
            "discount_amount": round(discount, 2),
            "final_amount": round(booking_amount - discount, 2),
        }

    return {"valid": False, "error": f"Invalid code: {code}. Please check and try again."}


def search_flights(
    db: Session,
    departure_city: str,
    arrival_city: str,
    travel_date: date,
    passengers: int = 1,
    cabin_class: str = "economy",
    return_date: Optional[date] = None,
) -> List[dict]:
    """Search for available flights between two cities on a given date."""
    dep_airport = _get_airport_by_city(db, departure_city) or _get_airport_by_code(db, departure_city)
    arr_airport = _get_airport_by_city(db, arrival_city) or _get_airport_by_code(db, arrival_city)

    if not dep_airport:
        return {"error": f"Could not find airport for departure city: {departure_city}"}
    if not arr_airport:
        return {"error": f"Could not find airport for arrival city: {arrival_city}"}

    # Search flights on the given date
    day_start = datetime.combine(travel_date, datetime.min.time())
    day_end = datetime.combine(travel_date, datetime.max.time())

    flights = (
        db.query(Flight)
        .filter(
            Flight.departure_airport_id == dep_airport.id,
            Flight.arrival_airport_id == arr_airport.id,
            Flight.departure_time >= day_start,
            Flight.departure_time <= day_end,
            Flight.is_active == True,
        )
        .order_by(Flight.departure_time)
        .all()
    )

    outbound = [_flight_to_dict(f, cabin_class) for f in flights]

    result = {
        "outbound_flights": outbound,
        "departure_city": dep_airport.city,
        "arrival_city": arr_airport.city,
        "travel_date": travel_date.isoformat(),
        "cabin_class": cabin_class,
        "passengers": passengers,
    }

    if return_date and return_date > travel_date:
        r_start = datetime.combine(return_date, datetime.min.time())
        r_end = datetime.combine(return_date, datetime.max.time())
        return_flights = (
            db.query(Flight)
            .filter(
                Flight.departure_airport_id == arr_airport.id,
                Flight.arrival_airport_id == dep_airport.id,
                Flight.departure_time >= r_start,
                Flight.departure_time <= r_end,
                Flight.is_active == True,
            )
            .order_by(Flight.departure_time)
            .all()
        )
        result["return_flights"] = [_flight_to_dict(f, cabin_class) for f in return_flights]

    return result


# ── Seat Map Tool ──────────────────────────────────────────────────────────

def get_seat_map(db: Session, flight_id: str, cabin_class: Optional[str] = None) -> List[dict]:
    """Get available seats for a flight, optionally filtered by cabin class."""
    query = db.query(Seat).filter(Seat.flight_id == flight_id)
    if cabin_class:
        try:
            cabin_enum = CabinClass(cabin_class)
            query = query.filter(Seat.cabin_class == cabin_enum)
        except (ValueError, KeyError):
            pass
    seats = query.order_by(Seat.seat_number).all()
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


def select_seat(db: Session, flight_id: str, seat_number: str) -> dict:
    """Select a seat on a flight."""
    seat = db.query(Seat).filter(
        Seat.flight_id == flight_id,
        Seat.seat_number == seat_number,
    ).first()

    if not seat:
        return {"error": f"Seat {seat_number} not found on this flight."}
    if seat.is_occupied:
        return {"error": f"Seat {seat_number} is already occupied. Please choose another seat."}

    seat.is_occupied = True
    db.commit()
    return {"success": True, "seat_number": seat_number, "price": seat.price}


# ── Booking Tools ──────────────────────────────────────────────────────────

def create_booking(
    db: Session,
    flight_id: str,
    passengers: List[dict],
    cabin_class: str = "economy",
    trip_type: str = "one_way",
    return_flight_id: Optional[str] = None,
    user_id: Optional[str] = None,
    contact_email: Optional[str] = None,
    contact_phone: Optional[str] = None,
    travel_insurance: bool = False,
    extra_baggage_kg: float = 0.0,
) -> dict:
    """Create a new booking."""
    flight = db.query(Flight).filter(Flight.id == flight_id).first()
    if not flight:
        return {"error": "Flight not found."}

    price_map = {
        "economy": flight.price_economy,
        "premium_economy": flight.price_premium_economy,
        "business": flight.price_business,
        "first": flight.price_first,
    }
    base_price = price_map.get(cabin_class, flight.price_economy)
    total = base_price * len(passengers)

    # Add extra baggage fee
    baggage_cost = 0
    if extra_baggage_kg and extra_baggage_kg > 0:
        baggage_cost = {5: 500, 10: 900, 20: 1500}.get(int(extra_baggage_kg), int(extra_baggage_kg) * 100)
        total += baggage_cost

    # Add travel insurance
    if travel_insurance:
        total += 200

    # Add seat selection fees — validate seat availability and cabin class
    for p in passengers:
        if p.get("seat_number"):
            seat = db.query(Seat).filter(
                Seat.flight_id == flight_id,
                Seat.seat_number == p["seat_number"],
            ).first()
            if not seat:
                return {"error": f"Seat {p['seat_number']} not found on this flight."}
            if seat.is_occupied:
                return {"error": f"Seat {p['seat_number']} is already occupied. Please choose another seat."}
            if seat.cabin_class.value != cabin_class:
                return {"error": f"Seat {p['seat_number']} is in {seat.cabin_class.value} class. Your booking is for {cabin_class} class."}
            total += seat.price
            seat.is_occupied = True

    booking = Booking(
        pnr=_generate_pnr(),
        user_id=user_id,
        flight_id=flight_id,
        return_flight_id=return_flight_id,
        trip_type=TripType(trip_type),
        cabin_class=CabinClass(cabin_class),
        passenger_count=len(passengers),
        total_amount=total,
        booking_status=BookingStatus.PENDING,
        departure_date=flight.departure_time.date(),
        contact_email=contact_email,
        contact_phone=contact_phone,
        travel_insurance=travel_insurance,
        extra_baggage_kg=extra_baggage_kg,
    )
    db.add(booking)
    db.flush()

    for p in passengers:
        passenger = Passenger(
            booking_id=booking.id,
            full_name=p["full_name"],
            age=p.get("age"),
            gender=p.get("gender"),
            seat_number=p.get("seat_number"),
            passport_number=p.get("passport_number"),
            meal_preference=p.get("meal_preference"),
            is_primary=p.get("is_primary", False),
        )
        db.add(passenger)

    db.commit()
    return {
        "success": True,
        "booking_id": booking.id,
        "pnr": booking.pnr,
        "total_amount": total,
        "base_fare": base_price * len(passengers),
        "baggage_cost": baggage_cost,
        "insurance_cost": 200 if travel_insurance else 0,
        "extra_baggage_kg": extra_baggage_kg,
        "travel_insurance": travel_insurance,
        "flight_number": flight.flight_number,
        "departure_city": flight.departure_airport.city,
        "arrival_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
    }


def get_booking_by_pnr(db: Session, pnr: str) -> Optional[dict]:
    """Get booking details by PNR."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return None

    flight = booking.flight
    passengers = [
        {
            "full_name": p.full_name,
            "age": p.age,
            "gender": p.gender,
            "seat_number": p.seat_number,
            "meal_preference": p.meal_preference,
            "is_primary": p.is_primary,
        }
        for p in booking.passengers
    ]

    return {
        "id": booking.id,
        "pnr": booking.pnr,
        "flight_id": booking.flight_id,
        "flight_number": flight.flight_number,
        "airline_name": flight.airline_name,
        "departure_city": flight.departure_airport.city,
        "arrival_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
        "arrival_time": flight.arrival_time.isoformat(),
        "trip_type": booking.trip_type.value,
        "cabin_class": booking.cabin_class.value,
        "passenger_count": booking.passenger_count,
        "total_amount": booking.total_amount,
        "extra_baggage_kg": booking.extra_baggage_kg,
        "cabin_baggage_kg": flight.cabin_baggage_kg,
        "checked_baggage_kg": flight.checked_baggage_kg,
        "travel_insurance": booking.travel_insurance,
        "booking_status": booking.booking_status.value,
        "check_in_status": booking.check_in_status.value,
        "passengers": passengers,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
    }


def get_user_bookings(db: Session, user_id: str) -> List[dict]:
    """Get all bookings for a user."""
    bookings = db.query(Booking).filter(Booking.user_id == user_id).order_by(Booking.created_at.desc()).all()
    return [get_booking_by_pnr(db, b.pnr) for b in bookings if b.pnr]


def get_bookings_by_email(db: Session, email: str) -> List[dict]:
    """Get all bookings by contact email (for guest users)."""
    bookings = db.query(Booking).filter(
        Booking.contact_email.ilike(email.strip())
    ).order_by(Booking.created_at.desc()).all()
    return [get_booking_by_pnr(db, b.pnr) for b in bookings if b.pnr]


def cancel_booking(db: Session, pnr: str, reason: Optional[str] = None) -> dict:
    """Cancel a booking by PNR."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return {"error": f"No booking found with PNR: {pnr}"}

    if booking.booking_status == BookingStatus.CANCELLED:
        return {"error": "This booking is already cancelled."}

    # Calculate cancellation fee
    fee_map = {
        "economy": 500, "premium_economy": 1000, "business": 1500, "first": 2000,
    }
    fee = fee_map.get(booking.cabin_class.value, 500)
    refund_amount = max(0, booking.total_amount - fee)

    booking.booking_status = BookingStatus.CANCELLED

    # Create refund record
    refund = Refund(
        booking_id=booking.id,
        refund_amount=refund_amount,
        refund_status=RefundStatus.PROCESSING,
        reason=reason or "Customer cancellation",
    )
    db.add(refund)

    # Free up seats
    for seat in db.query(Seat).filter(Seat.flight_id == booking.flight_id).all():
        for p in booking.passengers:
            if p.seat_number and seat.seat_number == p.seat_number:
                seat.is_occupied = False

    db.commit()
    return {
        "success": True,
        "pnr": booking.pnr,
        "refund_amount": refund_amount,
        "cancellation_fee": fee,
        "refund_status": "processing",
        "message": f"Booking {booking.pnr} has been cancelled. Refund of ₹{refund_amount} will be processed in 5-7 business days.",
    }


def modify_booking(db: Session, pnr: str, new_flight_id: Optional[str] = None, new_seat_numbers: Optional[List[str]] = None, add_passengers: Optional[List[dict]] = None) -> dict:
    """Modify a booking — change flight, seats, or add passengers."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return {"error": f"No booking found with PNR: {pnr}"}

    if booking.booking_status in [BookingStatus.CANCELLED, BookingStatus.REFUNDED]:
        return {"error": "Cannot modify a cancelled or refunded booking."}

    modification_fee = 500
    changes = []

    if new_flight_id:
        new_flight = db.query(Flight).filter(Flight.id == new_flight_id).first()
        if not new_flight:
            return {"error": "New flight not found."}

        # Free old seats
        for seat in db.query(Seat).filter(Seat.flight_id == booking.flight_id).all():
            for p in booking.passengers:
                if p.seat_number and seat.seat_number == p.seat_number:
                    seat.is_occupied = False

        booking.flight_id = new_flight_id
        booking.departure_date = new_flight.departure_time.date()

        price_map = {
            "economy": new_flight.price_economy,
            "premium_economy": new_flight.price_premium_economy,
            "business": new_flight.price_business,
            "first": new_flight.price_first,
        }
        new_price = price_map.get(booking.cabin_class.value, new_flight.price_economy) * booking.passenger_count
        booking.total_amount = new_price + modification_fee
        changes.append(f"Flight changed to {new_flight.flight_number}")

    if new_seat_numbers:
        for i, seat_num in enumerate(new_seat_numbers):
            if i < len(booking.passengers):
                seat = db.query(Seat).filter(
                    Seat.flight_id == booking.flight_id,
                    Seat.seat_number == seat_num,
                ).first()
                if not seat:
                    return {"error": f"Seat {seat_num} not found on this flight."}
                if seat.is_occupied:
                    return {"error": f"Seat {seat_num} is already occupied."}
                if seat.cabin_class != booking.cabin_class:
                    return {"error": f"Seat {seat_num} is in {seat.cabin_class.value} class. Your booking is for {booking.cabin_class.value} class."}
                # Free old seat if passenger had one
                if booking.passengers[i].seat_number:
                    old_seat = db.query(Seat).filter(
                        Seat.flight_id == booking.flight_id,
                        Seat.seat_number == booking.passengers[i].seat_number,
                    ).first()
                    if old_seat:
                        old_seat.is_occupied = False
                booking.passengers[i].seat_number = seat_num
                seat.is_occupied = True
                changes.append(f"Seat changed to {seat_num}")

    if add_passengers:
        flight = booking.flight
        price_map = {
            "economy": flight.price_economy,
            "premium_economy": flight.price_premium_economy,
            "business": flight.price_business,
            "first": flight.price_first,
        }
        per_pax_price = price_map.get(booking.cabin_class.value, flight.price_economy)
        for pax_data in add_passengers:
            new_pax = Passenger(
                booking_id=booking.id,
                full_name=pax_data.get("full_name", "Passenger"),
                age=pax_data.get("age"),
                gender=pax_data.get("gender"),
                seat_number=pax_data.get("seat_number"),
                meal_preference=pax_data.get("meal_preference", "none"),
                is_primary=False,
            )
            db.add(new_pax)
            # Assign seat if provided — validate availability and cabin class
            if pax_data.get("seat_number"):
                seat = db.query(Seat).filter(
                    Seat.flight_id == booking.flight_id,
                    Seat.seat_number == pax_data["seat_number"],
                ).first()
                if not seat:
                    return {"error": f"Seat {pax_data['seat_number']} not found on this flight."}
                if seat.is_occupied:
                    return {"error": f"Seat {pax_data['seat_number']} is already occupied."}
                if seat.cabin_class != booking.cabin_class:
                    return {"error": f"Seat {pax_data['seat_number']} is in {seat.cabin_class.value} class. Your booking is for {booking.cabin_class.value} class."}
                seat.is_occupied = True
            booking.total_amount += per_pax_price
            changes.append(f"Added passenger: {pax_data.get('full_name', 'Passenger')}")

    booking.booking_status = BookingStatus.MODIFIED
    booking.total_amount += modification_fee
    db.commit()

    return {
        "success": True,
        "pnr": booking.pnr,
        "changes": changes,
        "modification_fee": modification_fee,
        "new_total": booking.total_amount,
    }


# ── Payment Tools ──────────────────────────────────────────────────────────

def initiate_payment(db: Session, booking_id: str, payment_method: str = "card") -> dict:
    """Initiate a mock payment for a booking."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return {"error": "Booking not found."}

    txn = Transaction(
        booking_id=booking_id,
        amount=booking.total_amount,
        payment_method=payment_method,
        payment_status=PaymentStatus.INITIATED,
    )
    db.add(txn)
    db.commit()

    return {
        "success": True,
        "transaction_id": txn.id,
        "amount": booking.total_amount,
        "currency": "INR",
        "payment_url": f"/api/payments/process/{txn.id}",
        "message": f"Payment of ₹{booking.total_amount} initiated. Please complete the payment to confirm your booking.",
    }


def confirm_payment(db: Session, transaction_id: str, success: bool = True) -> dict:
    """Confirm a payment (mock — always succeeds unless success=False)."""
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        return {"error": "Transaction not found."}

    booking = db.query(Booking).filter(Booking.id == txn.booking_id).first()

    if success:
        txn.payment_status = PaymentStatus.SUCCESS
        txn.transaction_id = _generate_transaction_id()
        if booking:
            booking.booking_status = BookingStatus.CONFIRMED
    else:
        txn.payment_status = PaymentStatus.FAILED

    db.commit()

    if success and booking:
        return {
            "success": True,
            "pnr": booking.pnr,
            "amount": txn.amount,
            "transaction_id": txn.transaction_id,
            "message": f"Payment successful! Your booking is confirmed. PNR: {booking.pnr}",
        }
    return {"success": False, "message": "Payment failed. Please try again."}


# ── Refund Tools ───────────────────────────────────────────────────────────

def get_refund_status(db: Session, pnr: str) -> dict:
    """Check refund status for a booking."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return {"error": f"No booking found with PNR: {pnr}"}

    refunds = db.query(Refund).filter(Refund.booking_id == booking.id).all()
    if not refunds:
        return {"message": f"No refund found for PNR {pnr}. This booking has not been cancelled."}

    return {
        "pnr": booking.pnr,
        "booking_status": booking.booking_status.value,
        "refunds": [
            {
                "amount": r.refund_amount,
                "status": r.refund_status.value,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in refunds
        ],
    }


# ── Flight Status Tool ─────────────────────────────────────────────────────

def get_flight_status(db: Session, flight_number: str) -> dict:
    """Get real-time flight status."""
    flight = db.query(Flight).filter(Flight.flight_number.ilike(flight_number.strip())).first()
    if not flight:
        return {"error": f"Flight {flight_number} not found."}

    delay = 0
    if flight.status == FlightStatus.DELAYED:
        delay = random.randint(15, 120)

    gate = f"{random.choice('ABCDEF')}{random.randint(1, 30)}"

    return {
        "flight_number": flight.flight_number,
        "airline_name": flight.airline_name,
        "status": flight.status.value,
        "departure_city": flight.departure_airport.city,
        "arrival_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
        "arrival_time": flight.arrival_time.isoformat(),
        "delay_minutes": delay if delay > 0 else None,
        "gate": gate,
    }


# ── Check-in & Boarding Pass Tools ─────────────────────────────────────────

def web_check_in(db: Session, pnr: str, seat_number: Optional[str] = None) -> dict:
    """Perform web check-in for a booking."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return {"error": f"No booking found with PNR: {pnr}"}

    if booking.booking_status != BookingStatus.CONFIRMED:
        return {"error": f"Booking {pnr} is not confirmed. Cannot check in."}

    if booking.check_in_status != CheckInStatus.NOT_CHECKED_IN:
        return {"error": f"Already checked in for PNR {pnr}."}

    # Assign seat
    assigned_seat = None
    if seat_number:
        seat = db.query(Seat).filter(
            Seat.flight_id == booking.flight_id,
            Seat.seat_number == seat_number,
        ).first()
        if not seat:
            return {"error": f"Seat {seat_number} not found on this flight."}
        if seat.is_occupied:
            return {"error": f"Seat {seat_number} is already occupied. Please choose another seat."}
        if seat.cabin_class != booking.cabin_class:
            return {"error": f"Seat {seat_number} is in {seat.cabin_class.value} class. Your booking is for {booking.cabin_class.value} class."}
        seat.is_occupied = True
        assigned_seat = seat_number
        if booking.passengers:
            booking.passengers[0].seat_number = seat_number
    else:
        # Auto-assign: find first available seat in the booking's cabin class
        seat = db.query(Seat).filter(
            Seat.flight_id == booking.flight_id,
            Seat.cabin_class == booking.cabin_class,
            Seat.is_occupied == False,
        ).order_by(Seat.seat_number).first()
        if seat:
            seat.is_occupied = True
            assigned_seat = seat.seat_number
            if booking.passengers and not booking.passengers[0].seat_number:
                booking.passengers[0].seat_number = seat.seat_number
            elif booking.passengers:
                booking.passengers[0].seat_number = seat.seat_number
        elif booking.passengers and booking.passengers[0].seat_number:
            # Passenger already has a seat assigned from booking
            assigned_seat = booking.passengers[0].seat_number

    booking.check_in_status = CheckInStatus.CHECKED_IN
    db.commit()

    flight = booking.flight
    primary_pax = booking.passengers[0] if booking.passengers else None
    gate = f"{random.choice('ABCDEF')}{random.randint(1, 30)}"
    seat = assigned_seat or (primary_pax.seat_number if primary_pax and primary_pax.seat_number else "N/A")
    boarding_time = flight.departure_time - timedelta(minutes=30)

    boarding_pass = {
        "pnr": booking.pnr,
        "passenger_name": primary_pax.full_name if primary_pax else "Passenger",
        "flight_number": flight.flight_number,
        "airline_name": flight.airline_name,
        "departure_city": flight.departure_airport.city,
        "arrival_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
        "boarding_time": boarding_time.isoformat(),
        "gate": gate,
        "seat": seat,
        "boarding_pass_url": f"/api/bookings/boarding-pass/{booking.pnr}",
    }

    return {
        "success": True,
        "message": f"Check-in successful for PNR {booking.pnr}! Your boarding pass is ready.",
        "boarding_pass": boarding_pass,
    }


def get_boarding_pass(db: Session, pnr: str) -> dict:
    """Get boarding pass for a checked-in booking."""
    booking = db.query(Booking).filter(Booking.pnr.ilike(pnr.strip())).first()
    if not booking:
        return {"error": f"No booking found with PNR: {pnr}"}

    if booking.check_in_status != CheckInStatus.CHECKED_IN:
        return {"error": f"Please complete web check-in first for PNR {pnr}."}

    flight = booking.flight
    primary_pax = booking.passengers[0] if booking.passengers else None
    gate = f"{random.choice('ABCDEF')}{random.randint(1, 30)}"
    seat = primary_pax.seat_number if primary_pax and primary_pax.seat_number else "N/A"
    boarding_time = flight.departure_time - timedelta(minutes=30)

    return {
        "pnr": booking.pnr,
        "passenger_name": primary_pax.full_name if primary_pax else "Passenger",
        "flight_number": flight.flight_number,
        "airline_name": flight.airline_name,
        "departure_city": flight.departure_airport.city,
        "arrival_city": flight.arrival_airport.city,
        "departure_time": flight.departure_time.isoformat(),
        "boarding_time": boarding_time.isoformat(),
        "gate": gate,
        "seat": seat,
    }


# ── Baggage Info Tool ──────────────────────────────────────────────────────

def get_baggage_info(cabin_class: str = "economy") -> dict:
    """Get baggage allowance information."""
    baggage = {
        "economy": {"cabin_kg": 7, "checked_kg": 15, "extra_bag_fee": 500},
        "premium_economy": {"cabin_kg": 10, "checked_kg": 25, "extra_bag_fee": 400},
        "business": {"cabin_kg": 15, "checked_kg": 35, "extra_bag_fee": 300},
        "first": {"cabin_kg": 20, "checked_kg": 40, "extra_bag_fee": 250},
    }
    info = baggage.get(cabin_class, baggage["economy"])
    return {
        "cabin_class": cabin_class,
        "cabin_baggage_kg": info["cabin_kg"],
        "checked_baggage_kg": info["checked_kg"],
        "extra_bag_fee_per_kg": info["extra_bag_fee"],
        "note": "Excess baggage charges apply per kg above the free allowance.",
    }


# ── Weather Tool (Free API — Open-Meteo) ───────────────────────────────────

def get_weather(city: str) -> dict:
    """Get weather for a city using the free Open-Meteo API."""
    import httpx
    from config import settings

    # First geocode the city (free, no key needed)
    try:
        geo_resp = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "format": "json"},
            timeout=15,
        )
        geo_data = geo_resp.json()
        if not geo_data.get("results"):
            return {"error": f"Could not find weather data for {city}."}

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]

        weather_resp = httpx.get(
            settings.WEATHER_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
                "forecast_days": 1,
            },
            timeout=15,
        )
        w = weather_resp.json().get("current", {})
        code_map = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle",
            53: "Moderate drizzle", 55: "Dense drizzle", 56: "Light freezing drizzle",
            57: "Dense freezing drizzle", 61: "Slight rain", 63: "Moderate rain",
            65: "Heavy rain", 66: "Light freezing rain", 67: "Heavy freezing rain",
            71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
            77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
            82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
        }
        return {
            "city": city,
            "temperature": w.get("temperature_2m"),
            "condition": code_map.get(w.get("weather_code"), "Unknown"),
            "wind_speed": w.get("wind_speed_10m"),
        }
    except Exception as e:
        return {"error": f"Could not fetch weather: {str(e)}"}


# ── Currency Conversion Tool (Free API) ────────────────────────────────────

def convert_currency(amount: float, from_currency: str = "INR", to_currency: str = "USD") -> dict:
    """Convert currency using the free open.er-api.com API."""
    import httpx
    from config import settings

    try:
        resp = httpx.get(f"{settings.EXCHANGE_RATE_API_URL}/{from_currency}", timeout=10)
        data = resp.json()
        rate = data.get("rates", {}).get(to_currency)
        if rate:
            return {
                "original_amount": amount,
                "from_currency": from_currency,
                "to_currency": to_currency,
                "converted_amount": round(amount * rate, 2),
                "exchange_rate": rate,
            }
        return {"error": f"Could not convert {from_currency} to {to_currency}."}
    except Exception as e:
        return {"error": f"Currency conversion failed: {str(e)}"}


# ── Notification Tool ──────────────────────────────────────────────────────

def send_notification(
    db: Session,
    recipient: str,
    body: str,
    notification_type: str = "email",
    subject: Optional[str] = None,
    booking_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    """Send a notification — email via SMTP/Resend, SMS/WhatsApp via Twilio, logs to DB."""
    delivery_result = None

    # Email
    if notification_type == "email" and "@" in recipient:
        try:
            from services.email_service import send_email
            delivery_result = send_email(recipient, subject or "SkyBook AI Notification", body, notification_type)
        except Exception as e:
            print(f"⚠️  Email service error: {e}")
            delivery_result = {"success": False, "error": str(e)}

    # SMS
    elif notification_type == "sms":
        try:
            from services.sms_service import send_sms
            delivery_result = send_sms(recipient, body)
        except Exception as e:
            print(f"⚠️  SMS service error: {e}")
            delivery_result = {"success": False, "error": str(e)}

    # WhatsApp
    elif notification_type == "whatsapp":
        try:
            from services.sms_service import send_whatsapp
            delivery_result = send_whatsapp(recipient, body)
        except Exception as e:
            print(f"⚠️  WhatsApp service error: {e}")
            delivery_result = {"success": False, "error": str(e)}

    # Log to DB
    log = NotificationLog(
        booking_id=booking_id,
        user_id=user_id,
        notification_type=NotificationType(notification_type),
        recipient=recipient,
        subject=subject,
        body=body,
        status="sent" if (delivery_result and delivery_result.get("success")) else "logged",
    )
    db.add(log)
    db.commit()

    # Console logging
    method = delivery_result.get("method", "mock") if delivery_result else "mock"
    print(f"\n{'='*60}")
    print(f"📧 [{notification_type.upper()}] To: {recipient}")
    if subject:
        print(f"   Subject: {subject}")
    print(f"   Body: {body[:200]}")
    print(f"   Method: {method}")
    print(f"{'='*60}\n")

    return {
        "success": True,
        "message": f"{notification_type} sent to {recipient}",
        "delivery_method": method,
        "delivery_result": delivery_result,
    }
