import type {
  ChatResponse,
  User,
  BookingResult,
  Seat,
} from '@/types';

const API_BASE = '/api';

export async function newSession(): Promise<string> {
  try {
    const resp = await fetch(`${API_BASE}/chat/new-session`, { method: 'POST' });
    const data = await resp.json();
    return data.session_id;
  } catch {
    return 'session_' + Date.now();
  }
}

export async function sendMessage(
  sessionId: string,
  message: string,
  userId: string | null
): Promise<ChatResponse> {
  const resp = await fetch(`${API_BASE}/chat/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message, user_id: userId }),
  });
  return resp.json();
}

export async function login(email: string, password: string): Promise<User> {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Login failed');
  return data;
}

export async function register(
  name: string,
  email: string,
  phone: string,
  password: string
): Promise<User> {
  const resp = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email, phone, password }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Registration failed');
  return data;
}

export async function guestLogin(name: string, phone: string): Promise<User> {
  const resp = await fetch(`${API_BASE}/auth/guest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, phone }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Guest login failed');
  return data;
}

export async function getSeats(flightId: string): Promise<Seat[]> {
  const resp = await fetch(`${API_BASE}/chat/seats/${flightId}`);
  const data = await resp.json();
  return data.seats || [];
}

export async function submitBooking(
  sessionId: string,
  userId: string | null,
  flightId: string,
  passengers: Array<{
    full_name: string;
    age: number | null;
    gender: string | null;
    seat_number: string | null;
    meal_preference: string;
    is_primary: boolean;
  }>,
  contactEmail: string,
  contactPhone: string,
  travelInsurance: boolean,
  extraBaggageKg: number
): Promise<BookingResult> {
  const resp = await fetch(`${API_BASE}/chat/booking-details`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      user_id: userId,
      flight_id: flightId,
      cabin_class: 'economy',
      passengers,
      contact_email: contactEmail,
      contact_phone: contactPhone,
      travel_insurance: travelInsurance,
      extra_baggage_kg: extraBaggageKg,
    }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Booking failed');
  return data;
}

export async function initiatePayment(
  bookingId: string,
  paymentMethod: string
): Promise<{ transaction_id: string }> {
  const resp = await fetch(`${API_BASE}/payments/initiate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ booking_id: bookingId, payment_method: paymentMethod }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Payment initiation failed');
  return data;
}

export async function validateCoupon(
  code: string,
  bookingAmount: number
): Promise<{ valid: boolean; code: string; discount_type: string; discount_value: number; discount_amount: number; final_amount: number }> {
  const resp = await fetch(`${API_BASE}/payments/validate-coupon`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, booking_amount: bookingAmount }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Invalid coupon code');
  return data;
}

export async function confirmPayment(
  bookingId: string,
  transactionId: string,
  paymentMethod: string
): Promise<Record<string, unknown>> {
  const resp = await fetch(`${API_BASE}/payments/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      booking_id: bookingId,
      transaction_id: transactionId,
      payment_method: paymentMethod,
      success: true,
    }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || 'Payment confirmation failed');
  return data;
}

export function formatMessage(text: string): string {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" style="color:var(--primary);font-weight:600;">$1</a>'
    )
    .replace(/\n/g, '<br>');
}

export const INTENT_LABELS: Record<string, { icon: string; label: string }> = {
  greeting: { icon: '👋', label: 'Greeting' },
  book_flight: { icon: '✈️', label: 'Book Flight' },
  flight_status: { icon: '📊', label: 'Flight Status' },
  cancel_booking: { icon: '❌', label: 'Cancel Booking' },
  modify_booking: { icon: '🔄', label: 'Modify Booking' },
  refund: { icon: '💰', label: 'Refund' },
  check_in: { icon: '✅', label: 'Check-in' },
  baggage_info: { icon: '🧳', label: 'Baggage Info' },
  fare_comparison: { icon: '🏷️', label: 'Fare Comparison' },
  help: { icon: '💡', label: 'Help' },
  human_agent: { icon: '🤝', label: 'Human Agent' },
  general_query: { icon: '💬', label: 'General Query' },
};

export function formatIntentLabel(intent: string): string {
  const info = INTENT_LABELS[intent] || INTENT_LABELS.general_query;
  return `${info.icon} ${info.label}`;
}

export async function submitCSAT(sessionId: string, rating: number, feedback?: string, intent?: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/chat/csat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, rating, feedback, intent }),
    });
  } catch {
    // non-blocking
  }
}
