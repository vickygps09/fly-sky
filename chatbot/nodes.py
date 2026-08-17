"""LangGraph nodes — each node processes a step in the conversation workflow.

Nodes:
- intent_recognition: Classify user intent
- entity_extraction: Extract travel entities
- route_intent: Conditional router
- handle_greeting, handle_book_flight, handle_flight_status, etc.
- generate_response: Final response generation
- escalate_human: Human agent transfer
"""

import json
import re
from datetime import datetime, date, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
import models

from chatbot.state import ChatState
from chatbot.llm import get_llm
from chatbot.prompts import (
    SYSTEM_PROMPT, INTENT_RECOGNITION_PROMPT, ENTITY_EXTRACTION_PROMPT,
    FLIGHT_SEARCH_PROMPT, FARE_RECOMMENDATION_PROMPT, TRAVEL_POLICY_PROMPT,
    FAQ_PROMPT, BOOKING_ASSISTANCE_PROMPT, ESCALATION_PROMPT,
    CONVERSATION_SUMMARY_PROMPT,
)
from chatbot import tools
from chatbot.rag import city_retriever
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


# ── Intent Recognition Node ────────────────────────────────────────────────

def intent_recognition(state: ChatState) -> ChatState:
    """Classify the user's message into an intent."""
    last_message = state["messages"][-1].content if state["messages"] else ""

    # Context-aware: if we're in a multi-turn flow, keep the same intent
    flow_step = state.get("flow_step", "")
    if flow_step and (flow_step.startswith("collect_") or flow_step.startswith("chat_collect_") or flow_step in (
        "select_flight", "select_return_flight", "passenger_details", "payment", "no_flights",
        "confirm_cancel", "awaiting_modification_choice", "choose_booking_method",
        "check_in_select_seat",
    )):
        # User is responding to a question in the booking flow
        # Keep the previous intent unless they explicitly change topic
        msg_lower = last_message.lower().strip()
        # In payment step, "cancel" and "pay" are valid responses, not topic changes
        if flow_step == "payment":
            state["intent"] = state.get("intent") or "book_flight"
            return state
        # In choose_booking_method or chat-based booking steps, keep book_flight intent
        # unless user explicitly changes topic
        if flow_step == "choose_booking_method" or (flow_step and flow_step.startswith("chat_collect_")):
            topic_change_keywords = ["cancel", "status", "refund", "check-in", "check in",
                                     "human agent", "help", "baggage", "modify", "change my",
                                     "compare", "fare", "weather", "forecast", "currency",
                                     "convert", "exchange rate"]
            if not any(kw in msg_lower for kw in topic_change_keywords):
                state["intent"] = "book_flight"
                return state
        # In collect_email_bookings, keep my_bookings intent
        if flow_step == "collect_email_bookings":
            state["intent"] = "my_bookings"
            return state
        # In collect_flight_number, keep flight_status intent — but only if the
        # user's reply actually looks like a flight number. Otherwise fall through
        # to keyword matching so topic changes (e.g., "show my bookings") work.
        if flow_step == "collect_flight_number":
            if re.match(r'^[A-Za-z]{2}\d{2,4}$', msg_lower.strip()):
                state["intent"] = "flight_status"
                return state
            # Not a flight number — fall through to keyword/LLM matching
        # In collect_check_in_pnr, keep check_in intent — but only if the reply
        # looks like a PNR (6 alphanumeric chars). Otherwise fall through.
        elif flow_step == "collect_check_in_pnr":
            if re.match(r'^[A-Za-z0-9]{6}$', msg_lower.strip()):
                state["intent"] = "check_in"
                return state
            # Not a PNR — fall through to keyword/LLM matching
        # In collect_pnr_cancel, keep cancel_booking intent — but only if the reply
        # looks like a PNR (6 alphanumeric chars). Otherwise fall through.
        elif flow_step == "collect_pnr_cancel":
            if re.match(r'^[A-Za-z0-9]{6}$', msg_lower.strip()):
                state["intent"] = "cancel_booking"
                return state
            # Not a PNR — fall through to keyword/LLM matching
        # In confirm_cancel, "yes" and "no" are valid responses
        # But allow explicit intent changes like "check in" or "book flight"
        if flow_step == "confirm_cancel":
            cancel_exit_keywords = ["check-in", "check in", "book", "status", "refund",
                                    "weather", "currency", "baggage", "help", "modify"]
            if not any(kw in msg_lower for kw in cancel_exit_keywords):
                state["intent"] = state.get("intent") or "cancel_booking"
                return state
            # User changed topic — clear cancel flow state
            state["flow_step"] = None
        # In awaiting_modification_choice or modify sub-steps, keep modify intent
        if flow_step in ("awaiting_modification_choice", "collect_new_seat", "collect_new_date", "select_replacement_flight"):
            state["intent"] = state.get("intent") or "modify_booking"
            return state
        # For other steps, check for explicit topic changes
        topic_change_keywords = ["cancel", "status", "refund", "check-in", "check in",
                                 "human agent", "help", "baggage", "modify", "change my",
                                 "compare", "fare", "weather", "forecast", "currency",
                                 "convert", "exchange rate",
                                 "my booking", "my bookings", "show my", "my tickets",
                                 "my reservations", "list my", "what flights do i have",
                                 "book a flight", "book flight", "book ticket", "book",
                                 "find flight", "search flight",
                                 "need a flight", "i want to fly", "plan a trip"]
        if not any(kw in msg_lower for kw in topic_change_keywords):
            state["intent"] = state.get("intent") or "book_flight"
            return state

    # Quick keyword-based pre-check for common intents
    # Ordered by specificity — more specific phrases first to avoid false matches
    msg_lower = last_message.lower().strip()

    # Use word-boundary matching for single words, substring for phrases
    keyword_map = [
        # Refund — check before status since "refund status" contains "status"
        (r"\brefund\b", "refund"),
        # Cancel — check before my_bookings since "cancel my booking" contains "my booking"
        (r"\bcancel\b", "cancel_booking"),
        # Modify — check before my_bookings since "change my booking" contains "my booking"
        (r"\bmodify\b", "modify_booking"),
        ("change my", "modify_booking"),
        ("change the", "modify_booking"),
        (r"\breschedule\b", "modify_booking"),
        # My Bookings — check before book_flight since "bookings" contains "book"
        ("my flight bookings", "my_bookings"),
        ("my booking", "my_bookings"),
        ("my bookings", "my_bookings"),
        ("my tickets", "my_bookings"),
        ("my reservations", "my_bookings"),
        ("show booking", "my_bookings"),
        ("show my", "my_bookings"),
        ("have booked", "my_bookings"),
        ("list my bookings", "my_bookings"),
        ("what flights do i have", "my_bookings"),
        # Book flight
        ("need a flight", "book_flight"),
        ("need a ticket", "book_flight"),
        ("flight from", "book_flight"),
        ("flights from", "book_flight"),
        ("search flight", "book_flight"),
        ("find flight", "book_flight"),
        ("find me a flight", "book_flight"),
        ("fly from", "book_flight"),
        ("i want to fly", "book_flight"),
        ("looking for flight", "book_flight"),
        ("show me flight", "book_flight"),
        ("plan a trip", "book_flight"),
        ("plane ticket", "book_flight"),
        ("travel from", "book_flight"),
        ("i need to travel", "book_flight"),
        ("book 2 tickets", "book_flight"),
        (r"\bbook a flight\b", "book_flight"),
        (r"\bbook\b", "book_flight"),
        # Flight status
        ("flight status", "flight_status"),
        ("on time", "flight_status"),
        ("where is flight", "flight_status"),
        ("departed", "flight_status"),
        ("delayed", "flight_status"),
        (r"\bstatus\b", "flight_status"),
        # Check-in
        ("check-in", "check_in"),
        ("check in", "check_in"),
        ("check me in", "check_in"),
        (r"\bboarding\b", "check_in"),
        # Baggage
        (r"\bbaggage\b", "baggage_info"),
        (r"\bluggage\b", "baggage_info"),
        # Weather
        (r"\bweather\b", "weather"),
        (r"\bforecast\b", "weather"),
        (r"\btemperature in\b", "weather"),
        (r"\bwill it rain\b", "weather"),
        # Currency conversion
        (r"\bconvert\b", "currency_conversion"),
        (r"\bcurrency\b", "currency_conversion"),
        (r"\bexchange rate\b", "currency_conversion"),
        (r"\binr to\b", "currency_conversion"),
        (r"\busd to\b", "currency_conversion"),
        (r"\beur to\b", "currency_conversion"),
        (r"\brupees to\b", "currency_conversion"),
        (r"\bdollars to\b", "currency_conversion"),
        (r"\binr in\b", "currency_conversion"),
        (r"\busd in\b", "currency_conversion"),
        (r"\beur in\b", "currency_conversion"),
        (r"\bin dollars\b", "currency_conversion"),
        (r"\bin rupees\b", "currency_conversion"),
        # Fare comparison
        ("fare comparison", "fare_comparison"),
        (r"\bcompare\b", "fare_comparison"),
        (r"\bfare\b", "fare_comparison"),
        ("cheapest", "fare_comparison"),
        # Human agent — expanded patterns
        ("human agent", "human_agent"),
        ("talk to a human", "human_agent"),
        ("talk to an agent", "human_agent"),
        ("speak with a human", "human_agent"),
        ("speak to a human", "human_agent"),
        ("real person", "human_agent"),
        ("customer service", "human_agent"),
        (r"\brepresentative\b", "human_agent"),
        # Help — expanded patterns
        ("what can you", "help"),
        ("what can you do", "help"),
        ("what you can do", "help"),
        ("capabilities", "help"),
        ("assist me", "help"),
        ("how can you help", "help"),
        (r"\bhelp\b", "help"),
        # Greeting — check last to avoid matching substrings in city names
        ("hiya", "greeting"),
        ("what's up", "greeting"),
        (r"\bhi\b", "greeting"),
        (r"\bhello\b", "greeting"),
        (r"\bhey\b", "greeting"),
        (r"\bgreetings\b", "greeting"),
        (r"\bgood morning\b", "greeting"),
        (r"\bgood evening\b", "greeting"),
        (r"\bgood afternoon\b", "greeting"),
    ]

    for pattern, intent in keyword_map:
        if re.search(pattern, msg_lower):
            state["intent"] = intent
            return state

    # Use LLM for complex intent recognition
    try:
        llm = get_llm(temperature=0)
        conversation_history = state.get("conversation_history", [])
        # Build context from last 4 turns
        context_lines = []
        for hist in conversation_history[-4:]:
            speaker = "User" if hist["role"] == "user" else "Bot"
            context_lines.append(f"{speaker}: {hist['content'][:120]}")
        conversation_context = "\n".join(context_lines) if context_lines else "None"
        prompt = INTENT_RECOGNITION_PROMPT.format(
            message=last_message,
            conversation_context=conversation_context,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        intent = response.content.strip().lower().strip('"').strip("'")
        # Validate intent
        valid_intents = [
            "greeting", "book_flight", "flight_status", "cancel_booking",
            "modify_booking", "refund", "check_in", "baggage_info",
            "fare_comparison", "help", "human_agent", "general_query", "my_bookings",
        ]
        state["intent"] = intent if intent in valid_intents else "general_query"
    except Exception:
        state["intent"] = "general_query"

    return state


# ── Entity Extraction Node ─────────────────────────────────────────────────

def _regex_entity_extraction(message: str, flow_step: str = None, existing_entities: dict = None) -> dict:
    """Fallback entity extraction using regex + RAG city retrieval.

    Uses the CityRetriever (RAG) for robust city matching with:
    - Exact name, alias, and IATA code matching
    - Fuzzy string matching for typos
    - Phonetic (Soundex) matching for misspellings
    
    When flow_step is set (e.g., 'collect_arrival_city'), the extractor
    knows what the user is being asked and assigns entities accordingly.
    """
    entities = {}
    msg_lower = message.lower().strip()
    existing_entities = existing_entities or {}

    # Ensure RAG retriever is initialized
    if not city_retriever._initialized:
        city_retriever.load_from_db()

    # ── City extraction using RAG ──────────────────────────────────────────
    
    # Try "from X to Y" route pattern first
    dep_city, arr_city = city_retriever.extract_route(message)
    if dep_city:
        entities["departure_city"] = dep_city
    if arr_city:
        entities["arrival_city"] = arr_city

    # Context-aware extraction: if the bot asked for a specific field,
    # treat the user's reply as that field's value
    if flow_step:
        if flow_step == "collect_trip_type" and "trip_type" not in entities:
            if "round" in msg_lower or "return" in msg_lower:
                entities["trip_type"] = "round_trip"
            elif "one" in msg_lower or "single" in msg_lower:
                entities["trip_type"] = "one_way"
            # If user said something else, don't set trip_type — will re-ask

        elif flow_step == "collect_departure_city" and "departure_city" not in entities:
            result = city_retriever.retrieve(msg_lower)
            if result:
                entities["departure_city"] = result["city"]

        elif flow_step == "collect_arrival_city" and "arrival_city" not in entities:
            result = city_retriever.retrieve(msg_lower)
            if result:
                entities["arrival_city"] = result["city"]
            # If no city found, don't set arrival_city — let the flow re-ask
            # This prevents non-city input (e.g. 'what the weather') from being saved as a city

        elif flow_step == "collect_departure_date" and "departure_date" not in entities:
            # User is answering the date question
            if "day after" in msg_lower:
                entities["departure_date"] = (date.today() + timedelta(days=2)).isoformat()
            elif "tomorrow" in msg_lower:
                entities["departure_date"] = (date.today() + timedelta(days=1)).isoformat()
            elif "today" in msg_lower:
                entities["departure_date"] = date.today().isoformat()
            else:
                date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', message)
                if date_match:
                    entities["departure_date"] = date_match.group(1)
                else:
                    date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', message)
                    if date_match:
                        d, m, y = date_match.groups()
                        entities["departure_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
                    else:
                        # Try "Month DD, YYYY" format (e.g., "Aug 25, 2026" from calendar picker)
                        date_match = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b', message)
                        if date_match:
                            month_name, day, year = date_match.groups()
                            try:
                                parsed = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
                                entities["departure_date"] = parsed.date().isoformat()
                            except ValueError:
                                try:
                                    parsed = datetime.strptime(f"{month_name} {day} {year}", "%b %d %Y")
                                    entities["departure_date"] = parsed.date().isoformat()
                                except ValueError:
                                    entities["departure_date"] = msg_lower
                        else:
                            # Just accept whatever the user typed as a date string
                            entities["departure_date"] = msg_lower

        elif flow_step == "collect_return_date" and "return_date" not in entities:
            if "day after" in msg_lower:
                entities["return_date"] = (date.today() + timedelta(days=2)).isoformat()
            elif "tomorrow" in msg_lower:
                entities["return_date"] = (date.today() + timedelta(days=1)).isoformat()
            elif "today" in msg_lower:
                entities["return_date"] = date.today().isoformat()
            else:
                date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', message)
                if date_match:
                    entities["return_date"] = date_match.group(1)
                else:
                    date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', message)
                    if date_match:
                        d, m, y = date_match.groups()
                        entities["return_date"] = f"{y}-{int(m):02d}-{int(d):02d}"
                    else:
                        date_match = re.search(r'\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b', message)
                        if date_match:
                            month_name, day, year = date_match.groups()
                            try:
                                parsed = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
                                entities["return_date"] = parsed.date().isoformat()
                            except ValueError:
                                try:
                                    parsed = datetime.strptime(f"{month_name} {day} {year}", "%b %d %Y")
                                    entities["return_date"] = parsed.date().isoformat()
                                except ValueError:
                                    entities["return_date"] = msg_lower
                        else:
                            entities["return_date"] = msg_lower

        elif flow_step == "collect_passengers" and "passengers" not in entities:
            # Extract a number from the message
            num_match = re.search(r'\b(\d+)\b', msg_lower)
            if num_match:
                entities["passengers"] = int(num_match.group(1))
            elif "one" in msg_lower:
                entities["passengers"] = 1
            elif "two" in msg_lower:
                entities["passengers"] = 2
            elif "three" in msg_lower:
                entities["passengers"] = 3
            elif "four" in msg_lower:
                entities["passengers"] = 4

    # If no "from X to Y" pattern and no context, use RAG to find cities
    if "departure_city" not in entities and "arrival_city" not in entities and not flow_step:
        cities_found = city_retriever.extract_cities(message)
        if len(cities_found) >= 2:
            entities["departure_city"] = cities_found[0]["city"]
            entities["arrival_city"] = cities_found[1]["city"]
        elif len(cities_found) == 1:
            entities["departure_city"] = cities_found[0]["city"]

    # Date extraction (skip if already set via flow_step handler or collecting return date)
    if flow_step != "collect_return_date" and "departure_date" not in entities:
        if "day after" in msg_lower:
            entities["departure_date"] = (date.today() + timedelta(days=2)).isoformat()
        elif "tomorrow" in msg_lower:
            entities["departure_date"] = (date.today() + timedelta(days=1)).isoformat()
        elif "today" in msg_lower:
            entities["departure_date"] = date.today().isoformat()
        else:
            # YYYY-MM-DD format
            date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', message)
            if date_match:
                entities["departure_date"] = date_match.group(1)
            else:
                # DD/MM/YYYY or MM/DD/YYYY format
                date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', message)
                if date_match:
                    d, m, y = date_match.groups()
                    entities["departure_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

    # Return date
    if "return" in msg_lower:
        if "day after tomorrow" in msg_lower or "day after" in msg_lower:
            entities["return_date"] = (date.today() + timedelta(days=2)).isoformat()
        elif "tomorrow" in msg_lower:
            entities["return_date"] = (date.today() + timedelta(days=1)).isoformat()
        elif "today" in msg_lower:
            entities["return_date"] = date.today().isoformat()
        else:
            # Look for YYYY-MM-DD after "return"
            return_date_match = re.search(r'return(?:ing)?\s+(?:on\s+)?(\d{4}-\d{2}-\d{2})', msg_lower)
            if return_date_match:
                entities["return_date"] = return_date_match.group(1)
            else:
                # Look for DD/MM/YYYY after "return"
                return_date_match = re.search(r'return(?:ing)?\s+(?:on\s+)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})', msg_lower)
                if return_date_match:
                    d, m, y = return_date_match.groups()
                    entities["return_date"] = f"{y}-{int(m):02d}-{int(d):02d}"

    # Passenger count
    pax_match = re.search(r'(\d+)\s+passenger', msg_lower)
    if pax_match:
        entities["passengers"] = int(pax_match.group(1))
    else:
        # "for 3 people", "for 2 adults"
        pax_match = re.search(r'(?:for|with)\s+(\d+)\s+(?:people|adults|persons|travellers|travelers)', msg_lower)
        if pax_match:
            entities["passengers"] = int(pax_match.group(1))

    # Cabin class
    if "business" in msg_lower:
        entities["cabin_class"] = "business"
    elif "first class" in msg_lower:
        entities["cabin_class"] = "first"
    elif "premium" in msg_lower:
        entities["cabin_class"] = "premium_economy"
    elif "economy" in msg_lower:
        entities["cabin_class"] = "economy"

    # Trip type
    if "round trip" in msg_lower or "round-trip" in msg_lower or "return flight" in msg_lower:
        entities["trip_type"] = "round_trip"
    elif "one way" in msg_lower or "one-way" in msg_lower:
        entities["trip_type"] = "one_way"

    # Booking ID / PNR (6 alphanumeric chars, must contain at least one digit)
    pnr_matches = re.findall(r'\b([A-Z0-9]{6})\b', message.upper())
    for candidate in pnr_matches:
        # Must contain at least one digit to avoid matching common words
        if any(c.isdigit() for c in candidate) and candidate not in ["PLEASE", "THANK"]:
            entities["booking_id"] = candidate
            break

    # Flight number (e.g., SB101, AI234)
    flight_match = re.search(r'\b([A-Z]{2}\d{2,4})\b', message.upper())
    if flight_match:
        entities["flight_number"] = flight_match.group(1)

    # Seat number (e.g., 12A)
    seat_match = re.search(r'\bseat\s+(\d{1,2}[A-F])\b', msg_lower)
    if seat_match:
        entities["seat_number"] = seat_match.group(1).upper()
    else:
        seat_match = re.search(r'\b(\d{1,2}[A-F])\b', message.upper())
        if seat_match:
            entities["seat_number"] = seat_match.group(1)

    return entities


def entity_extraction(state: ChatState) -> ChatState:
    """Extract travel-related entities from the user's message."""
    last_message = state["messages"][-1].content if state["messages"] else ""
    today = date.today().isoformat()

    entities = {}
    llm_success = False

    # Skip LLM entity extraction during multi-turn collection steps —
    # these are simple text/number/date replies that don't need LLM parsing,
    # and the LLM call can timeout or hit rate limits.
    flow_step = state.get("flow_step")
    if flow_step and (flow_step.startswith("chat_collect_") or flow_step.startswith("collect_")):
        existing_ents = state.get("entities", {})
        regex_entities = _regex_entity_extraction(last_message, flow_step, existing_ents)
        entities = regex_entities
        existing = state.get("entities", {})
        if flow_step.startswith("chat_collect_"):
            entities.pop("passengers", None)
        # Don't overwrite already-collected fields
        if flow_step.startswith("collect_"):
            collecting_field = flow_step.replace("collect_", "")
            for k in list(entities.keys()):
                if k != collecting_field and k in existing and existing[k]:
                    entities.pop(k, None)
        existing.update(entities)
        state["entities"] = existing
        return state

    try:
        llm = get_llm(temperature=0)
        existing_ents = state.get("entities", {})
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            message=last_message,
            today=today,
            existing_entities=json.dumps(existing_ents, ensure_ascii=False) if existing_ents else "{}",
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # Clean up markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        entities = json.loads(content)
        llm_success = True
    except Exception:
        entities = {}

    # Post-process: normalize city names from LLM through RAG retriever
    # This ensures "Bengaluru" → "Bangalore", "Bombay" → "Mumbai", etc.
    # Also removes invalid or hallucinated cities.
    if entities:
        if not city_retriever._initialized:
            city_retriever.load_from_db()
        msg_lower_check = last_message.lower()
        for city_field in ("departure_city", "arrival_city"):
            if city_field in entities and entities[city_field]:
                city_val = str(entities[city_field])
                result = city_retriever.retrieve(city_val)
                if result:
                    # Validate: the city, its alias, or IATA code must appear in the
                    # original message — otherwise the LLM likely hallucinated it
                    city_lower = result["city"].lower()
                    aliases_for_city = [k for k, v in city_retriever._alias_index.items() if v.get("code") == result["code"]]
                    code_lower = result["code"].lower()
                    all_variants = [city_lower, code_lower] + aliases_for_city
                    if any(v in msg_lower_check for v in all_variants):
                        entities[city_field] = result["city"]
                    else:
                        # City not mentioned in message — likely hallucinated
                        entities.pop(city_field, None)
                else:
                    # City not recognized — remove it so the flow will ask again
                    entities.pop(city_field, None)

    # Fallback: regex+RAG extraction if LLM failed or returned empty
    # Pass flow_step and existing entities for context-aware extraction
    flow_step = state.get("flow_step")
    existing_ents = state.get("entities", {})
    if not llm_success or not entities:
        regex_entities = _regex_entity_extraction(last_message, flow_step, existing_ents)
        # Merge: LLM entities take priority, fill gaps with regex
        for k, v in regex_entities.items():
            if k not in entities:
                entities[k] = v
    else:
        # Even if LLM succeeded, use context-aware regex to fill any gaps
        # (e.g., if LLM missed the arrival city but flow_step says we asked for it)
        if flow_step and flow_step.startswith("collect_"):
            field_name = flow_step.replace("collect_", "")
            regex_entities = _regex_entity_extraction(last_message, flow_step, existing_ents)
            # Regex takes priority for the field being collected — LLM often
            # gets relative dates wrong (e.g., "day after tomorrow" → same as departure)
            if field_name in regex_entities:
                entities[field_name] = regex_entities[field_name]
            for k, v in regex_entities.items():
                if k not in entities:
                    entities[k] = v

    # Merge with existing entities (accumulate over conversation)
    existing = state.get("entities", {})
    # Don't let entity extraction overwrite passengers when the user is
    # choosing booking method, selecting a flight, or answering chat-based booking questions —
    # a "1" or "2" or "3" reply is a method/step/flight choice, not a passenger count.
    current_flow = state.get("flow_step")
    if current_flow in ("choose_booking_method", "select_flight", "payment") or (current_flow and current_flow.startswith("chat_collect_")):
        entities.pop("passengers", None)

    # When in a collect_ flow step, don't let LLM overwrite already-collected fields
    # (e.g., LLM might extract "Delhi" as departure_city when user is answering arrival_city)
    if current_flow and current_flow.startswith("collect_"):
        collecting_field = current_flow.replace("collect_", "")
        for k in list(entities.keys()):
            if k != collecting_field and k in existing and existing[k]:
                # Don't overwrite an already-set field with LLM extraction
                entities.pop(k, None)

    existing.update(entities)
    state["entities"] = existing

    return state


# ── Greeting Node ──────────────────────────────────────────────────────────

def handle_greeting(state: ChatState) -> ChatState:
    """Handle greeting intent."""
    state["response"] = (
        "👋 Welcome to **SkyBook AI** — your intelligent airline assistant!\n\n"
        "I can help you with:\n"
        "✈️ Search & book flights\n"
        "📊 Check flight status\n"
        "🎫 Modify or cancel bookings\n"
        "💰 Refund status\n"
        "✅ Web check-in & boarding pass\n"
        "🧳 Baggage information\n\n"
        "How can I assist you today?"
    )
    state["response_metadata"] = {
        "quick_replies": [
            "Book a flight", "Check flight status", "Cancel booking",
            "Web check-in", "Baggage info", "Talk to agent"
        ]
    }
    return state


# ── Book Flight Node ───────────────────────────────────────────────────────

def handle_book_flight(state: ChatState) -> ChatState:
    """Handle flight booking — multi-turn conversation flow."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    flow_step = state.get("flow_step", "start")
    last_message = state["messages"][-1].content if state["messages"] else ""
    msg_lower = last_message.lower().strip()

    # If user asks about available cities/routes, show them regardless of flow step
    if any(kw in msg_lower for kw in (
        "which cit", "available cit", "available route", "where can",
        "what cit", "list cit", "show cit", "show route", "routes",
        "cities available", "cities service", "cities do you",
        "cities fly", "cities go", "destinations",
    )):
        if db:
            try:
                routes = tools.get_available_routes(db)
                if routes:
                    from collections import defaultdict
                    route_map = defaultdict(list)
                    for dep, arr in routes:
                        route_map[dep].append(arr)
                    route_lines = []
                    for dep in sorted(route_map.keys()):
                        route_lines.append(f"  **{dep}** → {', '.join(route_map[dep])}")
                    state["response"] = (
                        "🗺️ **Available flight routes:**\n\n"
                        + "\n".join(route_lines)
                        + "\n\nJust tell me which route you'd like, e.g., 'Mumbai to Delhi tomorrow'"
                    )
                    state["response_metadata"] = {"quick_replies": ["Mumbai to Delhi", "Bangalore to Chennai", "Delhi to Kolkata"]}
                    return state
            except Exception:
                pass

    # If user says a booking trigger phrase, start fresh — clear all previous state
    booking_triggers = {
        "book a flight", "book flight", "search flight", "search flights",
        "find flight", "find flights", "book a ticket", "book ticket",
        "i want to book a flight", "i want to fly", "book",
    }
    if msg_lower in booking_triggers:
        state["flow_step"] = None
        state["entities"] = {}
        state["search_results"] = None
        state["selected_flight"] = None
        state["selected_return_flight"] = None
        state["chat_passengers"] = []
        state["chat_contact_email"] = None
        state["chat_contact_phone"] = None
        flow_step = None
        entities = {}

    # ── Handle no_flights state — user is responding after no flights found ──
    if flow_step == "no_flights":
        msg_lower = last_message.lower().strip()

        # User wants to cancel / start over
        if "cancel" in msg_lower or "start over" in msg_lower or "stop" in msg_lower:
            state["flow_step"] = None
            state["entities"] = {}
            state["response"] = (
                "✅ Started fresh. Tell me where you'd like to fly!\n\n"
                "e.g., *Book a flight from Mumbai to Delhi tomorrow*"
            )
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Check flight status"]}
            return state

        # User wants to try different cities / route
        if "different cit" in msg_lower or "different route" in msg_lower or "new route" in msg_lower:
            state["flow_step"] = "collect_departure_city"
            state["entities"] = {}  # Clear old route
            state["response"] = "✈️ From which city would you like to depart?"
            state["response_metadata"] = {"quick_replies": []}
            return state

        # User is asking about available cities/routes
        if any(kw in msg_lower for kw in ("which cit", "available", "where can", "what cit", "list cit", "show cit", "routes")):
            if db:
                try:
                    routes = tools.get_available_routes(db)
                    if routes:
                        from collections import defaultdict
                        route_map = defaultdict(list)
                        for dep, arr in routes:
                            route_map[dep].append(arr)
                        route_lines = []
                        for dep in sorted(route_map.keys()):
                            route_lines.append(f"  **{dep}** → {', '.join(route_map[dep])}")
                        state["response"] = (
                            "🗺️ **Available flight routes:**\n\n"
                            + "\n".join(route_lines)
                            + "\n\nJust tell me which route you'd like, e.g., 'Mumbai to Delhi tomorrow'"
                        )
                        state["response_metadata"] = {"quick_replies": ["Mumbai to Delhi", "Bangalore to Chennai", "Delhi to Kolkata"]}
                        return state
                except Exception:
                    pass

        # Check if user provided a date (try tomorrow, today, or date format)
        new_date = None
        if "tomorrow" in msg_lower:
            new_date = (date.today() + timedelta(days=1)).isoformat()
        elif "today" in msg_lower:
            new_date = date.today().isoformat()
        elif "day after" in msg_lower:
            new_date = (date.today() + timedelta(days=2)).isoformat()
        else:
            date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', last_message)
            if date_match:
                new_date = date_match.group(1)
            else:
                date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', last_message)
                if date_match:
                    d, m, y = date_match.groups()
                    new_date = f"{y}-{int(m):02d}-{int(d):02d}"

        # Check if user provided new cities (from X to Y pattern)
        dep_city, arr_city = city_retriever.extract_route(last_message)
        if dep_city and arr_city:
            state["entities"]["departure_city"] = dep_city
            state["entities"]["arrival_city"] = arr_city
            # Also check for a date in the same message
            if new_date:
                state["entities"]["departure_date"] = new_date
            state["flow_step"] = None  # Will re-search below
        elif new_date:
            # User provided a new date — update and re-search with same route
            state["entities"]["departure_date"] = new_date
            state["flow_step"] = None  # Will re-search below
        else:
            # User said something we can't parse — try extracting any cities
            cities_found = city_retriever.extract_cities(last_message)
            if len(cities_found) >= 2:
                state["entities"]["departure_city"] = cities_found[0]["city"]
                state["entities"]["arrival_city"] = cities_found[1]["city"]
                state["flow_step"] = None  # Will re-search below
            elif "no" in msg_lower or "where" in msg_lower:
                # User is asking for help / where to book
                state["flow_step"] = None
                state["entities"] = {}
                state["response"] = (
                    "I can help you find flights! Just tell me:\n\n"
                    "• **From** which city\n"
                    "• **To** which city\n"
                    "• **When** you want to travel\n\n"
                    "e.g., *Find flights from Mumbai to Delhi on 2025-08-20*"
                )
                state["response_metadata"] = {
                    "quick_replies": ["Mumbai to Delhi", "Chennai to Bangalore", "Kolkata to Hyderabad"]
                }
                return state
            else:
                # Can't understand — ask again
                state["response"] = (
                    "I didn't catch that. Would you like to:\n"
                    "1️⃣ Try a **different date** (e.g., 'tomorrow' or '2025-08-20')\n"
                    "2️⃣ Try **different cities** (e.g., 'Mumbai to Delhi')\n"
                    "3️⃣ **Cancel** to start over"
                )
                state["response_metadata"] = {
                    "quick_replies": ["Try tomorrow", "Try different cities", "Cancel"],
                }
                return state

        # If we updated entities and cleared flow_step, fall through to re-search
        flow_step = None

    # ── Handle flight selection ────────────────────────────────────────────
    if flow_step == "select_flight":
        search_results = state.get("search_results", [])
        # Handle round-trip results (stored as dict with 'outbound' key)
        if isinstance(search_results, dict):
            search_results = search_results.get("outbound", [])

        # Try to extract a flight number from the message
        selected_idx = None

        # Check for "option N" or "flight N" or just "N"
        option_match = re.search(r'(?:option|flight|choice)\s+(\d+)', msg_lower)
        if option_match:
            selected_idx = int(option_match.group(1)) - 1
        elif msg_lower.isdigit():
            selected_idx = int(msg_lower) - 1
        else:
            # Check for flight number like "SB167"
            flight_match = re.search(r'\b([A-Z]{2}\d{2,4})\b', last_message.upper())
            if flight_match:
                fn = flight_match.group(1)
                for i, f in enumerate(search_results):
                    if f["flight_number"].upper() == fn:
                        selected_idx = i
                        break

        if selected_idx is not None and 0 <= selected_idx < len(search_results):
            selected = search_results[selected_idx]
            state["selected_flight"] = selected

            # If round-trip, ask user to select a return flight
            trip_type = entities.get("trip_type", "one_way")
            all_results = state.get("search_results", {})
            if trip_type == "round_trip" and isinstance(all_results, dict) and all_results.get("return"):
                return_flights = all_results["return"]
                state["flow_step"] = "select_return_flight"

                ret_lines = []
                for i, f in enumerate(return_flights, 1):
                    dep_time = datetime.fromisoformat(f["departure_time"]).strftime("%H:%M")
                    arr_time = datetime.fromisoformat(f["arrival_time"]).strftime("%H:%M")
                    ret_lines.append(
                        f"**{i}.** ✈️ {f['flight_number']}\n"
                        f"   🕐 {dep_time} → {arr_time}\n"
                        f"   💰 ₹{f['price']:,} per passenger"
                    )

                return_date_str = ""
                try:
                    return_date_str = date.fromisoformat(entities["return_date"]).strftime('%B %d, %Y')
                except (ValueError, KeyError):
                    pass

                state["response"] = (
                    f"✈️ **Outbound selected: {selected['flight_number']} — {selected['departure_airport_city']} → {selected['arrival_airport_city']}**\n\n"
                    f"🔁 **Return flights** ({return_date_str}):\n\n"
                    + "\n\n".join(ret_lines)
                    + "\n\nWhich **return flight** would you like? Reply with the **number**."
                )
                state["response_metadata"] = {
                    "flight_cards": return_flights,
                    "quick_replies": [str(i + 1) for i in range(len(return_flights))],
                }
                return state

            # One-way: proceed directly to booking method
            state["flow_step"] = "choose_booking_method"
            state["response"] = (
                f"✈️ **Selected: {selected['flight_number']} — {selected['departure_airport_city']} → {selected['arrival_airport_city']}**\n"
                f"🕐 {datetime.fromisoformat(selected['departure_time']).strftime('%H:%M')} → {datetime.fromisoformat(selected['arrival_time']).strftime('%H:%M')}\n"
                f"💰 ₹{selected['price']:,} per passenger\n\n"
                f"How would you like to proceed with your booking?\n\n"
                f"1️⃣ **Booking Form** — Fill out a quick form with all details at once\n"
                f"2️⃣ **Chat** — Provide passenger details step-by-step in chat\n\n"
                f"Reply with **1** or **2**."
            )
            state["response_metadata"] = {
                "quick_replies": ["1 - Booking Form", "2 - Chat"],
            }
            return state
        else:
            state["response"] = (
                f"Please reply with a valid flight number (1-{len(search_results)}) "
                f"to select your flight, or type 'cancel' to start over."
            )
            state["response_metadata"] = {"quick_replies": [str(i + 1) for i in range(len(search_results))]}
            return state

    # ── Handle return flight selection (round-trip) ───────────────────────
    if flow_step == "select_return_flight":
        all_results = state.get("search_results", {})
        return_flights = []
        if isinstance(all_results, dict):
            return_flights = all_results.get("return", [])

        selected_idx = None
        option_match = re.search(r'(?:option|flight|choice)\s+(\d+)', msg_lower)
        if option_match:
            selected_idx = int(option_match.group(1)) - 1
        elif msg_lower.isdigit():
            selected_idx = int(msg_lower) - 1
        else:
            flight_match = re.search(r'\b([A-Z]{2}\d{2,4})\b', last_message.upper())
            if flight_match:
                fn = flight_match.group(1)
                for i, f in enumerate(return_flights):
                    if f["flight_number"].upper() == fn:
                        selected_idx = i
                        break

        if selected_idx is not None and 0 <= selected_idx < len(return_flights):
            selected_return = return_flights[selected_idx]
            state["selected_return_flight"] = selected_return
            state["flow_step"] = "choose_booking_method"

            outbound = state.get("selected_flight", {})
            total_price = outbound.get("price", 0) + selected_return.get("price", 0)
            state["response"] = (
                f"✈️ **Outbound: {outbound.get('flight_number', '')} — {outbound.get('departure_airport_city', '')} → {outbound.get('arrival_airport_city', '')}**\n"
                f"🕐 {datetime.fromisoformat(outbound['departure_time']).strftime('%H:%M')} → {datetime.fromisoformat(outbound['arrival_time']).strftime('%H:%M')}\n"
                f"💰 ₹{outbound.get('price', 0):,} per passenger\n\n"
                f"🔁 **Return: {selected_return['flight_number']} — {selected_return['departure_airport_city']} → {selected_return['arrival_airport_city']}**\n"
                f"🕐 {datetime.fromisoformat(selected_return['departure_time']).strftime('%H:%M')} → {datetime.fromisoformat(selected_return['arrival_time']).strftime('%H:%M')}\n"
                f"💰 ₹{selected_return['price']:,} per passenger\n\n"
                f"**Total: ₹{total_price:,} per passenger**\n\n"
                f"How would you like to proceed with your booking?\n\n"
                f"1️⃣ **Booking Form** — Fill out a quick form with all details at once\n"
                f"2️⃣ **Chat** — Provide passenger details step-by-step in chat\n\n"
                f"Reply with **1** or **2**."
            )
            state["response_metadata"] = {
                "quick_replies": ["1 - Booking Form", "2 - Chat"],
            }
            return state
        else:
            state["response"] = (
                f"Please reply with a valid return flight number (1-{len(return_flights)}) "
                f"to select your return flight, or type 'cancel' to start over."
            )
            state["response_metadata"] = {"quick_replies": [str(i + 1) for i in range(len(return_flights))]}
            return state

    # ── Handle booking method choice ──────────────────────────────────────
    if flow_step == "choose_booking_method":
        selected = state.get("selected_flight")
        if not selected:
            state["response"] = "Something went wrong — please search for flights again."
            state["flow_step"] = None
            return state

        passengers = int(entities.get("passengers", 1))

        # User chose booking form (1) or mentioned "form"
        if "1" in msg_lower or "form" in msg_lower:
            state["flow_step"] = "passenger_details"
            state["response"] = (
                f"✈️ **Selected: {selected['flight_number']} — {selected['departure_airport_city']} → {selected['arrival_airport_city']}**\n"
                f"🕐 {datetime.fromisoformat(selected['departure_time']).strftime('%H:%M')} → {datetime.fromisoformat(selected['arrival_time']).strftime('%H:%M')}\n"
                f"💰 ₹{selected['price']:,} per passenger\n\n"
                f"📝 Please fill in the **passenger details form** below to proceed with your booking."
            )
            state["response_metadata"] = {
                "show_booking_form": True,
                "flight_info": selected,
                "passenger_count": passengers,
                "quick_replies": [],
            }
            return state

        # User chose chat-based booking (2) or mentioned "chat"
        elif "2" in msg_lower or "chat" in msg_lower:
            state["flow_step"] = "chat_collect_name"
            state["chat_passengers"] = []
            state["chat_contact_email"] = None
            state["chat_contact_phone"] = None
            state["response"] = (
                f"Great! Let's book through chat. ✈️\n\n"
                f"For passenger 1 of {passengers}:\n"
                f"What is the **passenger's full name**?"
            )
            state["response_metadata"] = {"quick_replies": []}
            return state

        # User said cancel
        elif "cancel" in msg_lower:
            state["flow_step"] = None
            state["entities"] = {}
            state["chat_passengers"] = []
            state["response"] = "✅ Booking cancelled. Tell me where you'd like to fly!"
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Check flight status"]}
            return state

        # Unrecognized input
        else:
            state["response"] = (
                "Please choose how you'd like to proceed:\n\n"
                "1️⃣ **Booking Form** — Fill out a quick form with all details at once\n"
                "2️⃣ **Chat** — Provide passenger details step-by-step in chat\n\n"
                "Reply with **1** or **2**."
            )
            state["response_metadata"] = {"quick_replies": ["1 - Booking Form", "2 - Chat"]}
            return state

    # ── Handle chat-based passenger details collection ────────────────────
    if flow_step and flow_step.startswith("chat_collect_"):
        selected = state.get("selected_flight")
        if not selected:
            state["response"] = "Something went wrong — please search for flights again."
            state["flow_step"] = None
            return state

        passengers = int(entities.get("passengers", 1))
        chat_passengers = state.get("chat_passengers", [])
        current_pax_idx = len(chat_passengers)

        if flow_step == "chat_collect_name":
            name = last_message.strip()
            if len(name) < 2:
                state["response"] = "Please provide a valid full name (at least 2 characters)."
                return state
            chat_passengers.append({"full_name": name})
            state["chat_passengers"] = chat_passengers
            state["flow_step"] = "chat_collect_age"
            state["response"] = f"What is **{name}'s age**?"
            state["response_metadata"] = {"quick_replies": []}
            return state

        if flow_step == "chat_collect_age":
            age_match = re.search(r'\b(\d{1,3})\b', last_message)
            if not age_match:
                state["response"] = "Please provide a valid age (e.g., 28)."
                return state
            age = int(age_match.group(1))
            if age < 1 or age > 120:
                state["response"] = "Please provide a valid age between 1 and 120."
                return state
            chat_passengers[-1]["age"] = age
            state["chat_passengers"] = chat_passengers
            state["flow_step"] = "chat_collect_gender"
            state["response"] = f"What is **{chat_passengers[-1]['full_name']}'s gender**? (male / female / other)"
            state["response_metadata"] = {"quick_replies": ["Male", "Female", "Other"]}
            return state

        if flow_step == "chat_collect_gender":
            gender = msg_lower.strip()
            if gender in ("male", "m", "female", "f", "other", "o"):
                gender = {"m": "male", "f": "female", "o": "other"}.get(gender, gender)
            else:
                state["response"] = "Please reply with: male, female, or other."
                state["response_metadata"] = {"quick_replies": ["Male", "Female", "Other"]}
                return state
            chat_passengers[-1]["gender"] = gender
            state["chat_passengers"] = chat_passengers

            # Ask meal preference for this passenger
            state["flow_step"] = "chat_collect_meal"
            state["response"] = (
                f"What is **{chat_passengers[-1]['full_name']}'s meal preference**?\n"
                f"🍽️ Options: **Veg**, **Non-Veg**, **Jain**, or **None**"
            )
            state["response_metadata"] = {"quick_replies": ["Veg", "Non-Veg", "Jain", "None"]}
            return state

        if flow_step == "chat_collect_meal":
            meal = msg_lower.strip()
            meal_map = {
                "veg": "veg", "vegetarian": "veg", "v": "veg",
                "non-veg": "non_veg", "nonveg": "non_veg", "non veg": "non_veg", "nv": "non_veg", "n": "non_veg",
                "jain": "jain", "j": "jain",
                "none": "none", "no": "none", "skip": "none", "n/a": "none",
            }
            meal_pref = meal_map.get(meal)
            if not meal_pref:
                state["response"] = "Please reply with: **Veg**, **Non-Veg**, **Jain**, or **None**."
                state["response_metadata"] = {"quick_replies": ["Veg", "Non-Veg", "Jain", "None"]}
                return state
            chat_passengers[-1]["meal_preference"] = meal_pref
            state["chat_passengers"] = chat_passengers

            # Check if more passengers to collect
            if len(chat_passengers) < passengers:
                state["flow_step"] = "chat_collect_name"
                state["response"] = (
                    f"Got it! ✅\n\n"
                    f"For passenger {len(chat_passengers) + 1} of {passengers}:\n"
                    f"What is the **passenger's full name**?"
                )
                state["response_metadata"] = {"quick_replies": []}
                return state

            # All passengers collected — ask for extra baggage
            state["flow_step"] = "chat_collect_baggage"
            state["response"] = (
                f"All {passengers} passenger(s) collected! ✅\n\n"
                f"🧳 **Baggage Options:**\n"
                f"Your flight includes **{selected.get('cabin_baggage_kg', 7)} kg** cabin baggage "
                f"and **{selected.get('checked_baggage_kg', 15)} kg** checked baggage.\n\n"
                f"Would you like to add **extra baggage**?\n"
                f"• **+5 kg** — ₹500\n"
                f"• **+10 kg** — ₹900\n"
                f"• **+20 kg** — ₹1,500\n"
                f"• **None** — no extra baggage\n\n"
                f"Reply with '5', '10', '20', or 'none'."
            )
            state["response_metadata"] = {"quick_replies": ["+5 kg", "+10 kg", "+20 kg", "None"]}
            return state

        if flow_step == "chat_collect_baggage":
            baggage_map = {"5": 5, "10": 10, "20": 20, "none": 0, "no": 0, "skip": 0, "0": 0, "+5": 5, "+10": 10, "+20": 20, "+5 kg": 5, "+10 kg": 10, "+20 kg": 20}
            extra_kg = baggage_map.get(msg_lower)
            if extra_kg is None:
                state["response"] = "Please reply with '5', '10', '20', or 'none'."
                state["response_metadata"] = {"quick_replies": ["+5 kg", "+10 kg", "+20 kg", "None"]}
                return state
            state["chat_extra_baggage"] = extra_kg

            # Ask about travel insurance
            state["flow_step"] = "chat_collect_insurance"
            baggage_cost = {5: 500, 10: 900, 20: 1500}.get(extra_kg, 0)
            state["response"] = (
                f"🧳 Extra baggage: {'+' + str(extra_kg) + ' kg (₹' + str(baggage_cost) + ')' if extra_kg > 0 else 'No extra baggage'}\n\n"
                f"🛡️ Would you like to add **travel insurance** for ₹200?\n"
                f"It covers trip cancellation, lost baggage, and medical emergencies.\n\n"
                f"Reply with **Yes** or **No**."
            )
            state["response_metadata"] = {"quick_replies": ["Yes", "No"]}
            return state

        if flow_step == "chat_collect_insurance":
            insurance = msg_lower in ("yes", "y", "yeah", "sure", "ok", "okay")
            state["chat_insurance"] = insurance

            # Ask for coupon code
            state["flow_step"] = "chat_collect_coupon"
            state["response"] = (
                f"🛡️ Travel insurance: {'Yes (₹200)' if insurance else 'No'}\n\n"
                f"🎫 Do you have a **coupon or promo code**?\n"
                f"Enter your code, or type **'skip'** to continue without a discount."
            )
            state["response_metadata"] = {"quick_replies": ["Skip"]}
            return state

        if flow_step == "chat_collect_coupon":
            if msg_lower in ("skip", "no", "none", "n/a", ""):
                state["chat_coupon_code"] = None
                state["chat_discount"] = 0
            else:
                code = last_message.strip()
                # Calculate current total for coupon validation
                base_price_map = {"economy": selected.get("price", 3000), "premium_economy": selected.get("price", 6000),
                                  "business": selected.get("price", 12000), "first": selected.get("price", 20000)}
                est_total = base_price_map.get(entities.get("cabin_class", "economy"), selected.get("price", 3000)) * passengers
                if state.get("chat_extra_baggage", 0) > 0:
                    est_total += {5: 500, 10: 900, 20: 1500}.get(int(state["chat_extra_baggage"]), 0)
                if state.get("chat_insurance", False):
                    est_total += 200

                coupon_result = tools.validate_coupon(db, code, est_total)
                if not coupon_result.get("valid"):
                    state["response"] = f"❌ {coupon_result.get('error', 'Invalid code.')}\n\nPlease try again or type **'skip'**."
                    state["response_metadata"] = {"quick_replies": ["Skip"]}
                    return state
                state["chat_coupon_code"] = coupon_result["code"]
                state["chat_discount"] = coupon_result["discount_amount"]
                state["response"] = (
                    f"✅ Coupon **{coupon_result['code']}** applied!\n"
                    f"💰 Discount: ₹{coupon_result['discount_amount']:,}\n\n"
                )

            # Ask for contact email
            state["flow_step"] = "chat_collect_email"
            discount = state.get("chat_discount", 0)
            state["response"] = (
                state.get("response", "") +
                f"What is your **email address** for the booking confirmation?"
            )
            state["response_metadata"] = {"quick_replies": []}
            return state

        if flow_step == "chat_collect_email":
            email = msg_lower.strip()
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', email)
            if not email_match:
                state["response"] = "Please provide a valid email address (e.g., john@example.com)."
                return state
            state["chat_contact_email"] = email_match.group()
            state["flow_step"] = "chat_collect_phone"
            state["response"] = "What is your **phone number**?"
            state["response_metadata"] = {"quick_replies": []}
            return state

        if flow_step == "chat_collect_phone":
            phone = re.sub(r'[^\d+]', '', last_message.strip())
            if len(phone) < 10:
                state["response"] = "Please provide a valid phone number (at least 10 digits)."
                return state
            # Normalize: if 10-digit Indian number without country code, add +91
            if len(phone) == 10 and not phone.startswith("+"):
                phone = "+91" + phone
            elif len(phone) == 12 and phone.startswith("91"):
                phone = "+" + phone
            elif not phone.startswith("+") and len(phone) > 10:
                phone = "+" + phone
            state["chat_contact_phone"] = phone

            # All details collected — create the booking via tools
            if db:
                return_flight = state.get("selected_return_flight")
                result = tools.create_booking(
                    db=db,
                    flight_id=selected["id"],
                    passengers=chat_passengers,
                    cabin_class=entities.get("cabin_class", "economy"),
                    trip_type=entities.get("trip_type", "one_way"),
                    return_flight_id=return_flight["id"] if return_flight else None,
                    user_id=state.get("user_id"),
                    contact_email=state["chat_contact_email"],
                    contact_phone=phone,
                    travel_insurance=state.get("chat_insurance", False),
                    extra_baggage_kg=state.get("chat_extra_baggage", 0),
                )

                if "error" in result:
                    state["response"] = f"❌ {result['error']}"
                    state["flow_step"] = None
                    return state

                # Apply coupon discount
                discount = state.get("chat_discount", 0)
                if discount > 0:
                    result["total_amount"] = max(0, result["total_amount"] - discount)
                    # Increment coupon/promo usage count
                    coupon_code = state.get("chat_coupon_code")
                    if coupon_code and db:
                        coupon_obj = db.query(models.Coupon).filter(models.Coupon.code.ilike(coupon_code)).first()
                        if coupon_obj:
                            coupon_obj.used_count += 1
                        else:
                            promo_obj = db.query(models.Promotion).filter(models.Promotion.promo_code.ilike(coupon_code)).first()
                            if promo_obj:
                                promo_obj.used_count += 1
                        db.commit()

                state["booking_result"] = {
                    "booking_id": result["booking_id"],
                    "pnr": result["pnr"],
                    "total_amount": result["total_amount"],
                    "passenger_name": chat_passengers[0]["full_name"],
                    "contact_email": state["chat_contact_email"],
                    "contact_phone": phone,
                    "flight_number": result.get("flight_number", selected.get("flight_number", "")),
                    "departure_city": result.get("departure_city", selected.get("departure_airport_city", "")),
                    "arrival_city": result.get("arrival_city", selected.get("arrival_airport_city", "")),
                    "departure_time": result.get("departure_time", selected.get("departure_time", "")),
                    "passengers": len(chat_passengers),
                    "travel_insurance": state.get("chat_insurance", False),
                    "extra_baggage_kg": state.get("chat_extra_baggage", 0),
                }
                state["flow_step"] = "payment"
                total = result["total_amount"]

                # Build passenger summary with meal info
                pax_lines = []
                for p in chat_passengers:
                    meal = p.get("meal_preference", "none")
                    meal_label = {"veg": "🥗 Veg", "non_veg": "🍖 Non-Veg", "jain": "🌿 Jain", "none": "—"}.get(meal, "—")
                    pax_lines.append(f"  • {p['full_name']} ({p.get('age', '?')} yrs, {p.get('gender', '?')}) — Meal: {meal_label}")

                # Build cost breakdown
                cost_lines = [f"  • Base fare: ₹{result.get('base_fare', total):,}"]
                if result.get("baggage_cost", 0) > 0:
                    cost_lines.append(f"  • Extra baggage (+{result.get('extra_baggage_kg', 0)} kg): ₹{result['baggage_cost']:,}")
                if result.get("insurance_cost", 0) > 0:
                    cost_lines.append(f"  • Travel insurance: ₹{result['insurance_cost']:,}")
                if discount > 0:
                    cost_lines.append(f"  • Coupon discount: -₹{discount:,}")
                cost_lines.append(f"  • **Total: ₹{total:,}**")

                state["response"] = (
                    f"✅ **Booking Created!**\n\n"
                    f"🎫 PNR: **{result['pnr']}**\n"
                    f"✈️ Flight: {selected['flight_number']} — {selected['departure_airport_city']} → {selected['arrival_airport_city']}\n"
                    f"👥 Passengers:\n" + "\n".join(pax_lines) + "\n\n"
                    f"🧳 **Baggage:** {selected.get('cabin_baggage_kg', 7)} kg cabin + {selected.get('checked_baggage_kg', 15)} kg checked"
                    + (f" + {state.get('chat_extra_baggage', 0)} kg extra" if state.get("chat_extra_baggage", 0) > 0 else "")
                    + f"\n\n"
                    f"💰 **Cost Breakdown:**\n" + "\n".join(cost_lines) + "\n\n"
                    f"Would you like to **pay now**? Reply 'pay' to proceed or 'cancel' to abort."
                )
                state["response_metadata"] = {"quick_replies": ["Pay now", "Cancel"]}
                return state
            else:
                state["response"] = "I'm having trouble accessing the database. Please try again."
                state["flow_step"] = None
                return state

    # ── Handle passenger details (form-based) ──────────────────────────────
    # This step triggers the ixigo-style booking form on the frontend.
    if flow_step == "passenger_details":
        selected = state.get("selected_flight")
        if not selected:
            state["response"] = "Something went wrong — please search for flights again."
            state["flow_step"] = None
            return state

        passengers = int(entities.get("passengers", 1))
        state["response"] = (
            f"✈️ **Selected: {selected['flight_number']} — {selected['departure_airport_city']} → {selected['arrival_airport_city']}**\n"
            f"🕐 {datetime.fromisoformat(selected['departure_time']).strftime('%H:%M')} → {datetime.fromisoformat(selected['arrival_time']).strftime('%H:%M')}\n"
            f"💰 ₹{selected['price']:,} per passenger\n\n"
            f"📝 Please fill in the **passenger details form** below to proceed with your booking."
        )
        state["response_metadata"] = {
            "show_booking_form": True,
            "flight_info": selected,
            "passenger_count": passengers,
            "quick_replies": [],
        }
        return state

    # ── Handle payment confirmation ────────────────────────────────────────
    if flow_step == "payment":
        booking_result = state.get("booking_result", {})
        pnr = booking_result.get("pnr", "")
        selected = state.get("selected_flight", {})
        passengers = int(entities.get("passengers", 1))
        total_price = booking_result.get("total_amount", selected.get("price", 0) * passengers)

        # __payment_completed__ is sent by the frontend after the payment gateway
        # has already initiated and confirmed the payment. We just need to send
        # the confirmation email and reset the flow.
        if msg_lower == "__payment_completed__":
            state["flow_step"] = None
            contact_email = booking_result.get("contact_email", "")

            # Send confirmation email
            try:
                from services.email_service import send_booking_confirmation
                user_email = contact_email or "guest@skybook.ai"
                dep_time = datetime.fromisoformat(selected["departure_time"]).strftime("%B %d, %Y at %H:%M")
                arr_time = datetime.fromisoformat(selected["arrival_time"]).strftime("%B %d, %Y at %H:%M")
                route = f"{selected.get('departure_airport_city', 'Unknown')} → {selected.get('arrival_airport_city', 'Unknown')}"
                send_booking_confirmation(
                    to_email=user_email,
                    pnr=pnr,
                    flight_number=selected.get("flight_number", ""),
                    route=route,
                    departure_time=dep_time,
                    passenger_name=booking_result.get("passenger_name", "Guest"),
                    total_amount=booking_result.get("total_amount", total_price),
                    airline_name=selected.get("airline_name", "SkyBook Airlines"),
                    departure_city=selected.get("departure_airport_city", ""),
                    departure_code=selected.get("departure_airport_code", ""),
                    arrival_city=selected.get("arrival_airport_city", ""),
                    arrival_code=selected.get("arrival_airport_code", ""),
                    arrival_time=arr_time,
                    duration_minutes=selected.get("duration_minutes", 0),
                    cabin_class=selected.get("cabin_class", "Economy"),
                )
            except Exception as e:
                print(f"⚠️  Email send error: {e}")

            # Send confirmation SMS
            try:
                from services.sms_service import send_booking_confirmation_sms
                contact_phone = booking_result.get("contact_phone", "")
                if contact_phone:
                    send_booking_confirmation_sms(
                        to_phone=contact_phone,
                        pnr=pnr,
                        flight_number=selected.get("flight_number", ""),
                        departure_city=selected.get("departure_airport_city", ""),
                        arrival_city=selected.get("arrival_airport_city", ""),
                        departure_time=dep_time,
                    )
            except Exception as e:
                print(f"⚠️  SMS send error: {e}")

            state["response"] = ""
            state["response_metadata"] = {"quick_replies": []}
            return state

        elif "pay" in msg_lower or "yes" in msg_lower or "confirm" in msg_lower:
            if db and booking_result:
                booking_id = booking_result.get("booking_id", "")
                pay_result = tools.initiate_payment(db, booking_id, "card")
                if "error" in pay_result:
                    state["response"] = f"❌ {pay_result['error']}"
                    return state

                # Confirm payment automatically for demo
                confirm_result = tools.confirm_payment(db, pay_result.get("transaction_id", ""), "success")
                if "error" in confirm_result:
                    state["response"] = f"❌ {confirm_result['error']}"
                    return state

                state["flow_step"] = None
                contact_email = booking_result.get("contact_email", "")
                state["response"] = (
                    f"✅ **Payment Successful! Booking Confirmed**\n\n"
                    f"PNR: **{pnr}**\n"
                    f"Amount Paid: ₹{total_price:,}\n"
                    f"Payment Method: Card\n"
                    f"Status: Confirmed ✅\n\n"
                    f"📧 A confirmation email has been sent to **{contact_email}**.\n"
                    f"🎫 You can check-in online 24 hours before departure.\n\n"
                    f"Is there anything else I can help you with?"
                )
                state["response_metadata"] = {
                    "quick_replies": ["Web check-in", "Check flight status", "Book another flight"],
                }

                # Send confirmation email
                try:
                    from services.email_service import send_booking_confirmation
                    # Use the email collected during booking flow; fall back to user's account email
                    user_email = booking_result.get("contact_email")
                    if not user_email:
                        user_id = state.get("user_id")
                        if user_id and db:
                            user = db.query(models.User).filter(models.User.id == user_id).first()
                            if user:
                                user_email = user.email
                    if not user_email:
                        user_email = "guest@skybook.ai"

                    dep_time = datetime.fromisoformat(selected["departure_time"]).strftime("%B %d, %Y at %H:%M")
                    arr_time = datetime.fromisoformat(selected["arrival_time"]).strftime("%B %d, %Y at %H:%M")
                    route = f"{selected.get('departure_airport_city', 'Unknown')} → {selected.get('arrival_airport_city', 'Unknown')}"
                    send_booking_confirmation(
                        to_email=user_email,
                        pnr=pnr,
                        flight_number=selected.get("flight_number", ""),
                        route=route,
                        departure_time=dep_time,
                        passenger_name=booking_result.get("passenger_name", "Guest"),
                        total_amount=total_price,
                        airline_name=selected.get("airline_name", "SkyBook Airlines"),
                        departure_city=selected.get("departure_airport_city", ""),
                        departure_code=selected.get("departure_airport_code", ""),
                        arrival_city=selected.get("arrival_airport_city", ""),
                        arrival_code=selected.get("arrival_airport_code", ""),
                        arrival_time=arr_time,
                        duration_minutes=selected.get("duration_minutes", 0),
                        cabin_class=selected.get("cabin_class", "Economy"),
                    )
                except Exception as e:
                    print(f"⚠️  Email send error: {e}")

                # Send confirmation SMS
                try:
                    from services.sms_service import send_booking_confirmation_sms
                    contact_phone = booking_result.get("contact_phone", "")
                    if contact_phone:
                        send_booking_confirmation_sms(
                            to_phone=contact_phone,
                            pnr=pnr,
                            flight_number=selected.get("flight_number", ""),
                            departure_city=selected.get("departure_airport_city", ""),
                            arrival_city=selected.get("arrival_airport_city", ""),
                            departure_time=dep_time,
                        )
                except Exception as e:
                    print(f"⚠️  SMS send error: {e}")

                return state
        elif "cancel" in msg_lower or "no" in msg_lower or "abort" in msg_lower:
            if db and pnr:
                tools.cancel_booking(db, pnr)
            state["flow_step"] = None
            state["response"] = (
                "❌ Booking cancelled. Your flight was not booked and no payment was charged.\n\n"
                "Would you like to search for a different flight?"
            )
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Check flight status"]}
            return state
        else:
            state["response"] = (
                "Please click **Pay now** to proceed to the payment gateway or **Cancel** to abort the booking."
            )
            state["response_metadata"] = {"quick_replies": ["Pay now", "Cancel"]}
            return state

    # Determine what's missing
    required = ["trip_type", "departure_city", "arrival_city", "departure_date"]

    missing = [k for k in required if not entities.get(k)]

    # If round-trip, return_date is also required
    if entities.get("trip_type") == "round_trip" and not entities.get("return_date"):
        missing.append("return_date")

    if not entities.get("passengers"):
        missing.append("passengers")

    if missing:
        # Ask for the first missing piece
        next_needed = missing[0]
        prompts_map = {
            "trip_type": "✈️ Is this a **one-way** or **round-trip** flight?",
            "departure_city": "✈️ From which city would you like to depart?\n\n*Available cities: Bangalore, Chennai, Mumbai, Delhi, Hyderabad, Kolkata, Goa, Kochi, Jaipur, Ahmedabad, Coimbatore, Pune, Thiruvananthapuram*",
            "arrival_city": "📍 What is your destination city?\n\n*Available cities: Bangalore, Chennai, Mumbai, Delhi, Hyderabad, Kolkata, Goa, Kochi, Jaipur, Ahmedabad, Coimbatore, Pune, Thiruvananthapuram*",
            "departure_date": "📅 What date would you like to travel? (e.g., 2025-01-15 or 'tomorrow')",
            "return_date": "🔁 What date would you like to return? (e.g., 2025-01-20 or 'tomorrow')",
            "passengers": "👥 How many passengers will be traveling?",
        }
        state["response"] = prompts_map.get(next_needed, "Could you provide more details?")
        state["flow_step"] = f"collect_{next_needed}"
        state["response_metadata"] = {
            "quick_replies": ["One-way", "Round-trip"] if next_needed == "trip_type" else (["Tomorrow", "Day after tomorrow"] if next_needed in ("departure_date", "return_date") else []),
            "show_date_picker": next_needed in ("departure_date", "return_date"),
        }
        return state

    # All required info available — search flights
    try:
        travel_date = date.fromisoformat(entities["departure_date"])
    except (ValueError, KeyError):
        state["response"] = "I couldn't parse the travel date. Please provide it in YYYY-MM-DD format (e.g., 2025-01-15)."
        return state

    passengers = int(entities.get("passengers", 1))
    cabin_class = entities.get("cabin_class", "economy")
    return_date = None
    if entities.get("return_date"):
        try:
            return_date = date.fromisoformat(entities["return_date"])
        except ValueError:
            pass

    if db:
        results = tools.search_flights(
            db=db,
            departure_city=entities["departure_city"],
            arrival_city=entities["arrival_city"],
            travel_date=travel_date,
            passengers=passengers,
            cabin_class=cabin_class,
            return_date=return_date,
        )

        if isinstance(results, dict) and "error" in results:
            state["response"] = f"❌ {results['error']}"
            return state

        outbound = results.get("outbound_flights", [])
        if not outbound:
            state["flow_step"] = "no_flights"
            # Build available routes list
            routes_text = ""
            if db:
                try:
                    routes = tools.get_available_routes(db)
                    if routes:
                        from collections import defaultdict
                        route_map = defaultdict(list)
                        for dep, arr in routes:
                            route_map[dep].append(arr)
                        route_lines = []
                        for dep in sorted(route_map.keys()):
                            route_lines.append(f"  **{dep}** → {', '.join(route_map[dep])}")
                        routes_text = "\n\n🗺️ **Available routes:**\n" + "\n".join(route_lines)
                except Exception:
                    pass

            state["response"] = (
                f"😔 No flights found from {entities['departure_city']} to {entities['arrival_city']} "
                f"on {travel_date.strftime('%B %d, %Y')}.\n\n"
                f"Would you like to:\n"
                f"1️⃣ Try a **different date**\n"
                f"2️⃣ Try a **different route** (different cities)\n"
                f"3️⃣ **Cancel** and start over\n\n"
                f"Just reply with a date, new cities, or 'cancel'."
                f"{routes_text}"
            )
            state["response_metadata"] = {
                "quick_replies": ["Try tomorrow", "Try different cities", "Cancel"],
            }
            return state

        # Store search results
        state["search_results"] = outbound
        state["flow_step"] = "select_flight"

        # Format flight results
        flight_lines = []
        for i, f in enumerate(outbound, 1):
            dep_time = datetime.fromisoformat(f["departure_time"]).strftime("%H:%M")
            arr_time = datetime.fromisoformat(f["arrival_time"]).strftime("%H:%M")
            duration_h = f["duration_minutes"] // 60
            duration_m = f["duration_minutes"] % 60
            flight_lines.append(
                f"**{i}.** ✈️ {f['flight_number']} ({f['airline_name']})\n"
                f"   🕐 {dep_time} → {arr_time} ({duration_h}h {duration_m}m)\n"
                f"   💰 ₹{f['price']:,} per passenger ({f['cabin_class']})\n"
                f"   💺 {f['available_seats']} seats available"
            )

        response = (
            f"🔍 Found {len(outbound)} flight(s) from {results['departure_city']} "
            f"to {results['arrival_city']} on {travel_date.strftime('%B %d, %Y')}:\n\n"
            + "\n\n".join(flight_lines)
            + "\n\nWhich flight would you like to book? Reply with the **number** (e.g., '1')."
        )

        if return_date and results.get("return_flights"):
            ret_flights = results["return_flights"]
            state["search_results"] = {"outbound": outbound, "return": ret_flights}
            ret_lines = []
            for i, f in enumerate(ret_flights, 1):
                dep_time = datetime.fromisoformat(f["departure_time"]).strftime("%H:%M")
                arr_time = datetime.fromisoformat(f["arrival_time"]).strftime("%H:%M")
                ret_lines.append(f"**{i}.** {f['flight_number']} — {dep_time}→{arr_time} — ₹{f['price']:,}")
            response += f"\n\n🔁 **Return flights** ({return_date.strftime('%B %d, %Y')}):\n" + "\n".join(ret_lines)

        state["response"] = response
        state["response_metadata"] = {
            "flight_cards": outbound,
            "quick_replies": [str(i + 1) for i in range(len(outbound))],
        }
    else:
        state["response"] = "I'm having trouble accessing the flight database. Please try again."

    return state


# ── Flight Status Node ─────────────────────────────────────────────────────

def handle_flight_status(state: ChatState) -> ChatState:
    """Handle flight status check."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    flight_number = entities.get("flight_number")

    if not flight_number:
        state["response"] = "✈️ Please provide the flight number you'd like to check. (e.g., 'SB101' or 'AI234')"
        state["flow_step"] = "collect_flight_number"
        return state

    if db:
        result = tools.get_flight_status(db, flight_number)
        if "error" in result:
            state["response"] = f"❌ {result['error']}"
        else:
            dep_time = datetime.fromisoformat(result["departure_time"]).strftime("%B %d, %Y at %H:%M")
            arr_time = datetime.fromisoformat(result["arrival_time"]).strftime("%H:%M")
            status_emoji = {"scheduled": "📅", "boarding": "🚪", "departed": "✈️", "arrived": "🏁", "delayed": "⏰", "cancelled": "❌"}
            state["response"] = (
                f"📊 **Flight Status: {result['flight_number']}**\n\n"
                f"Airline: {result['airline_name']}\n"
                f"Route: {result['departure_city']} → {result['arrival_city']}\n"
                f"Departure: {dep_time}\n"
                f"Arrival: {arr_time}\n"
                f"Status: {status_emoji.get(result['status'], '📋')} **{result['status'].upper()}**\n"
            )
            if result.get("delay_minutes"):
                state["response"] += f"⏰ Delayed by {result['delay_minutes']} minutes\n"
            if result.get("gate"):
                state["response"] += f"🚪 Gate: {result['gate']}\n"
    else:
        state["response"] = "Unable to access flight data right now."

    state["flow_step"] = None
    state["entities"] = {}
    return state


# ── Cancel Booking Node ────────────────────────────────────────────────────

def handle_cancel_booking(state: ChatState) -> ChatState:
    """Handle booking cancellation."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    booking_id = entities.get("booking_id")
    flow_step = state.get("flow_step", "")

    # If we asked for PNR, extract it from user's message
    if flow_step == "collect_pnr_cancel" and not booking_id:
        last_message = state["messages"][-1].content if state["messages"] else ""
        pnr_match = re.search(r'\b([A-Z0-9]{6})\b', last_message.upper())
        if pnr_match:
            candidate = pnr_match.group(1)
            if any(c.isdigit() for c in candidate) and candidate not in ["PLEASE", "THANK"]:
                booking_id = candidate
                entities["booking_id"] = booking_id
                state["entities"] = entities
                flow_step = None  # Fall through to confirmation below
        else:
            state["response"] = "I couldn't find a valid PNR. Please provide your 6-character booking reference (e.g., 'ABC123')."
            state["flow_step"] = "collect_pnr_cancel"
            return state

    if not booking_id and flow_step != "confirm_cancel":
        state["response"] = "Please provide your booking PNR to cancel. (e.g., 'Cancel booking ABC123')"
        state["flow_step"] = "collect_pnr_cancel"
        return state

    if flow_step != "confirm_cancel" and booking_id:
        # Show booking details and ask for confirmation
        if db:
            booking = tools.get_booking_by_pnr(db, booking_id)
            if not booking:
                state["response"] = f"❌ No booking found with PNR: {booking_id}"
                return state
            state["response"] = (
                f"🎫 **Booking Details:**\n"
                f"PNR: {booking['pnr']}\n"
                f"Flight: {booking['flight_number']} — {booking['departure_city']} → {booking['arrival_city']}\n"
                f"Date: {datetime.fromisoformat(booking['departure_time']).strftime('%B %d, %Y')}\n"
                f"Amount: ₹{booking['total_amount']:,}\n"
                f"Status: {booking['booking_status']}\n\n"
                f"⚠️ Are you sure you want to cancel this booking? A cancellation fee may apply.\n"
                f"Reply **'Yes, cancel'** to confirm or **'No'** to keep the booking."
            )
            state["flow_step"] = "confirm_cancel"
            state["response_metadata"] = {"quick_replies": ["Yes, cancel", "No, keep it"]}
        return state

    # Check confirmation
    last_msg = state["messages"][-1].content.lower() if state["messages"] else ""
    if "yes" in last_msg or "confirm" in last_msg:
        if db and booking_id:
            result = tools.cancel_booking(db, booking_id)
            if "error" in result:
                state["response"] = f"❌ {result['error']}"
            else:
                state["response"] = (
                    f"✅ **Booking Cancelled Successfully!**\n\n"
                    f"PNR: {result['pnr']}\n"
                    f"Cancellation Fee: ₹{result['cancellation_fee']}\n"
                    f"Refund Amount: ₹{result['refund_amount']}\n"
                    f"Refund Status: {result['refund_status']}\n\n"
                    f"💰 Your refund will be processed in 5-7 business days."
                )
                # Send notification
                tools.send_notification(
                    db=db, recipient="user@example.com",
                    subject=f"Booking {result['pnr']} Cancelled",
                    body=f"Your booking {result['pnr']} has been cancelled. Refund of ₹{result['refund_amount']} will be processed in 5-7 business days.",
                    notification_type="email",
                )
        state["flow_step"] = None
    else:
        state["response"] = "👍 Your booking has not been cancelled. Is there anything else I can help with?"
        state["flow_step"] = None

    return state


# ── Modify Booking Node ────────────────────────────────────────────────────

def _complete_add_passenger(state: ChatState, db: Session, booking_id: str, seat_number: str = None) -> None:
    """Complete the add-passenger flow by calling modify_booking."""
    pax_data = {
        "full_name": state.get("new_passenger_name", "Passenger"),
        "age": state.get("new_passenger_age"),
        "gender": state.get("new_passenger_gender"),
    }
    if seat_number:
        pax_data["seat_number"] = seat_number

    result = tools.modify_booking(db, booking_id, add_passengers=[pax_data])
    if "error" in result:
        state["response"] = f"❌ {result['error']}"
    else:
        seat_info = f" with seat {seat_number}" if seat_number else ""
        state["response"] = (
            f"✅ **Passenger {pax_data['full_name']} added** to PNR {booking_id}{seat_info}.\n"
            f"Modification fee of ₹{result.get('modification_fee', 500)} has been applied.\n"
            f"New total: ₹{result.get('new_total', 0):,}"
        )
    state["flow_step"] = None
    # Clean up temp state
    state.pop("new_passenger_name", None)
    state.pop("new_passenger_age", None)
    state.pop("new_passenger_gender", None)


def handle_modify_booking(state: ChatState) -> ChatState:
    """Handle booking modification."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    booking_id = entities.get("booking_id")
    flow_step = state.get("flow_step", "")
    last_message = state["messages"][-1].content if state["messages"] else ""
    msg_lower = last_message.lower().strip()

    # If we asked for PNR, extract it from user's message
    if flow_step == "collect_pnr_modify" and not booking_id:
        pnr_match = re.search(r'\b([A-Z0-9]{6})\b', last_message.upper())
        if pnr_match:
            candidate = pnr_match.group(1)
            if any(c.isdigit() for c in candidate) and candidate not in ["PLEASE", "THANK"]:
                booking_id = candidate
                entities["booking_id"] = booking_id
                state["entities"] = entities
                flow_step = None  # Fall through to showing booking details
        else:
            state["response"] = "I couldn't find a valid PNR. Please provide your 6-character booking reference (e.g., 'ABC123')."
            state["flow_step"] = "collect_pnr_modify"
            return state

    # Handle modification choice
    if flow_step == "awaiting_modification_choice":
        if "cancel" in msg_lower or "no" in msg_lower or "stop" in msg_lower:
            state["flow_step"] = None
            state["response"] = "👍 Modification cancelled. Is there anything else I can help you with?"
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Check flight status"]}
            return state
        elif "seat" in msg_lower:
            if db and booking_id:
                booking = tools.get_booking_by_pnr(db, booking_id)
                if not booking:
                    state["response"] = f"❌ No booking found with PNR: {booking_id}"
                    state["flow_step"] = None
                    return state
                seats = tools.get_seat_map(db, booking["flight_id"], booking.get("cabin_class"))
                available = [s["seat_number"] for s in seats if not s.get("is_occupied", False)]
                state["response"] = (
                    f"💺 **Available seats for {booking_id}** ({booking.get('cabin_class', 'economy')} class):\n\n"
                    f"{', '.join(available[:20])}\n\n"
                    f"Reply with the seat number you'd like (e.g., '12A')."
                )
                state["flow_step"] = "collect_new_seat"
                state["response_metadata"] = {"quick_replies": available[:6]}
            return state
        elif "passenger" in msg_lower or "add pax" in msg_lower or "extra passenger" in msg_lower or "add person" in msg_lower:
            state["flow_step"] = "collect_add_passenger_name"
            state["response"] = "👤 What is the **full name** of the passenger you'd like to add?"
            state["response_metadata"] = {"quick_replies": []}
            return state
        elif "flight" in msg_lower or "date" in msg_lower or "reschedule" in msg_lower:
            state["flow_step"] = "collect_new_date"
            state["response"] = "📅 What new date would you like to travel? (e.g., '2025-08-20' or 'tomorrow')"
            state["response_metadata"] = {"quick_replies": ["Tomorrow", "Day after tomorrow"], "show_date_picker": True}
            return state
        else:
            state["response"] = (
                "I didn't catch that. Would you like to:\n"
                "• **Change flight** — search for alternative dates\n"
                "• **Change seat** — view available seats\n"
                "• **Add passenger** — add an extra passenger\n"
                "• **Cancel modification**"
            )
            state["response_metadata"] = {"quick_replies": ["Change flight", "Change seat", "Add passenger", "Cancel modification"]}
            return state

    # Handle new seat selection
    if flow_step == "collect_new_seat":
        seat_match = re.search(r'\b(\d{1,2}[A-F])\b', last_message.upper())
        if seat_match and db and booking_id:
            new_seat = seat_match.group(1)
            result = tools.modify_booking(db, booking_id, new_seat_numbers=[new_seat])
            if "error" in result:
                state["response"] = f"❌ {result['error']}"
            else:
                state["response"] = f"✅ **Seat updated to {new_seat}** for PNR {booking_id}. Modification fee of ₹500 has been applied."
            state["flow_step"] = None
        else:
            state["response"] = "Please provide a valid seat number (e.g., '12A')."
            state["flow_step"] = "collect_new_seat"
        return state

    # ── Add passenger flow ─────────────────────────────────────────────
    if flow_step == "collect_add_passenger_name":
        # Store the name and ask for age
        state["new_passenger_name"] = last_message.strip()
        state["flow_step"] = "collect_add_passenger_age"
        state["response"] = f"📅 What is **{last_message.strip()}'s** age?"
        return state

    if flow_step == "collect_add_passenger_age":
        age_match = re.search(r'\b(\d{1,3})\b', last_message)
        if age_match:
            age = int(age_match.group(1))
            if age > 120:
                state["response"] = "Please provide a valid age (1-120)."
                return state
            state["new_passenger_age"] = age
            state["flow_step"] = "collect_add_passenger_gender"
            state["response"] = f"👤 What is **{state.get('new_passenger_name', 'the passenger')}'s** gender? (Male/Female/Other)"
            state["response_metadata"] = {"quick_replies": ["Male", "Female", "Other"]}
            return state
        else:
            state["response"] = "Please provide a valid age (e.g., '25')."
            return state

    if flow_step == "collect_add_passenger_gender":
        gender = None
        if "male" in msg_lower:
            gender = "Male"
        elif "female" in msg_lower:
            gender = "Female"
        elif "other" in msg_lower:
            gender = "Other"
        if gender:
            state["new_passenger_gender"] = gender
            # Ask if they want to select a seat for the new passenger
            if db and booking_id:
                booking = tools.get_booking_by_pnr(db, booking_id)
                if booking:
                    seats = tools.get_seat_map(db, booking["flight_id"], booking.get("cabin_class"))
                    available = [s["seat_number"] for s in seats if not s.get("is_occupied", False)]
                    if available:
                        state["flow_step"] = "collect_add_passenger_seat"
                        state["response"] = (
                            f"💺 **Available seats** ({len(available)} free):\n"
                            f"{', '.join(available[:20])}\n\n"
                            f"Would you like to assign a seat to **{state.get('new_passenger_name', 'the new passenger')}**? "
                            f"Reply with a seat number or 'skip'."
                        )
                        state["response_metadata"] = {"quick_replies": available[:6] + ["Skip"]}
                        return state
            # No seats to choose — proceed directly
            _complete_add_passenger(state, db, booking_id)
            return state
        else:
            state["response"] = "Please reply with Male, Female, or Other."
            state["response_metadata"] = {"quick_replies": ["Male", "Female", "Other"]}
            return state

    if flow_step == "collect_add_passenger_seat":
        seat_number = None
        if "skip" not in msg_lower:
            seat_match = re.search(r'\b(\d{1,2}[A-F])\b', last_message.upper())
            if seat_match:
                seat_number = seat_match.group(1)
        _complete_add_passenger(state, db, booking_id, seat_number)
        return state

    # Handle new date for flight change
    if flow_step == "collect_new_date":
        new_date = None
        if "tomorrow" in msg_lower:
            new_date = (date.today() + timedelta(days=1)).isoformat()
        elif "today" in msg_lower:
            new_date = date.today().isoformat()
        else:
            date_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', last_message)
            if date_match:
                new_date = date_match.group(1)
            else:
                date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', last_message)
                if date_match:
                    d, m, y = date_match.groups()
                    new_date = f"{y}-{int(m):02d}-{int(d):02d}"

        if new_date and db and booking_id:
            # Get current booking to find route
            booking = tools.get_booking_by_pnr(db, booking_id)
            if not booking:
                state["response"] = f"❌ No booking found with PNR: {booking_id}"
                state["flow_step"] = None
                return state

            # Search for flights on the new date for the same route
            try:
                travel_date_obj = date.fromisoformat(new_date)
            except ValueError:
                state["response"] = "I couldn't parse that date. Please use YYYY-MM-DD format."
                state["flow_step"] = "collect_new_date"
                return state

            results = tools.search_flights(
                db=db,
                departure_city=booking["departure_city"],
                arrival_city=booking["arrival_city"],
                travel_date=travel_date_obj,
                passengers=booking["passenger_count"],
                cabin_class=booking.get("cabin_class", "economy"),
            )

            if isinstance(results, dict) and "error" in results:
                state["response"] = f"❌ {results['error']}"
                state["flow_step"] = None
                return state

            outbound = results.get("outbound_flights", [])
            if not outbound:
                state["response"] = (
                    f"😔 No flights found from {booking['departure_city']} to {booking['arrival_city']} "
                    f"on {travel_date_obj.strftime('%B %d, %Y')}. Try a different date."
                )
                state["response_metadata"] = {"quick_replies": ["Tomorrow", "Try another date", "Cancel"]}
                return state

            # Show available flights for new date
            flight_lines = []
            for i, f in enumerate(outbound, 1):
                dep_time = datetime.fromisoformat(f["departure_time"]).strftime("%H:%M")
                arr_time = datetime.fromisoformat(f["arrival_time"]).strftime("%H:%M")
                flight_lines.append(
                    f"**{i}.** ✈️ {f['flight_number']} — {dep_time}→{arr_time} — ₹{f['price']:,}"
                )
            state["response"] = (
                f"🔍 Flights on {travel_date_obj.strftime('%B %d, %Y')}:\n\n"
                + "\n".join(flight_lines)
                + "\n\nReply with the **number** of the flight you'd like to switch to."
            )
            state["response_metadata"] = {
                "flight_cards": outbound,
                "quick_replies": [str(i + 1) for i in range(len(outbound))],
            }
            state["flow_step"] = "select_replacement_flight"
            state["search_results"] = outbound
        else:
            state["response"] = "Please provide a valid date (e.g., '2025-08-20' or 'tomorrow')."
            state["flow_step"] = "collect_new_date"
        return state

    # Handle selection of replacement flight for modification
    if flow_step == "select_replacement_flight":
        selected_idx = None
        if msg_lower.isdigit():
            selected_idx = int(msg_lower) - 1
        else:
            flight_match = re.search(r'\b([A-Z]{2}\d{2,4})\b', last_message.upper())
            if flight_match:
                fn = flight_match.group(1)
                search_results = state.get("search_results", [])
                if isinstance(search_results, list):
                    for i, f in enumerate(search_results):
                        if f["flight_number"].upper() == fn:
                            selected_idx = i
                            break

        if selected_idx is not None and db and booking_id:
            search_results = state.get("search_results", [])
            if isinstance(search_results, list) and 0 <= selected_idx < len(search_results):
                selected = search_results[selected_idx]
                result = tools.modify_booking(db, booking_id, new_flight_id=selected["id"])
                if "error" in result:
                    state["response"] = f"❌ {result['error']}"
                else:
                    state["response"] = (
                        f"✅ **Flight changed to {selected['flight_number']}** for PNR {booking_id}.\n"
                        f"Modification fee of ₹500 has been applied."
                    )
                state["flow_step"] = None
                state["search_results"] = None
                return state

        state["response"] = "Please reply with a valid flight number to switch to, or type 'cancel' to abort."
        state["response_metadata"] = {"quick_replies": ["Cancel"]}
        return state

    if not booking_id:
        state["response"] = "Please provide your booking PNR to modify. (e.g., 'Modify booking ABC123')"
        state["flow_step"] = "collect_pnr_modify"
        return state

    if db:
        booking = tools.get_booking_by_pnr(db, booking_id)
        if not booking:
            state["response"] = f"❌ No booking found with PNR: {booking_id}"
            return state

        dep_time = datetime.fromisoformat(booking["departure_time"]).strftime("%B %d, %Y at %H:%M")
        state["response"] = (
            f"🎫 **Current Booking:**\n"
            f"PNR: {booking['pnr']}\n"
            f"Flight: {booking['flight_number']} — {booking['departure_city']} → {booking['arrival_city']}\n"
            f"Date: {dep_time}\n"
            f"Passengers: {booking['passenger_count']}\n"
            f"Seats: {', '.join(p['seat_number'] or 'Not selected' for p in booking['passengers'])}\n\n"
            f"What would you like to change?\n"
            f"• **Flight date** — I can search for alternative flights\n"
            f"• **Seat** — I can show available seats\n"
            f"• **Add passenger** — add an extra passenger to this booking\n\n"
            f"A modification fee of ₹500 will apply."
        )
        state["flow_step"] = "awaiting_modification_choice"
        state["response_metadata"] = {"quick_replies": ["Change flight", "Change seat", "Add passenger", "Cancel modification"]}
    return state


# ── Refund Node ────────────────────────────────────────────────────────────

def handle_refund(state: ChatState) -> ChatState:
    """Handle refund status check."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    last_message = state["messages"][-1].content if state["messages"] else ""

    # Check if the user explicitly typed a PNR-like string
    explicit_pnr = None
    pnr_match = re.search(r'\b([A-Z0-9]{6})\b', last_message.upper())
    if pnr_match:
        candidate = pnr_match.group(1)
        if any(c.isdigit() for c in candidate) and candidate not in ["PLEASE", "THANK"]:
            explicit_pnr = candidate

    # Priority: explicit PNR > booking_result PNR > entity-extracted booking_id
    booking_result = state.get("booking_result", {})
    if explicit_pnr:
        booking_id = explicit_pnr
    elif booking_result and booking_result.get("pnr"):
        booking_id = booking_result["pnr"]
    else:
        booking_id = entities.get("booking_id")

    if not booking_id:
        state["response"] = "Please provide your booking PNR to check refund status. (e.g., 'Refund for ABC123')"
        return state

    if db:
        result = tools.get_refund_status(db, booking_id)
        if "error" in result:
            state["response"] = f"❌ {result['error']}"
        elif "message" in result:
            state["response"] = result["message"]
        else:
            lines = [f"💰 **Refund Status for PNR: {result['pnr']}**\n"]
            lines.append(f"Booking Status: {result['booking_status']}\n")
            for r in result["refunds"]:
                lines.append(f"Refund Amount: ₹{r['amount']:,}")
                lines.append(f"Status: {r['status'].upper()}")
                lines.append(f"Reason: {r['reason']}")
                created = datetime.fromisoformat(r["created_at"]).strftime("%B %d, %Y") if r.get("created_at") else "N/A"
                lines.append(f"Requested: {created}")
            state["response"] = "\n".join(lines)
    return state


# ── Check-in Node ──────────────────────────────────────────────────────────

def handle_check_in(state: ChatState) -> ChatState:
    """Handle web check-in and boarding pass."""
    db: Session = state.get("db_session")
    entities = state.get("entities", {})
    flow_step = state.get("flow_step", "")
    last_message = state["messages"][-1].content if state["messages"] else ""
    msg_lower = last_message.lower().strip()

    # ── Handle seat selection during check-in ─────────────────────────────
    if flow_step == "check_in_select_seat":
        booking_id = state.get("check_in_pnr", "")
        seat_match = re.search(r'\b(\d{1,2}[A-F])\b', last_message.upper())
        if seat_match and db and booking_id:
            chosen_seat = seat_match.group(1)
            result = tools.web_check_in(db, booking_id, chosen_seat)
            if "error" in result:
                state["response"] = f"❌ {result['error']}"
                state["flow_step"] = None
            else:
                bp = result.get("boarding_pass", {})
                dep_time = datetime.fromisoformat(bp["departure_time"]).strftime("%B %d, %Y at %H:%M")
                board_time = datetime.fromisoformat(bp["boarding_time"]).strftime("%H:%M")
                state["response"] = (
                    f"✅ **{result['message']}**\n\n"
                    f"**Boarding Pass:**\n"
                    f"Passenger: {bp['passenger_name']}\n"
                    f"Flight: {bp['flight_number']} ({bp['airline_name']})\n"
                    f"Route: {bp['departure_city']} → {bp['arrival_city']}\n"
                    f"Date: {dep_time}\n"
                    f"Gate: {bp['gate']}\n"
                    f"Seat: {bp['seat']}\n"
                    f"Boarding Time: {board_time}\n\n"
                    f"📥 [Download Boarding Pass]({bp['boarding_pass_url']})"
                )
                state["response_metadata"] = {"boarding_pass": bp}
                state["flow_step"] = None
            return state
        elif "skip" in msg_lower or "no" in msg_lower or "any" in msg_lower or "auto" in msg_lower:
            # User wants auto seat assignment
            if db and booking_id:
                result = tools.web_check_in(db, booking_id, None)
                if "error" in result:
                    state["response"] = f"❌ {result['error']}"
                else:
                    bp = result.get("boarding_pass", {})
                    dep_time = datetime.fromisoformat(bp["departure_time"]).strftime("%B %d, %Y at %H:%M")
                    board_time = datetime.fromisoformat(bp["boarding_time"]).strftime("%H:%M")
                    state["response"] = (
                        f"✅ **{result['message']}**\n\n"
                        f"**Boarding Pass:**\n"
                        f"Passenger: {bp['passenger_name']}\n"
                        f"Flight: {bp['flight_number']} ({bp['airline_name']})\n"
                        f"Route: {bp['departure_city']} → {bp['arrival_city']}\n"
                        f"Date: {dep_time}\n"
                        f"Gate: {bp['gate']}\n"
                        f"Seat: {bp['seat']}\n"
                        f"Boarding Time: {board_time}\n\n"
                        f"📥 [Download Boarding Pass]({bp['boarding_pass_url']})"
                    )
                    state["response_metadata"] = {"boarding_pass": bp}
                state["flow_step"] = None
            return state
        else:
            state["response"] = (
                "Please reply with a **seat number** (e.g., '12A'), "
                "or type **'skip'** for auto seat assignment."
            )
            return state

    # ── Initial check-in request ──────────────────────────────────────────
    seat_number = entities.get("seat_number")

    # Check if the user explicitly typed a PNR-like string (6 alphanumeric chars with at least 1 digit)
    explicit_pnr = None
    pnr_match = re.search(r'\b([A-Z0-9]{6})\b', last_message.upper())
    if pnr_match:
        candidate = pnr_match.group(1)
        if any(c.isdigit() for c in candidate) and candidate not in ["PLEASE", "THANK"]:
            explicit_pnr = candidate

    # Priority: explicit PNR in message > PNR from recent booking > entity-extracted booking_id
    booking_result = state.get("booking_result", {})
    if explicit_pnr:
        booking_id = explicit_pnr
    elif booking_result and booking_result.get("pnr"):
        booking_id = booking_result["pnr"]
    else:
        booking_id = entities.get("booking_id")

    if not booking_id:
        state["response"] = "Please provide your booking PNR for web check-in. (e.g., 'Check-in for ABC123')"
        state["flow_step"] = "collect_check_in_pnr"
        return state

    if db:
        # Verify booking exists and is eligible for check-in
        booking = tools.get_booking_by_pnr(db, booking_id)
        if not booking:
            state["response"] = f"❌ No booking found with PNR: {booking_id}"
            return state
        if booking.get("booking_status") != "confirmed":
            state["response"] = f"❌ Booking {booking_id} is not confirmed. Cannot check in."
            return state
        if booking.get("check_in_status") != "not_checked_in":
            state["response"] = f"❌ Already checked in for PNR {booking_id}."
            return state

        # If user already specified a seat, proceed directly
        if seat_number:
            result = tools.web_check_in(db, booking_id, seat_number)
            if "error" in result:
                state["response"] = f"❌ {result['error']}"
            else:
                bp = result.get("boarding_pass", {})
                dep_time = datetime.fromisoformat(bp["departure_time"]).strftime("%B %d, %Y at %H:%M")
                board_time = datetime.fromisoformat(bp["boarding_time"]).strftime("%H:%M")
                state["response"] = (
                    f"✅ **{result['message']}**\n\n"
                    f"**Boarding Pass:**\n"
                    f"Passenger: {bp['passenger_name']}\n"
                    f"Flight: {bp['flight_number']} ({bp['airline_name']})\n"
                    f"Route: {bp['departure_city']} → {bp['arrival_city']}\n"
                    f"Date: {dep_time}\n"
                    f"Gate: {bp['gate']}\n"
                    f"Seat: {bp['seat']}\n"
                    f"Boarding Time: {board_time}\n\n"
                    f"📥 [Download Boarding Pass]({bp['boarding_pass_url']})"
                )
                state["response_metadata"] = {"boarding_pass": bp}
            return state

        # Show available seats and ask user to select
        seats = tools.get_seat_map(db, booking["flight_id"], booking.get("cabin_class"))
        available_seats = [s for s in seats if not s.get("is_occupied", False)]

        if available_seats:
            # Group seats by category for display
            window_seats = [s for s in available_seats if s.get("is_window")]
            aisle_seats = [s for s in available_seats if s.get("is_aisle")]
            extra_legroom = [s for s in available_seats if s.get("extra_legroom")]

            seat_list = []
            for s in available_seats[:20]:
                tags = []
                if s.get("is_window"):
                    tags.append("🪟 Window")
                if s.get("is_aisle"):
                    tags.append("🚶 Aisle")
                if s.get("extra_legroom"):
                    tags.append("🦵 Extra legroom")
                price_tag = f" (+₹{s['price']})" if s.get("price", 0) > 0 else ""
                tag_str = f" — {' | '.join(tags)}{price_tag}" if tags else price_tag
                seat_list.append(f"  **{s['seat_number']}**{tag_str}")

            state["check_in_pnr"] = booking_id
            state["flow_step"] = "check_in_select_seat"
            cabin_label = booking.get("cabin_class", "economy").replace("_", " ").title()
            state["response"] = (
                f"✈️ **Web Check-in for PNR {booking_id}**\n"
                f"Flight: {booking.get('flight_number', '')} — {booking.get('departure_city', '')} → {booking.get('arrival_city', '')}\n"
                f"Cabin: {cabin_label}\n\n"
                f"💺 **Available seats** ({len(available_seats)} free in {cabin_label}):\n\n"
                + "\n".join(seat_list)
                + f"\n\nReply with a **seat number** (e.g., '12A') to select your seat, "
                f"or type **'skip'** for auto seat assignment."
            )
            state["response_metadata"] = {
                "quick_replies": [s["seat_number"] for s in available_seats[:6]] + ["Skip"],
            }
        else:
            # No seats available — auto assign
            result = tools.web_check_in(db, booking_id, None)
            if "error" in result:
                state["response"] = f"❌ {result['error']}"
            else:
                bp = result.get("boarding_pass", {})
                dep_time = datetime.fromisoformat(bp["departure_time"]).strftime("%B %d, %Y at %H:%M")
                board_time = datetime.fromisoformat(bp["boarding_time"]).strftime("%H:%M")
                state["response"] = (
                    f"✅ **{result['message']}**\n\n"
                    f"**Boarding Pass:**\n"
                    f"Passenger: {bp['passenger_name']}\n"
                    f"Flight: {bp['flight_number']} ({bp['airline_name']})\n"
                    f"Route: {bp['departure_city']} → {bp['arrival_city']}\n"
                    f"Date: {dep_time}\n"
                    f"Gate: {bp['gate']}\n"
                    f"Seat: {bp['seat']}\n"
                    f"Boarding Time: {board_time}\n\n"
                    f"📥 [Download Boarding Pass]({bp['boarding_pass_url']})"
                )
                state["response_metadata"] = {"boarding_pass": bp}
    return state


# ── My Bookings Node ───────────────────────────────────────────────────────

def handle_my_bookings(state: ChatState) -> ChatState:
    """Show the user's bookings."""
    db: Session = state.get("db_session")
    user_id = state.get("user_id")
    flow_step = state.get("flow_step", "")
    last_message = state["messages"][-1].content if state["messages"] else ""
    msg_lower = last_message.lower().strip()

    # If we asked for email, extract it
    if flow_step == "collect_email_bookings":
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', msg_lower)
        if not email_match:
            state["response"] = "Please provide a valid email address (e.g., john@example.com)."
            state["flow_step"] = "collect_email_bookings"
            return state
        email = email_match.group()
        state["flow_step"] = None
        if db:
            bookings = tools.get_bookings_by_email(db, email)
            state["response"] = _format_bookings(bookings, email)
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Web check-in", "Cancel my booking"]}
        else:
            state["response"] = "Unable to access booking data right now."
        return state

    # Try user_id first (logged-in users)
    if user_id and db:
        bookings = tools.get_user_bookings(db, user_id)
        if bookings:
            state["response"] = _format_bookings(bookings)
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Web check-in", "Cancel my booking"]}
            return state
        # No bookings found for user_id — fall through to email

    # Try booking_result email (recent booking in this session)
    booking_result = state.get("booking_result", {})
    if booking_result and booking_result.get("contact_email") and db:
        email = booking_result["contact_email"]
        bookings = tools.get_bookings_by_email(db, email)
        if bookings:
            state["response"] = _format_bookings(bookings, email)
            state["response_metadata"] = {"quick_replies": ["Book a flight", "Web check-in", "Cancel my booking"]}
            return state

    # No user_id and no recent booking email — ask for email
    state["response"] = "📧 What email address did you use for your booking? I'll look up your reservations."
    state["flow_step"] = "collect_email_bookings"
    state["response_metadata"] = {"quick_replies": []}
    return state


def _format_bookings(bookings: list, email: str = None) -> str:
    """Format a list of booking dicts into a readable message."""
    if not bookings:
        prefix = f"No bookings found for **{email}**.\n\n" if email else ""
        return (
            f"{prefix}You don't have any bookings yet.\n\n"
            f"Would you like to **book a flight**?"
        )

    header = f"📋 **Your Bookings**{f' ({email})' if email else ''}\n\n"
    lines = []
    for i, b in enumerate(bookings, 1):
        dep_time = datetime.fromisoformat(b["departure_time"]).strftime("%b %d, %Y at %H:%M")
        status_emoji = {
            "confirmed": "✅", "pending": "⏳", "cancelled": "❌",
            "modified": "🔄", "refunded": "💸",
        }.get(b["booking_status"], "📋")
        lines.append(
            f"**{i}.** {status_emoji} PNR: **{b['pnr']}**\n"
            f"   ✈️ {b['flight_number']} — {b['departure_city']} → {b['arrival_city']}\n"
            f"   📅 {dep_time}\n"
            f"   💺 {b['passenger_count']} passenger(s) | {b['cabin_class'].replace('_', ' ').title()}\n"
            f"   💰 ₹{b['total_amount']:,.0f} | Status: **{b['booking_status'].title()}**"
        )
    return header + "\n\n".join(lines)


# ── Baggage Info Node ──────────────────────────────────────────────────────

def handle_baggage_info(state: ChatState) -> ChatState:
    """Handle baggage information request.

    Uses the selected flight's actual baggage allowance if available,
    or the booking's baggage info if a PNR was provided. Falls back
    to static data only if no flight/booking context exists.
    """
    entities = state.get("entities", {})
    cabin_class = entities.get("cabin_class", "economy")
    db = state.get("db_session")
    selected = state.get("selected_flight")

    # If user provided a PNR, look up their actual booking baggage info
    pnr = entities.get("booking_id")
    if pnr and db:
        booking = tools.get_booking_by_pnr(db, pnr)
        if booking:
            flight = db.query(models.Flight).filter(models.Flight.id == booking["flight_id"]).first()
            if flight:
                cabin_bg = flight.cabin_baggage_kg
                checked_bg = flight.checked_baggage_kg
                extra_bg = booking.get("extra_baggage_kg", 0)
                total_checked = checked_bg + extra_bg
                state["response"] = (
                    f"🧳 **Baggage Allowance for PNR {booking['pnr']}:**\n\n"
                    f"✈️ Flight: {booking['flight_number']} ({booking['cabin_class'].replace('_', ' ').title()})\n\n"
                    f"🎒 Cabin Baggage: {cabin_bg} kg\n"
                    f"📦 Checked Baggage: {checked_bg} kg"
                    + (f" + {extra_bg} kg extra = **{total_checked} kg total**" if extra_bg > 0 else "")
                    + f"\n\n"
                    f"💡 Excess baggage charges: ₹500/kg above the free allowance.\n"
                    f"Need more baggage? You can add it during booking or modification."
                )
                return state

    # If a flight is selected, use its actual baggage allowance
    if selected:
        cabin_bg = selected.get("cabin_baggage_kg", 7)
        checked_bg = selected.get("checked_baggage_kg", 15)
        extra_bg = state.get("chat_extra_baggage", 0)
        total_checked = checked_bg + extra_bg
        state["response"] = (
            f"🧳 **Baggage Allowance ({cabin_class.replace('_', ' ').title()} Class):**\n\n"
            f"✈️ Flight: {selected.get('flight_number', 'Selected Flight')}\n\n"
            f"🎒 Cabin Baggage: {cabin_bg} kg\n"
            f"📦 Checked Baggage: {checked_bg} kg"
            + (f" + {extra_bg} kg extra = **{total_checked} kg total**" if extra_bg > 0 else "")
            + f"\n\n"
            f"💡 Extra baggage options:\n"
            f"• +5 kg — ₹500\n"
            f"• +10 kg — ₹900\n"
            f"• +20 kg — ₹1,500\n\n"
            f"Excess baggage charges: ₹500/kg above the free allowance."
        )
        return state

    # Fallback: static baggage info
    info = tools.get_baggage_info(cabin_class)
    state["response"] = (
        f"🧳 **Baggage Allowance ({info['cabin_class'].replace('_', ' ').title()} Class):**\n\n"
        f"🎒 Cabin Baggage: {info['cabin_baggage_kg']} kg\n"
        f"📦 Checked Baggage: {info['checked_baggage_kg']} kg\n"
        f"💰 Extra Bag Fee: ₹{info['extra_bag_fee_per_kg']} per kg\n\n"
        f"📌 {info['note']}\n\n"
        f"💡 Extra baggage options:\n"
        f"• +5 kg — ₹500\n"
        f"• +10 kg — ₹900\n"
        f"• +20 kg — ₹1,500"
    )
    return state


# ── Fare Comparison Node ───────────────────────────────────────────────────

def handle_fare_comparison(state: ChatState) -> ChatState:
    """Handle fare comparison request."""
    search_results = state.get("search_results", [])

    if not search_results:
        state["response"] = (
            "To compare fares, please search for a flight first.\n"
            "Tell me your departure city, destination, and travel date."
        )
        return state

    # Handle round-trip results (stored as dict with 'outbound' key)
    if isinstance(search_results, dict):
        search_results = search_results.get("outbound", [])

    # Compare cabin class prices for the first flight
    if isinstance(search_results, list) and search_results:
        flight = search_results[0]
        state["response"] = (
            f"📊 **Fare Comparison for {flight['flight_number']}:**\n\n"
            f"• Economy: ₹{flight.get('price', 3000):,}\n"
            f"• Premium Economy: ₹{flight.get('price', 3000) * 2:,.0f}\n"
            f"• Business: ₹{flight.get('price', 3000) * 4:,.0f}\n"
            f"• First Class: ₹{flight.get('price', 3000) * 6.67:,.0f}\n\n"
            f"💡 **Best Value:** Economy offers the most affordable option.\n"
            f"Business class includes priority boarding, lounge access, and 35kg checked baggage."
        )
    return state


# ── Help Node ──────────────────────────────────────────────────────────────

def handle_help(state: ChatState) -> ChatState:
    """Handle help request."""
    state["response"] = (
        "🤖 **How I Can Help You:**\n\n"
        "✈️ **Book a Flight** — Say 'I need a flight from Bangalore to Delhi tomorrow'\n"
        "📊 **Check Flight Status** — Say 'Check SB101 status'\n"
        "🎫 **Cancel Booking** — Say 'Cancel my booking ABC123'\n"
        "🔄 **Modify Booking** — Say 'Change my flight ABC123'\n"
        "💰 **Refund Status** — Say 'Where is my refund for ABC123?'\n"
        "✅ **Web Check-in** — Say 'Check-in for ABC123'\n"
        "🧳 **Baggage Info** — Say 'What is the baggage allowance?'\n"
        "📊 **Compare Fares** — Say 'Compare fares for flights'\n"
        "👤 **Talk to Agent** — Say 'I want to talk to a human agent'\n\n"
        "What would you like to do?"
    )
    state["response_metadata"] = {
        "quick_replies": [
            "Book a flight", "Check flight status", "Cancel booking",
            "Web check-in", "Baggage info", "Talk to agent"
        ]
    }
    return state


# ── Human Agent Escalation Node ────────────────────────────────────────────

def handle_human_agent(state: ChatState) -> ChatState:
    """Handle escalation to human agent."""
    last_message = state["messages"][-1].content if state["messages"] else ""
    state["escalated"] = True

    try:
        llm = get_llm(temperature=0.5)
        prompt = ESCALATION_PROMPT.format(message=last_message)
        response = llm.invoke([HumanMessage(content=prompt)])
        state["response"] = response.content
    except Exception:
        state["response"] = (
            "🤝 I understand you'd like to speak with a human agent.\n\n"
            "📞 **Customer Support:** 1800-SKYBOOK (1800-759-2665)\n"
            "📧 **Email:** support@skybookairlines.com\n\n"
            "A human agent will assist you shortly. Thank you for your patience!"
        )

    return state


# ── General Query Node ─────────────────────────────────────────────────────

def handle_general_query(state: ChatState) -> ChatState:
    """Handle general queries using LLM with system prompt and conversation context.

    Uses TRAVEL_POLICY_PROMPT for policy questions and FAQ_PROMPT for FAQs
    to ground responses in actual SkyBook policies (anti-hallucination).
    """
    last_message = state["messages"][-1].content if state["messages"] else ""
    conversation_history = state.get("conversation_history", [])
    msg_lower = last_message.lower()

    try:
        llm = get_llm(temperature=0.3)

        # Detect policy-related questions and use grounded prompt
        policy_keywords = ["cancellation policy", "refund policy", "modification policy",
                          "baggage policy", "check-in policy", "boarding policy",
                          "unaccompanied minor", "pet policy", "travel policy",
                          "cancellation fee", "modification fee", "baggage allowance",
                          "how much baggage", "how much luggage", "cabin baggage",
                          "checked baggage", "extra baggage"]
        is_policy = any(kw in msg_lower for kw in policy_keywords)

        if is_policy:
            # Use grounded travel policy prompt — prevents hallucination about policies
            prompt = TRAVEL_POLICY_PROMPT.format(question=last_message)
            messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        else:
            # Build system prompt with conversation summary if available
            system_content = SYSTEM_PROMPT
            response_metadata = state.get("response_metadata") or {}
            conv_summary = response_metadata.get("conversation_summary")
            if not conv_summary:
                conv_summary = state.get("conversation_summary")
            if conv_summary:
                system_content += f"\n\nConversation so far:\n{conv_summary}"

            messages = [SystemMessage(content=system_content)]

            # Add recent conversation history for context (last 6 turns)
            for hist in conversation_history[-6:]:
                if hist["role"] == "user":
                    messages.append(HumanMessage(content=hist["content"]))
                elif hist["role"] == "assistant":
                    messages.append(AIMessage(content=hist["content"]))

            # Current message
            messages.append(HumanMessage(content=last_message))

        response = llm.invoke(messages)
        state["response"] = response.content
    except Exception as e:
        # Anti-hallucination fallback: don't make up answers when LLM is unavailable
        policy_keywords = ["cancellation", "refund", "modification", "baggage", "check-in", "boarding"]
        if any(kw in msg_lower for kw in policy_keywords):
            state["response"] = (
                "I can help with that! Please contact our customer support at "
                "1800-SKYBOOK (1800-759-2665) or email support@skybookairlines.com "
                "for detailed policy information, or I can connect you to a human agent."
            )
        else:
            state["response"] = (
                "I'm here to help with flight bookings, status checks, cancellations, and more. "
                "Could you rephrase your question? If you need immediate assistance, I can connect you to a human agent."
            )

    return state


# ── Travel Policy Node ──────────────────────────────────────────────────────

def handle_travel_policy(state: ChatState) -> ChatState:
    """Handle travel policy questions using grounded TRAVEL_POLICY_PROMPT."""
    last_message = state["messages"][-1].content if state["messages"] else ""

    try:
        llm = get_llm(temperature=0.3)
        prompt = TRAVEL_POLICY_PROMPT.format(question=last_message)
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        state["response"] = response.content
    except Exception:
        state["response"] = (
            "📋 **SkyBook Airlines Travel Policy:**\n\n"
            "• **Cancellation:** Free within 24 hours of booking. After that: ₹500 (economy), ₹750 (premium economy), ₹1,000 (business), ₹1,500 (first class).\n"
            "• **Refund:** Processed within 5-7 business days to original payment method.\n"
            "• **Modification:** Flight changes allowed up to 4 hours before departure with ₹500 modification fee.\n"
            "• **Baggage:** Economy (7kg cabin + 15kg checked), Premium Economy (10kg + 25kg), Business (15kg + 35kg), First (20kg + 40kg).\n"
            "• **Check-in:** Web check-in opens 48 hours before departure, closes 1 hour before.\n"
            "• **Boarding:** Closes 25 minutes before departure.\n"
            "• **Unaccompanied minors:** Children 5-11 can travel alone with prior arrangement (₹1,000 fee).\n"
            "• **Pets:** Small pets in cabin for ₹2,000 (domestic only).\n\n"
            "For more details, contact 1800-SKYBOOK or support@skybookairlines.com"
        )

    return state


# ── FAQ Node ────────────────────────────────────────────────────────────────

def handle_faq(state: ChatState) -> ChatState:
    """Handle FAQ questions using grounded FAQ_PROMPT."""
    last_message = state["messages"][-1].content if state["messages"] else ""

    try:
        llm = get_llm(temperature=0.3)
        prompt = FAQ_PROMPT.format(question=last_message)
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        state["response"] = response.content
    except Exception:
        state["response"] = (
            "I'd be happy to help with your question! For detailed information, "
            "please contact our customer support at 1800-SKYBOOK (1800-759-2665) "
            "or email support@skybookairlines.com. You can also ask me about "
            "flight bookings, check-in, baggage, or our travel policies."
        )

    return state


# ── Weather Node ────────────────────────────────────────────────────────────

def handle_weather(state: ChatState) -> ChatState:
    """Handle weather queries using Open-Meteo free API."""
    last_message = state["messages"][-1].content if state["messages"] else ""
    entities = state.get("entities", {})
    msg_lower = last_message.lower()

    # Determine which city to check weather for
    # Only use entities if they look like real cities (not leftover from failed extraction)
    city = None
    if entities.get("arrival_city"):
        result = city_retriever.retrieve(entities["arrival_city"])
        city = result["city"] if result else None
    if not city and entities.get("departure_city"):
        result = city_retriever.retrieve(entities["departure_city"])
        city = result["city"] if result else None

    if not city:
        # Try to extract a city from the message using RAG
        if not city_retriever._initialized:
            city_retriever.load_from_db()
        cities = city_retriever.extract_cities(last_message)
        if cities:
            city = cities[0]["city"]

    if not city:
        state["response"] = (
            "🌤️ I can check the weather for your departure or destination city.\n"
            "Which city would you like the weather for?"
        )
        return state

    db = state.get("db_session")
    result = tools.get_weather(city)

    if "error" in result:
        state["response"] = f"🌤️ {result['error']}"
    else:
        temp = result.get("temperature")
        condition = result.get("condition", "Unknown")
        wind = result.get("wind_speed")
        state["response"] = (
            f"🌤️ **Weather in {city.title()}:**\n"
            f"• Temperature: {temp}°C\n"
            f"• Condition: {condition}\n"
            f"• Wind Speed: {wind} km/h\n\n"
            f"Safe travels! ✈️"
        )

    return state


# ── Currency Conversion Node ────────────────────────────────────────────────

def handle_currency_conversion(state: ChatState) -> ChatState:
    """Handle currency conversion queries using free exchange rate API."""
    last_message = state["messages"][-1].content if state["messages"] else ""
    msg_lower = last_message.lower()

    # Extract amount and currencies from message
    import re
    amount_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', last_message)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else None

    # Try to detect currencies
    currency_map = {
        "inr": "INR", "rupee": "INR", "rupees": "INR", "₹": "INR",
        "usd": "USD", "dollar": "USD", "dollars": "USD", "$": "USD",
        "eur": "EUR", "euro": "EUR", "euros": "EUR", "€": "EUR",
        "gbp": "GBP", "pound": "GBP", "pounds": "GBP", "£": "GBP",
        "aed": "AED", "dirham": "AED", "dirhams": "AED",
        "sgd": "SGD", "singapore dollar": "SGD",
        "jpy": "JPY", "yen": "JPY",
        "aud": "AUD", "australian dollar": "AUD",
    }

    from_curr = None
    to_curr = None

    # Check for "X to Y" or "X in Y" pattern
    for keyword, code in currency_map.items():
        if keyword in msg_lower and from_curr is None:
            from_curr = code
        elif keyword in msg_lower and to_curr is None and code != from_curr:
            to_curr = code

    # Default: if only one currency mentioned and it's not INR, convert from INR
    if from_curr and not to_curr:
        if from_curr != "INR":
            to_curr = from_curr
            from_curr = "INR"
        else:
            to_curr = "USD"
    elif not from_curr and not to_curr:
        # No currency mentioned — try to use booking amount
        booking_result = state.get("booking_result")
        if booking_result and booking_result.get("total_amount"):
            amount = booking_result["total_amount"]
            from_curr = "INR"
            to_curr = "USD"
        else:
            state["response"] = (
                "💱 I can convert currency for you!\n"
                "Example: \"Convert 5000 INR to USD\" or \"How much is $100 in rupees?\""
            )
            return state

    if not amount:
        state["response"] = "💱 Please specify an amount to convert. Example: \"Convert 5000 INR to USD\""
        return state

    result = tools.convert_currency(amount, from_curr, to_curr)

    if "error" in result:
        state["response"] = f"💱 {result['error']}"
    else:
        converted = result["converted_amount"]
        rate = result["exchange_rate"]
        symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "د.إ", "SGD": "S$", "JPY": "¥", "AUD": "A$"}
        from_sym = symbols.get(from_curr, "")
        to_sym = symbols.get(to_curr, "")
        state["response"] = (
            f"💱 **Currency Conversion:**\n"
            f"• {from_sym}{amount:,.2f} {from_curr} = {to_sym}{converted:,.2f} {to_curr}\n"
            f"• Exchange Rate: 1 {from_curr} = {rate:.4f} {to_curr}\n\n"
            f"Rates are indicative and may vary at time of transaction."
        )

    return state


# ── Conversation Summary Node ──────────────────────────────────────────────

def generate_conversation_summary(state: ChatState) -> ChatState:
    """Generate a summary of the conversation (for context/memory)."""
    # Use conversation_history (includes previous turns) + current exchange
    conversation_history = state.get("conversation_history", [])
    current_response = state.get("response", "")
    last_message = state["messages"][-1].content if state["messages"] else ""

    # Build full conversation text from history + current turn
    all_turns = list(conversation_history[-10:])
    all_turns.append({"role": "user", "content": last_message})
    all_turns.append({"role": "assistant", "content": current_response})

    if len(all_turns) < 4:
        return state

    try:
        conversation_text = "\n".join([
            f"{'User' if t['role'] == 'user' else 'Bot'}: {t['content'][:200]}"
            for t in all_turns
        ])
        llm = get_llm(temperature=0.3)
        prompt = CONVERSATION_SUMMARY_PROMPT.format(conversation=conversation_text)
        response = llm.invoke([HumanMessage(content=prompt)])
        state["response_metadata"] = state.get("response_metadata") or {}
        state["response_metadata"]["conversation_summary"] = response.content
    except Exception:
        pass

    return state
