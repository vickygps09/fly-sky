"""Seed data — populates the database with sample airports, flights, users, and AI prompts.

Run automatically on first startup, or manually: python seed_data.py
"""

from datetime import datetime, timedelta, date
from database import SessionLocal, init_db
import models
from auth import hash_password
from routers.admin import _generate_seats


def seed_database(db=None):
    """Seed the database with sample data."""
    if db is None:
        db = SessionLocal()

    try:
        # ── Airports ────────────────────────────────────────────────────────
        airports_data = [
            ("BLR", "Kempegowda International Airport", "Bangalore", "India", "Asia/Kolkata", 13.1986, 77.7066),
            ("DEL", "Indira Gandhi International Airport", "Delhi", "India", "Asia/Kolkata", 28.5562, 77.1000),
            ("BOM", "Chhatrapati Shivaji International Airport", "Mumbai", "India", "Asia/Kolkata", 19.0896, 72.8656),
            ("MAA", "Chennai International Airport", "Chennai", "India", "Asia/Kolkata", 12.9941, 80.1709),
            ("HYD", "Rajiv Gandhi International Airport", "Hyderabad", "India", "Asia/Kolkata", 17.2403, 78.4294),
            ("CCU", "Netaji Subhas Chandra Bose Airport", "Kolkata", "India", "Asia/Kolkata", 22.6547, 88.4467),
            ("GOI", "Goa International Airport", "Goa", "India", "Asia/Kolkata", 15.3808, 73.8314),
            ("COK", "Cochin International Airport", "Kochi", "India", "Asia/Kolkata", 10.1520, 76.4019),
            ("JAI", "Jaipur International Airport", "Jaipur", "India", "Asia/Kolkata", 26.8242, 75.8122),
            ("AMD", "Sardar Vallabhbhai Patel Airport", "Ahmedabad", "India", "Asia/Kolkata", 23.0772, 72.6347),
            ("CJB", "Coimbatore International Airport", "Coimbatore", "India", "Asia/Kolkata", 11.0311, 77.0435),
            ("TRV", "Trivandrum International Airport", "Thiruvananthapuram", "India", "Asia/Kolkata", 8.4821, 76.9200),
            ("PNQ", "Pune International Airport", "Pune", "India", "Asia/Kolkata", 18.5793, 73.9089),
        ]

        airports = {}
        for code, name, city, country, tz, lat, lon in airports_data:
            airport = models.Airport(code=code, name=name, city=city, country=country, timezone=tz, latitude=lat, longitude=lon)
            db.add(airport)
            db.flush()
            airports[code] = airport

        # ── Users ───────────────────────────────────────────────────────────
        # Admin user
        admin = models.User(
            name="Admin User",
            email="admin@skybook.ai",
            phone="9999999999",
            password_hash=hash_password("admin123"),
            is_guest=False,
            is_verified=True,
            role=models.UserRole.ADMIN,
        )
        db.add(admin)

        # Demo user
        demo_user = models.User(
            name="John Doe",
            email="john@example.com",
            phone="8888888888",
            password_hash=hash_password("user123"),
            is_guest=False,
            is_verified=True,
            role=models.UserRole.USER,
        )
        db.add(demo_user)
        db.flush()

        # ── Flights ────────────────────────────────────────────────────────
        # Generate flights for the next 7 days across multiple routes
        routes = [
            ("BLR", "DEL", 175, 3500),  # Bangalore → Delhi, 175min, ₹3500
            ("DEL", "BLR", 175, 3200),
            ("BLR", "BOM", 90, 2800),   # Bangalore → Mumbai
            ("BOM", "BLR", 90, 2600),
            ("BLR", "MAA", 60, 2200),   # Bangalore → Chennai
            ("MAA", "BLR", 60, 2000),
            ("DEL", "BOM", 130, 3000),  # Delhi → Mumbai
            ("BOM", "DEL", 130, 3100),
            ("BLR", "HYD", 70, 2400),   # Bangalore → Hyderabad
            ("HYD", "BLR", 70, 2300),
            ("BLR", "GOI", 75, 2600),   # Bangalore → Goa
            ("GOI", "BLR", 75, 2700),
            ("DEL", "CCU", 150, 3800),  # Delhi → Kolkata
            ("CCU", "DEL", 150, 3600),
            ("BOM", "MAA", 110, 2900),  # Mumbai → Chennai
            ("MAA", "BOM", 110, 2800),
            ("BLR", "COK", 65, 2300),   # Bangalore → Kochi
            ("COK", "BLR", 65, 2200),
            ("DEL", "JAI", 75, 2500),   # Delhi → Jaipur
            ("JAI", "DEL", 75, 2400),
            ("BOM", "AMD", 80, 2500),   # Mumbai → Ahmedabad
            ("AMD", "BOM", 80, 2400),
            ("MAA", "CJB", 60, 1800),   # Chennai → Coimbatore
            ("CJB", "MAA", 60, 1800),
            ("BLR", "CJB", 70, 2200),   # Bangalore → Coimbatore
            ("CJB", "BLR", 70, 2100),
            ("COK", "CJB", 45, 1500),   # Kochi → Coimbatore
            ("CJB", "COK", 45, 1500),
            ("MAA", "TRV", 90, 2500),   # Chennai → Thiruvananthapuram
            ("TRV", "MAA", 90, 2400),
            ("BLR", "PNQ", 80, 2400),   # Bangalore → Pune
            ("PNQ", "BLR", 80, 2300),
            ("BOM", "PNQ", 45, 1200),   # Mumbai → Pune
            ("PNQ", "BOM", 45, 1200),
            ("DEL", "PNQ", 120, 3200),  # Delhi → Pune
            ("PNQ", "DEL", 120, 3100),
        ]

        flight_counter = 101
        today = date.today()

        for day_offset in range(7):
            flight_date = today + timedelta(days=day_offset)

            for dep_code, arr_code, duration, base_price in routes:
                # Morning flight (6:00 AM)
                dep_time_1 = datetime.combine(flight_date, datetime.min.time()).replace(hour=6, minute=0)
                arr_time_1 = dep_time_1 + timedelta(minutes=duration)

                flight_1 = models.Flight(
                    flight_number=f"SB{flight_counter}",
                    airline_name="SkyBook Airlines",
                    airline_code="SB",
                    departure_airport_id=airports[dep_code].id,
                    arrival_airport_id=airports[arr_code].id,
                    departure_time=dep_time_1,
                    arrival_time=arr_time_1,
                    duration_minutes=duration,
                    aircraft="Boeing 737-800",
                    total_seats=180,
                    price_economy=base_price,
                    price_premium_economy=base_price * 2,
                    price_business=base_price * 4,
                    price_first=base_price * 6.5,
                    cabin_baggage_kg=7,
                    checked_baggage_kg=15,
                    seat_rows=30,
                    seat_cols=6,
                    status=models.FlightStatus.SCHEDULED,
                )
                db.add(flight_1)
                db.flush()
                _generate_seats(db, flight_1)
                flight_counter += 1

                # Afternoon flight (2:00 PM)
                dep_time_2 = datetime.combine(flight_date, datetime.min.time()).replace(hour=14, minute=0)
                arr_time_2 = dep_time_2 + timedelta(minutes=duration)

                flight_2 = models.Flight(
                    flight_number=f"SB{flight_counter}",
                    airline_name="SkyBook Airlines",
                    airline_code="SB",
                    departure_airport_id=airports[dep_code].id,
                    arrival_airport_id=airports[arr_code].id,
                    departure_time=dep_time_2,
                    arrival_time=arr_time_2,
                    duration_minutes=duration,
                    aircraft="Airbus A320",
                    total_seats=180,
                    price_economy=int(base_price * 1.1),
                    price_premium_economy=int(base_price * 2.2),
                    price_business=int(base_price * 4.4),
                    price_first=int(base_price * 7),
                    cabin_baggage_kg=7,
                    checked_baggage_kg=15,
                    seat_rows=30,
                    seat_cols=6,
                    status=models.FlightStatus.SCHEDULED,
                )
                db.add(flight_2)
                db.flush()
                _generate_seats(db, flight_2)
                flight_counter += 1

                # Evening flight (7:00 PM)
                dep_time_3 = datetime.combine(flight_date, datetime.min.time()).replace(hour=19, minute=0)
                arr_time_3 = dep_time_3 + timedelta(minutes=duration)

                flight_3 = models.Flight(
                    flight_number=f"SB{flight_counter}",
                    airline_name="SkyBook Airlines",
                    airline_code="SB",
                    departure_airport_id=airports[dep_code].id,
                    arrival_airport_id=airports[arr_code].id,
                    departure_time=dep_time_3,
                    arrival_time=arr_time_3,
                    duration_minutes=duration,
                    aircraft="Boeing 737-900",
                    total_seats=180,
                    price_economy=int(base_price * 1.2),
                    price_premium_economy=int(base_price * 2.4),
                    price_business=int(base_price * 4.8),
                    price_first=int(base_price * 7.5),
                    cabin_baggage_kg=7,
                    checked_baggage_kg=15,
                    seat_rows=30,
                    seat_cols=6,
                    status=models.FlightStatus.SCHEDULED,
                )
                db.add(flight_3)
                db.flush()
                _generate_seats(db, flight_3)
                flight_counter += 1

        # ── Sample Booking (for demo) ───────────────────────────────────────
        first_flight = db.query(models.Flight).filter(models.Flight.flight_number == "SB101").first()
        if first_flight:
            booking = models.Booking(
                pnr="DEMO01",
                user_id=demo_user.id,
                flight_id=first_flight.id,
                trip_type=models.TripType.ONE_WAY,
                cabin_class=models.CabinClass.ECONOMY,
                passenger_count=1,
                total_amount=first_flight.price_economy,
                booking_status=models.BookingStatus.CONFIRMED,
                departure_date=first_flight.departure_time.date(),
            )
            db.add(booking)
            db.flush()

            passenger = models.Passenger(
                booking_id=booking.id,
                full_name="John Doe",
                age=30,
                gender="Male",
                seat_number="15A",
                is_primary=True,
            )
            db.add(passenger)

            # Mark seat as occupied
            seat = db.query(models.Seat).filter(
                models.Seat.flight_id == first_flight.id,
                models.Seat.seat_number == "15A",
            ).first()
            if seat:
                seat.is_occupied = True

            # Add transaction
            txn = models.Transaction(
                booking_id=booking.id,
                amount=first_flight.price_economy,
                payment_method="card",
                payment_status=models.PaymentStatus.SUCCESS,
                transaction_id="TXN123456789012",
            )
            db.add(txn)

        # ── AI Prompts ──────────────────────────────────────────────────────
        prompts_data = [
            ("flight_search", "Flight Search", "Help user search for flights between cities on a given date."),
            ("fare_recommendation", "Fare Recommendation", "Compare fares and recommend best value options."),
            ("travel_policy", "Travel Policy", "Answer questions about cancellation, refund, and baggage policies."),
            ("faq", "FAQ", "Answer frequently asked questions about air travel."),
            ("booking_assistance", "Booking Assistance", "Guide user through the booking process step by step."),
        ]

        for name, category, template in prompts_data:
            prompt = models.Prompt(name=name, category=category, template=template, is_active=True)
            db.add(prompt)

        # ── Intents ─────────────────────────────────────────────────────────
        intents_data = [
            ("greeting", "User greeting", ["Hi", "Hello", "Hey", "Good morning"]),
            ("book_flight", "Book a flight", ["I need a flight", "Book a ticket", "Search flights"]),
            ("flight_status", "Check flight status", ["Check flight status", "Where is my flight", "Flight AI234 status"]),
            ("cancel_booking", "Cancel booking", ["Cancel my booking", "Cancel ticket", "Refund my ticket"]),
            ("modify_booking", "Modify booking", ["Change my flight", "Modify booking", "Reschedule"]),
            ("refund", "Refund status", ["Where is my refund", "Refund status", "When will I get my refund"]),
            ("check_in", "Web check-in", ["Web check-in", "Check in", "Boarding pass"]),
            ("help", "Help", ["Help", "What can you do", "How do I"]),
        ]

        for name, desc, examples in intents_data:
            intent = models.Intent(name=name, description=desc, example_phrases=examples)
            db.add(intent)

        # ── Entities ────────────────────────────────────────────────────────
        entities_data = [
            ("departure_city", "city"), ("arrival_city", "city"), ("date", "date"),
            ("return_date", "date"), ("passengers", "number"), ("cabin_class", "enum"),
            ("airline", "string"), ("booking_id", "string"), ("seat_number", "string"),
            ("flight_number", "string"), ("trip_type", "enum"),
        ]

        for name, etype in entities_data:
            entity = models.Entity(name=name, entity_type=etype)
            db.add(entity)

        db.commit()
        print(f"✅ Seeded: {len(airports)} airports, {flight_counter - 101} flights, 2 users, 1 demo booking")
        print(f"   Admin login: admin@skybook.ai / admin123")
        print(f"   User login:  john@example.com / user123")
        print(f"   Demo PNR:    DEMO01")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed error: {e}")
        raise
    finally:
        if db is None:
            db.close()


if __name__ == "__main__":
    init_db()
    seed_database()
