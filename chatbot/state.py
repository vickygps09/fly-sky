"""LangGraph state definition for the airline chatbot."""

from typing import TypedDict, Optional, List, Any, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ChatState(TypedDict):
    """State that flows through the LangGraph workflow."""

    # Core conversation
    session_id: str
    user_id: Optional[str]
    messages: Annotated[List[BaseMessage], add_messages]

    # Intent & entities
    intent: Optional[str]  # greeting, book_flight, flight_status, cancel_booking, modify_booking, refund, check_in, help, human_agent
    entities: dict  # extracted entities (departure_city, arrival_city, date, etc.)

    # Conversation context
    conversation_history: List[dict]  # previous turns for context memory
    conversation_summary: Optional[str]  # running summary for long-term context

    # Booking flow state
    flow_step: Optional[str]  # current step in a multi-turn flow
    search_results: Optional[List[dict]]  # flight search results
    selected_flight: Optional[dict]
    selected_return_flight: Optional[dict]
    pending_booking: Optional[dict]
    booking_result: Optional[dict]
    chat_passengers: Optional[List[dict]]  # collected during chat-based booking
    chat_contact_email: Optional[str]
    chat_contact_phone: Optional[str]
    chat_extra_baggage: Optional[float]  # extra baggage kg during chat booking
    chat_insurance: Optional[bool]  # travel insurance during chat booking
    chat_coupon_code: Optional[str]  # coupon/promo code during chat booking
    chat_discount: Optional[float]  # discount amount from coupon
    check_in_pnr: Optional[str]  # PNR during check-in seat selection flow
    new_passenger_name: Optional[str]  # during add-passenger modify flow
    new_passenger_age: Optional[int]
    new_passenger_gender: Optional[str]

    # Response
    response: str
    response_metadata: Optional[dict]  # flight cards, quick replies, etc.
    escalated: bool  # human agent transfer

    # Database session reference (not serializable, but used in-process)
    db_session: Optional[Any]
