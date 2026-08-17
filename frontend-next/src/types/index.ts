// Types matching the FastAPI backend schemas

export interface User {
  user_id: string;
  name: string;
  email?: string;
  phone?: string;
  access_token: string;
  token_type?: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  intent: string;
  entities: Record<string, unknown>;
  metadata: ResponseMetadata | null;
  escalated: boolean;
}

export interface ResponseMetadata {
  quick_replies?: string[];
  flight_cards?: FlightInfo[];
  boarding_pass?: BoardingPass;
  show_booking_form?: boolean;
  flight_info?: FlightInfo;
  passenger_count?: number;
  conversation_summary?: string;
  booking_pnr?: string;
  booking_result?: BookingResult;
  intent?: string;
  show_date_picker?: boolean;
}

export interface FlightInfo {
  id: string;
  flight_number: string;
  airline_name: string;
  departure_airport_city: string;
  departure_airport_code: string;
  arrival_airport_city: string;
  arrival_airport_code: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  price: number;
  cabin_class: string;
  available_seats: number;
  cabin_baggage_kg: number;
  checked_baggage_kg: number;
  departure_lat?: number;
  departure_lon?: number;
  arrival_lat?: number;
  arrival_lon?: number;
}

export interface Seat {
  seat_number: string;
  is_occupied: boolean;
  is_window: boolean;
  price: number;
}

export interface BoardingPass {
  pnr: string;
  flight_number: string;
  airline_name: string;
  passenger_name: string;
  departure_city: string;
  arrival_city: string;
  departure_time: string;
  boarding_time: string;
  gate: string;
  seat: string;
  boarding_pass_url: string;
}

export interface PassengerDetail {
  full_name: string;
  age: number | null;
  gender: string | null;
  seat_number: string | null;
  meal_preference: string;
  is_primary: boolean;
}

export interface BookingResult {
  booking_id: string;
  pnr: string;
  total_amount: number;
  flight_number: string;
  departure_city: string;
  arrival_city: string;
  passenger_name: string;
  passengers: number;
  contact_email: string;
  contact_phone: string;
  travel_insurance: boolean;
  extra_baggage_kg: number;
  departure_time: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'bot';
  content: string;
  metadata?: ResponseMetadata | null;
  escalated?: boolean;
  intent?: string;
  streaming?: boolean;
}
