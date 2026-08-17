"""SQLAlchemy ORM models — covers all database modules from the task spec.

Modules: User, Flights, Booking, Payment, Chat, AI, Notifications, Reports
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Boolean, Text,
    ForeignKey, Enum, JSON, func,
)
from sqlalchemy.orm import relationship
from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ──────────────────────────────────────────────────────────────────

class TripType(str, enum.Enum):
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class CabinClass(str, enum.Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    MODIFIED = "modified"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    INITIATED = "initiated"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class RefundStatus(str, enum.Enum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class CheckInStatus(str, enum.Enum):
    NOT_CHECKED_IN = "not_checked_in"
    CHECKED_IN = "checked_in"
    BOARDED = "boarded"


class FlightStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    ARRIVED = "arrived"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class NotificationType(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


# ── User Module ────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=True)  # nullable for guest users
    is_guest = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    otp_code = Column(String(6), nullable=True)
    otp_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    bookings = relationship("Booking", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")


# ── Flights Module ─────────────────────────────────────────────────────────

class Airport(Base):
    __tablename__ = "airports"

    id = Column(String, primary_key=True, default=_uuid)
    code = Column(String(3), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    timezone = Column(String(50), default="UTC")
    terminals = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    departures = relationship("Flight", back_populates="departure_airport", foreign_keys="Flight.departure_airport_id")
    arrivals = relationship("Flight", back_populates="arrival_airport", foreign_keys="Flight.arrival_airport_id")


class Route(Base):
    __tablename__ = "routes"

    id = Column(String, primary_key=True, default=_uuid)
    departure_airport_id = Column(String, ForeignKey("airports.id"), nullable=False)
    arrival_airport_id = Column(String, ForeignKey("airports.id"), nullable=False)
    distance_km = Column(Float, nullable=True)
    base_price = Column(Float, default=3000.0)
    created_at = Column(DateTime, server_default=func.now())

    departure_airport = relationship("Airport", foreign_keys=[departure_airport_id])
    arrival_airport = relationship("Airport", foreign_keys=[arrival_airport_id])


class Flight(Base):
    __tablename__ = "flights"

    id = Column(String, primary_key=True, default=_uuid)
    flight_number = Column(String(10), unique=True, nullable=False, index=True)
    airline_name = Column(String(100), default="SkyBook Airlines")
    airline_code = Column(String(3), default="SB")

    departure_airport_id = Column(String, ForeignKey("airports.id"), nullable=False)
    arrival_airport_id = Column(String, ForeignKey("airports.id"), nullable=False)

    departure_time = Column(DateTime, nullable=False)
    arrival_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)

    aircraft = Column(String(50), default="Boeing 737-800")
    total_seats = Column(Integer, default=180)

    # Pricing per cabin class
    price_economy = Column(Float, default=3000.0)
    price_premium_economy = Column(Float, default=6000.0)
    price_business = Column(Float, default=12000.0)
    price_first = Column(Float, default=20000.0)

    # Baggage allowance
    cabin_baggage_kg = Column(Float, default=7.0)
    checked_baggage_kg = Column(Float, default=15.0)

    # Seat layout (rows x cols, e.g. "6x2" means 6 rows, 2 seats per row per side)
    seat_rows = Column(Integer, default=30)
    seat_cols = Column(Integer, default=6)

    status = Column(Enum(FlightStatus), default=FlightStatus.SCHEDULED)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    departure_airport = relationship("Airport", back_populates="departures", foreign_keys=[departure_airport_id])
    arrival_airport = relationship("Airport", back_populates="arrivals", foreign_keys=[arrival_airport_id])
    seats = relationship("Seat", back_populates="flight", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="flight", foreign_keys="Booking.flight_id")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(String, primary_key=True, default=_uuid)
    flight_id = Column(String, ForeignKey("flights.id"), nullable=False)
    seat_number = Column(String(5), nullable=False)  # e.g. "12A"
    cabin_class = Column(Enum(CabinClass), default=CabinClass.ECONOMY)
    is_occupied = Column(Boolean, default=False)
    is_window = Column(Boolean, default=False)
    is_aisle = Column(Boolean, default=False)
    extra_legroom = Column(Boolean, default=False)
    price = Column(Float, default=0.0)  # seat selection fee

    flight = relationship("Flight", back_populates="seats")


# ── Booking Module ─────────────────────────────────────────────────────────

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(String, primary_key=True, default=_uuid)
    pnr = Column(String(6), unique=True, nullable=False, index=True)  # 6-char booking ref
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # nullable for guest
    flight_id = Column(String, ForeignKey("flights.id"), nullable=False)
    return_flight_id = Column(String, ForeignKey("flights.id"), nullable=True)

    trip_type = Column(Enum(TripType), default=TripType.ONE_WAY)
    cabin_class = Column(Enum(CabinClass), default=CabinClass.ECONOMY)
    passenger_count = Column(Integer, default=1)

    total_amount = Column(Float, default=0.0)
    booking_status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    check_in_status = Column(Enum(CheckInStatus), default=CheckInStatus.NOT_CHECKED_IN)
    boarding_pass_url = Column(String(500), nullable=True)

    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    travel_insurance = Column(Boolean, default=False)
    extra_baggage_kg = Column(Float, default=0.0)

    departure_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="bookings")
    flight = relationship("Flight", back_populates="bookings", foreign_keys=[flight_id])
    return_flight = relationship("Flight", foreign_keys=[return_flight_id])
    passengers = relationship("Passenger", back_populates="booking", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="booking", cascade="all, delete-orphan")
    refunds = relationship("Refund", back_populates="booking", cascade="all, delete-orphan")


class Passenger(Base):
    __tablename__ = "passengers"

    id = Column(String, primary_key=True, default=_uuid)
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    full_name = Column(String(200), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    seat_number = Column(String(5), nullable=True)
    passport_number = Column(String(50), nullable=True)
    meal_preference = Column(String(20), nullable=True)  # veg, non_veg, jain, none
    is_primary = Column(Boolean, default=False)

    booking = relationship("Booking", back_populates="passengers")


# ── Payment Module ─────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=_uuid)
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="INR")
    payment_method = Column(String(50), default="card")
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.INITIATED)
    transaction_id = Column(String(100), nullable=True)  # gateway transaction ID
    gateway_response = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    booking = relationship("Booking", back_populates="transactions")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String, primary_key=True, default=_uuid)
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=False)
    transaction_id = Column(String, ForeignKey("transactions.id"), nullable=True)
    refund_amount = Column(Float, nullable=False)
    refund_status = Column(Enum(RefundStatus), default=RefundStatus.REQUESTED)
    reason = Column(Text, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    booking = relationship("Booking", back_populates="refunds")
    transaction = relationship("Transaction", foreign_keys=[transaction_id])


# ── Chat Module ────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, nullable=False, index=True)
    is_escalated = Column(Boolean, default=False)  # human agent transfer
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    entities = Column(JSON, nullable=True)  # extracted entities
    extra_metadata = Column("metadata", JSON, nullable=True)  # extra data (flight cards, etc.)
    created_at = Column(DateTime, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


# ── AI Module ──────────────────────────────────────────────────────────────

class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), nullable=False)  # flight_search, fare_recommendation, etc.
    template = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class Intent(Base):
    __tablename__ = "intents"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    example_phrases = Column(JSON, nullable=True)  # list of example utterances
    created_at = Column(DateTime, server_default=func.now())


class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(50), nullable=False)
    entity_type = Column(String(50), nullable=False)  # city, date, number, etc.
    created_at = Column(DateTime, server_default=func.now())


# ── Notifications Module ───────────────────────────────────────────────────

class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(String, primary_key=True, default=_uuid)
    booking_id = Column(String, ForeignKey("bookings.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    recipient = Column(String(255), nullable=False)  # phone or email
    subject = Column(String(200), nullable=True)
    body = Column(Text, nullable=False)
    status = Column(String(20), default="sent")  # sent, failed
    created_at = Column(DateTime, server_default=func.now())


# ── Reports / Analytics Module ─────────────────────────────────────────────

class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(String, primary_key=True, default=_uuid)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_date = Column(Date, nullable=False, default=date.today)
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ── Promotions & Coupons Module ─────────────────────────────────────────────

class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    discount_type = Column(String(20), default="percentage")  # percentage, fixed
    discount_value = Column(Float, default=0.0)
    promo_code = Column(String(50), unique=True, nullable=False, index=True)
    valid_from = Column(Date, nullable=False, default=date.today)
    valid_until = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    max_uses = Column(Integer, default=100)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(String, primary_key=True, default=_uuid)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_type = Column(String(20), default="percentage")  # percentage, fixed
    discount_value = Column(Float, default=0.0)
    min_booking_amount = Column(Float, default=0.0)
    max_discount_amount = Column(Float, nullable=True)
    valid_from = Column(Date, nullable=False, default=date.today)
    valid_until = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    max_uses = Column(Integer, default=100)
    used_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


# ── CSAT (Customer Satisfaction) Module ─────────────────────────────────────

class CSAT(Base):
    __tablename__ = "csat_ratings"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    feedback = Column(Text, nullable=True)
    intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
