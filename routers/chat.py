"""Chat router — REST and WebSocket endpoints for the AI chatbot.

Integrates with LangGraph workflow for intent recognition, entity extraction,
multi-turn conversations, and all airline operations.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from database import get_db
import models
from auth import get_current_user
from schemas import ChatMessage, ChatResponse, BookingDetailsRequest, BookingDetailsResponse, CSATCreate
from chatbot.graph import get_graph
from chatbot import tools

router = APIRouter(prefix="/api/chat", tags=["Chatbot"])


def _process_message(message: str, session_id: str, user_id: str | None, db: Session) -> ChatResponse:
    """Process a chat message through the LangGraph workflow."""
    graph = get_graph()

    # Load conversation history from DB
    conversation = db.query(models.Conversation).filter(
        models.Conversation.session_id == session_id
    ).first()

    conversation_history = []
    prev_flow_step = None
    prev_entities = {}
    prev_intent = None
    prev_search_results = None
    prev_selected_flight = None
    prev_selected_return_flight = None
    prev_booking_result = None
    prev_conversation_summary = None
    prev_chat_passengers = None
    prev_chat_email = None
    prev_chat_phone = None
    prev_chat_baggage = None
    prev_chat_insurance = None
    prev_chat_coupon = None
    prev_chat_discount = None
    prev_check_in_pnr = None
    prev_new_pax_name = None
    prev_new_pax_age = None
    prev_new_pax_gender = None
    if conversation:
        sorted_msgs = sorted(conversation.messages, key=lambda m: m.created_at or "")
        for msg in sorted_msgs[-10:]:  # last 10 messages for context
            conversation_history.append({"role": msg.role, "content": msg.content})
        # Restore state from last assistant message
        last_assistant = None
        for msg in reversed(sorted_msgs):
            if msg.role == "assistant":
                last_assistant = msg
                break
        if last_assistant:
            prev_intent = last_assistant.intent
            prev_entities = last_assistant.entities or {}
            # flow state is stored in metadata
            if last_assistant.extra_metadata and isinstance(last_assistant.extra_metadata, dict):
                prev_flow_step = last_assistant.extra_metadata.get("flow_step")
                prev_search_results = last_assistant.extra_metadata.get("search_results")
                prev_selected_flight = last_assistant.extra_metadata.get("selected_flight")
                prev_selected_return_flight = last_assistant.extra_metadata.get("selected_return_flight")
                prev_booking_result = last_assistant.extra_metadata.get("booking_result")
                prev_chat_passengers = last_assistant.extra_metadata.get("chat_passengers")
                prev_chat_email = last_assistant.extra_metadata.get("chat_contact_email")
                prev_chat_phone = last_assistant.extra_metadata.get("chat_contact_phone")
                prev_chat_baggage = last_assistant.extra_metadata.get("chat_extra_baggage")
                prev_chat_insurance = last_assistant.extra_metadata.get("chat_insurance")
                prev_chat_coupon = last_assistant.extra_metadata.get("chat_coupon_code")
                prev_chat_discount = last_assistant.extra_metadata.get("chat_discount")
                prev_check_in_pnr = last_assistant.extra_metadata.get("check_in_pnr")
                prev_new_pax_name = last_assistant.extra_metadata.get("new_passenger_name")
                prev_new_pax_age = last_assistant.extra_metadata.get("new_passenger_age")
                prev_new_pax_gender = last_assistant.extra_metadata.get("new_passenger_gender")
        # Load conversation summary
        prev_conversation_summary = conversation.summary if conversation.summary else None

    # Build initial state — restore previous context for multi-turn flows
    initial_state = {
        "session_id": session_id,
        "user_id": user_id,
        "messages": [HumanMessage(content=message)],
        "intent": prev_intent,
        "entities": prev_entities.copy(),
        "conversation_history": conversation_history,
        "conversation_summary": prev_conversation_summary,
        "flow_step": prev_flow_step,
        "search_results": prev_search_results,
        "selected_flight": prev_selected_flight,
        "selected_return_flight": prev_selected_return_flight,
        "pending_booking": None,
        "booking_result": prev_booking_result,
        "chat_passengers": prev_chat_passengers if prev_chat_passengers is not None else [],
        "chat_contact_email": prev_chat_email,
        "chat_contact_phone": prev_chat_phone,
        "chat_extra_baggage": prev_chat_baggage,
        "chat_insurance": prev_chat_insurance,
        "chat_coupon_code": prev_chat_coupon,
        "chat_discount": prev_chat_discount,
        "check_in_pnr": prev_check_in_pnr,
        "new_passenger_name": prev_new_pax_name,
        "new_passenger_age": prev_new_pax_age,
        "new_passenger_gender": prev_new_pax_gender,
        "response": "",
        "response_metadata": None,
        "escalated": False,
        "db_session": db,
    }

    # Invoke the graph
    result = graph.invoke(initial_state)

    # Save conversation and messages to DB
    if not conversation:
        # Verify user_id exists in DB — it may be stale from a previous DB
        valid_user_id = user_id
        if user_id:
            if not db.query(models.User).filter(models.User.id == user_id).first():
                valid_user_id = None
        conversation = models.Conversation(
            session_id=session_id,
            user_id=valid_user_id,
            is_escalated=result.get("escalated", False),
        )
        db.add(conversation)
        db.flush()

    # Save user message
    user_msg = models.Message(
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(user_msg)

    # Save assistant response — include flow state in metadata for multi-turn state
    response_metadata = result.get("response_metadata") or {}
    if result.get("flow_step"):
        response_metadata["flow_step"] = result["flow_step"]
    if result.get("search_results"):
        response_metadata["search_results"] = result["search_results"]
    if result.get("selected_flight"):
        response_metadata["selected_flight"] = result["selected_flight"]
    if result.get("selected_return_flight"):
        response_metadata["selected_return_flight"] = result["selected_return_flight"]
    if result.get("booking_result"):
        response_metadata["booking_result"] = result["booking_result"]
    if result.get("chat_passengers"):
        response_metadata["chat_passengers"] = result["chat_passengers"]
    if result.get("chat_contact_email"):
        response_metadata["chat_contact_email"] = result["chat_contact_email"]
    if result.get("chat_contact_phone"):
        response_metadata["chat_contact_phone"] = result["chat_contact_phone"]
    if result.get("chat_extra_baggage") is not None:
        response_metadata["chat_extra_baggage"] = result["chat_extra_baggage"]
    if result.get("chat_insurance") is not None:
        response_metadata["chat_insurance"] = result["chat_insurance"]
    if result.get("chat_coupon_code"):
        response_metadata["chat_coupon_code"] = result["chat_coupon_code"]
    if result.get("chat_discount") is not None:
        response_metadata["chat_discount"] = result["chat_discount"]
    if result.get("check_in_pnr"):
        response_metadata["check_in_pnr"] = result["check_in_pnr"]
    if result.get("new_passenger_name"):
        response_metadata["new_passenger_name"] = result["new_passenger_name"]
    if result.get("new_passenger_age") is not None:
        response_metadata["new_passenger_age"] = result["new_passenger_age"]
    if result.get("new_passenger_gender"):
        response_metadata["new_passenger_gender"] = result["new_passenger_gender"]

    assistant_msg = models.Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("response", ""),
        intent=result.get("intent"),
        entities=result.get("entities"),
        extra_metadata=response_metadata,
    )
    db.add(assistant_msg)

    # Update conversation
    conversation.is_escalated = result.get("escalated", False)
    result_summary = result.get("conversation_summary")
    if not result_summary and result.get("response_metadata"):
        result_summary = result["response_metadata"].get("conversation_summary")
    if result_summary:
        conversation.summary = result_summary

    db.commit()

    return ChatResponse(
        session_id=session_id,
        reply=result.get("response", "I'm sorry, I couldn't process that. Please try again."),
        intent=result.get("intent"),
        entities=result.get("entities"),
        metadata=result.get("response_metadata"),
        escalated=result.get("escalated", False),
    )


@router.post("/message", response_model=ChatResponse)
def send_message(data: ChatMessage, db: Session = Depends(get_db)):
    """Send a message to the chatbot and get a response (REST endpoint)."""
    try:
        return _process_message(data.message, data.session_id, data.user_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot error: {str(e)}")


@router.get("/history/{session_id}", response_model=list[dict])
def get_history(session_id: str, db: Session = Depends(get_db)):
    """Get conversation history for a session."""
    conversation = db.query(models.Conversation).filter(
        models.Conversation.session_id == session_id
    ).first()
    if not conversation:
        return []
    return [
        {
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in conversation.messages
    ]


@router.post("/new-session")
def new_session():
    """Create a new chat session ID."""
    return {"session_id": str(uuid.uuid4())}


@router.get("/seats/{flight_id}")
def get_available_seats(flight_id: str, db: Session = Depends(get_db)):
    """Get available seats for a flight (for the booking form seat picker)."""
    seats = tools.get_seat_map(db, flight_id)
    return {"seats": seats}


@router.post("/booking-details", response_model=BookingDetailsResponse)
def create_booking_from_form(data: BookingDetailsRequest, db: Session = Depends(get_db)):
    """Create a booking from the ixigo-style details form.

    Accepts all passenger details, contact info, seat selection, meal
    preference, baggage add-ons, and travel insurance in one request.
    Returns the booking summary so the chat can proceed to payment.
    """
    passengers_list = [
        {
            "full_name": p.full_name,
            "age": p.age,
            "gender": p.gender,
            "seat_number": p.seat_number,
            "meal_preference": p.meal_preference,
            "is_primary": p.is_primary,
        }
        for p in data.passengers
    ]

    result = tools.create_booking(
        db=db,
        flight_id=data.flight_id,
        passengers=passengers_list,
        cabin_class=data.cabin_class,
        user_id=data.user_id,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        travel_insurance=data.travel_insurance,
        extra_baggage_kg=data.extra_baggage_kg,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Save booking result to conversation state so the chat flow can continue
    conversation = db.query(models.Conversation).filter(
        models.Conversation.session_id == data.session_id
    ).first()
    if conversation:
        # Find the last assistant message and update its metadata with booking result
        last_assistant = None
        for msg in reversed(conversation.messages):
            if msg.role == "assistant":
                last_assistant = msg
                break
        booking_result = {
            "booking_id": result["booking_id"],
            "pnr": result["pnr"],
            "total_amount": result["total_amount"],
            "passenger_name": data.passengers[0].full_name if data.passengers else "Guest",
            "contact_email": data.contact_email,
            "contact_phone": data.contact_phone,
            "flight_number": result.get("flight_number", ""),
            "departure_city": result.get("departure_city", ""),
            "arrival_city": result.get("arrival_city", ""),
            "departure_time": result.get("departure_time", ""),
            "passengers": len(data.passengers),
            "travel_insurance": data.travel_insurance,
            "extra_baggage_kg": data.extra_baggage_kg,
        }
        if last_assistant:
            meta = dict(last_assistant.extra_metadata or {})
            meta["booking_result"] = booking_result
            meta["flow_step"] = "payment"
            last_assistant.extra_metadata = meta
            # Also update entities with contact info
            ents = dict(last_assistant.entities or {})
            ents["contact_email"] = data.contact_email
            ents["contact_phone"] = data.contact_phone
            ents["passenger_name"] = data.passengers[0].full_name if data.passengers else "Guest"
            ents["passengers"] = len(data.passengers)
            last_assistant.entities = ents
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(last_assistant, "extra_metadata")
            flag_modified(last_assistant, "entities")
        db.commit()

    return BookingDetailsResponse(
        success=True,
        pnr=result["pnr"],
        booking_id=result["booking_id"],
        total_amount=result["total_amount"],
        flight_number=result["flight_number"],
        departure_city=result["departure_city"],
        arrival_city=result["arrival_city"],
        departure_time=result["departure_time"],
        passenger_name=data.passengers[0].full_name if data.passengers else "Guest",
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        passengers=len(data.passengers),
        travel_insurance=data.travel_insurance,
        extra_baggage_kg=data.extra_baggage_kg,
    )


# ── WebSocket for real-time chat ───────────────────────────────────────────

@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    await websocket.accept()
    session_id = str(uuid.uuid4())

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            user_id = data.get("user_id")

            # Get a fresh DB session
            db = SessionLocal()
            try:
                response = _process_message(message, session_id, user_id, db)
                await websocket.send_json(response.model_dump())
            except Exception as e:
                await websocket.send_json({
                    "session_id": session_id,
                    "reply": f"Error: {str(e)}",
                    "escalated": False,
                })
            finally:
                db.close()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# Import SessionLocal for WebSocket
from database import SessionLocal


# ── CSAT (Customer Satisfaction) ────────────────────────────────────────────

@router.post("/csat", response_model=dict)
def submit_csat(data: CSATCreate, db: Session = Depends(get_db)):
    """Submit a customer satisfaction rating after a conversation."""
    rating = models.CSAT(
        session_id=data.session_id,
        rating=data.rating,
        feedback=data.feedback,
        intent=data.intent,
    )
    db.add(rating)
    db.commit()
    return {"success": True, "message": "Thank you for your feedback!"}
