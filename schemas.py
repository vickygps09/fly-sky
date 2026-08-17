"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime, date


# ── Auth ───────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GuestLogin(BaseModel):
    name: str = Field(..., min_length=2)
    phone: Optional[str] = None


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str
    is_guest: bool = False


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    is_guest: bool
    is_verified: bool
    role: str
    model_config = {"from_attributes": True}


# ── Flights ────────────────────────────────────────────────────────────────

class AirportOut(BaseModel):
    id: str
    code: str
    name: str
    city: str
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    model_config = {"from_attributes": True}


class FlightSearch(BaseModel):
    departure_city: str
    arrival_city: str
    departure_date: date
    return_date: Optional[date] = None
    trip_type: str = "one_way"
    passengers: int = Field(1, ge=1, le=9)
    cabin_class: str = "economy"


class FlightOut(BaseModel):
    id: str
    flight_number: str
    airline_name: str
    departure_airport_code: str
    departure_airport_city: str
    arrival_airport_code: str
    arrival_airport_city: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    price: float
    cabin_class: str
    available_seats: int
    cabin_baggage_kg: float
    checked_baggage_kg: float
    status: str


class SeatOut(BaseModel):
    id: str
    seat_number: str
    cabin_class: str
    is_occupied: bool
    is_window: bool
    is_aisle: bool
    extra_legroom: bool
    price: float


# ── Bookings ───────────────────────────────────────────────────────────────

class PassengerInfo(BaseModel):
    full_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    seat_number: Optional[str] = None
    passport_number: Optional[str] = None
    is_primary: bool = False


class BookingCreate(BaseModel):
    flight_id: str
    return_flight_id: Optional[str] = None
    trip_type: str = "one_way"
    cabin_class: str = "economy"
    passengers: List[PassengerInfo]


class BookingOut(BaseModel):
    id: str
    pnr: str
    flight_number: str
    airline_name: str
    departure_city: str
    arrival_city: str
    departure_time: str
    arrival_time: str
    trip_type: str
    cabin_class: str
    passenger_count: int
    total_amount: float
    booking_status: str
    check_in_status: str
    passengers: List[PassengerInfo]
    created_at: str


class BookingModify(BaseModel):
    new_flight_id: Optional[str] = None
    new_seat_numbers: Optional[List[str]] = None


class BookingCancel(BaseModel):
    reason: Optional[str] = None


# ── Payments ───────────────────────────────────────────────────────────────

class PaymentInitiate(BaseModel):
    booking_id: str
    payment_method: str = "card"


class PaymentConfirm(BaseModel):
    booking_id: str
    transaction_id: str
    payment_method: str = "card"
    success: bool = True


class TransactionOut(BaseModel):
    id: str
    booking_id: str
    amount: float
    currency: str
    payment_method: str
    payment_status: str
    transaction_id: Optional[str]
    created_at: str


class RefundOut(BaseModel):
    id: str
    booking_id: str
    refund_amount: float
    refund_status: str
    reason: Optional[str]
    created_at: str


# ── Chat ───────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    session_id: str
    message: str
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None
    entities: Optional[dict] = None
    metadata: Optional[dict] = None
    escalated: bool = False


# ── Booking Details Form (ixigo-style) ─────────────────────────────────────

class PassengerDetail(BaseModel):
    full_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    seat_number: Optional[str] = None
    meal_preference: Optional[str] = None  # veg, non_veg, jain, none
    is_primary: bool = False


class BookingDetailsRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    flight_id: str
    cabin_class: str = "economy"
    passengers: List[PassengerDetail]
    contact_email: str
    contact_phone: str
    travel_insurance: bool = False
    extra_baggage_kg: float = 0.0


class BookingDetailsResponse(BaseModel):
    success: bool
    pnr: str
    booking_id: str
    total_amount: float
    flight_number: str
    departure_city: str
    arrival_city: str
    departure_time: str
    passenger_name: str
    contact_email: str
    contact_phone: str
    passengers: int
    travel_insurance: bool
    extra_baggage_kg: float


# ── Check-in ───────────────────────────────────────────────────────────────

class CheckInRequest(BaseModel):
    pnr: str
    seat_number: Optional[str] = None


class BoardingPass(BaseModel):
    pnr: str
    passenger_name: str
    flight_number: str
    departure_city: str
    arrival_city: str
    departure_time: str
    gate: str
    seat: str
    boarding_time: str


# ── Admin ──────────────────────────────────────────────────────────────────

class FlightCreate(BaseModel):
    flight_number: str
    airline_name: str = "SkyBook Airlines"
    airline_code: str = "SB"
    departure_airport_code: str
    arrival_airport_code: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    aircraft: str = "Boeing 737-800"
    total_seats: int = 180
    price_economy: float = 3000.0
    price_premium_economy: float = 6000.0
    price_business: float = 12000.0
    price_first: float = 20000.0
    cabin_baggage_kg: float = 7.0
    checked_baggage_kg: float = 15.0
    seat_rows: int = 30
    seat_cols: int = 6


class AnalyticsOut(BaseModel):
    total_bookings: int
    total_revenue: float
    total_cancellations: int
    total_refunds: float
    active_flights: int
    total_users: int
    popular_routes: List[dict]
    booking_trends: List[dict]


# ── Notifications ──────────────────────────────────────────────────────────

class NotificationSend(BaseModel):
    booking_id: Optional[str] = None
    notification_type: str = "email"
    recipient: str
    subject: Optional[str] = None
    body: str


# ── Flight Status ──────────────────────────────────────────────────────────

class FlightStatusOut(BaseModel):
    flight_number: str
    status: str
    departure_city: str
    arrival_city: str
    departure_time: str
    arrival_time: str
    delay_minutes: Optional[int] = None
    gate: Optional[str] = None


# ── Promotions ──────────────────────────────────────────────────────────────

class PromotionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: float = 0.0
    promo_code: str
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    max_uses: int = 100


class PromotionOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    discount_type: str
    discount_value: float
    promo_code: str
    valid_from: date
    valid_until: Optional[date] = None
    is_active: bool
    max_uses: int
    used_count: int
    created_at: datetime


# ── Coupons ─────────────────────────────────────────────────────────────────

class CouponCreate(BaseModel):
    code: str
    discount_type: str = "percentage"
    discount_value: float = 0.0
    min_booking_amount: float = 0.0
    max_discount_amount: Optional[float] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    max_uses: int = 100


class CouponOut(BaseModel):
    id: str
    code: str
    discount_type: str
    discount_value: float
    min_booking_amount: float
    max_discount_amount: Optional[float] = None
    valid_from: date
    valid_until: Optional[date] = None
    is_active: bool
    max_uses: int
    used_count: int
    created_at: datetime


# ── CSAT ────────────────────────────────────────────────────────────────────

class CSATCreate(BaseModel):
    session_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = None
    intent: Optional[str] = None


class CSATOut(BaseModel):
    id: str
    session_id: str
    rating: int
    feedback: Optional[str] = None
    intent: Optional[str] = None
    created_at: datetime


# ── Airport CRUD ────────────────────────────────────────────────────────────

class AirportCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=3)
    name: str
    city: str
    country: str
    timezone: str = "UTC"
    terminals: int = 1
