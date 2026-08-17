"""LangGraph workflow — defines the conversation graph.

The graph routes user messages through:
1. Intent recognition
2. Entity extraction
3. Intent-specific handler (conditional edge)
4. Conversation summary (optional)

This implements: context memory, multi-turn conversations, intent recognition,
entity extraction, conversation summary, and human agent transfer.
"""

from langgraph.graph import StateGraph, END
from chatbot.state import ChatState
from chatbot.nodes import (
    intent_recognition,
    entity_extraction,
    handle_greeting,
    handle_book_flight,
    handle_flight_status,
    handle_cancel_booking,
    handle_modify_booking,
    handle_refund,
    handle_check_in,
    handle_my_bookings,
    handle_baggage_info,
    handle_fare_comparison,
    handle_travel_policy,
    handle_faq,
    handle_weather,
    handle_currency_conversion,
    handle_help,
    handle_human_agent,
    handle_general_query,
    generate_conversation_summary,
)


# ── Conditional Router ─────────────────────────────────────────────────────

def route_by_intent(state: ChatState) -> str:
    """Route to the appropriate handler based on detected intent."""
    intent = state.get("intent", "general_query")

    routing = {
        "greeting": "greeting",
        "book_flight": "book_flight",
        "flight_status": "flight_status",
        "cancel_booking": "cancel_booking",
        "modify_booking": "modify_booking",
        "refund": "refund",
        "check_in": "check_in",
        "my_bookings": "my_bookings",
        "baggage_info": "baggage_info",
        "fare_comparison": "fare_comparison",
        "travel_policy": "travel_policy",
        "faq": "faq",
        "weather": "weather",
        "currency_conversion": "currency_conversion",
        "help": "help",
        "human_agent": "human_agent",
        "general_query": "general_query",
    }

    return routing.get(intent, "general_query")


# ── Build the Graph ────────────────────────────────────────────────────────

def build_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(ChatState)

    # Add nodes
    workflow.add_node("intent_recognition", intent_recognition)
    workflow.add_node("entity_extraction", entity_extraction)
    workflow.add_node("greeting", handle_greeting)
    workflow.add_node("book_flight", handle_book_flight)
    workflow.add_node("flight_status", handle_flight_status)
    workflow.add_node("cancel_booking", handle_cancel_booking)
    workflow.add_node("modify_booking", handle_modify_booking)
    workflow.add_node("refund", handle_refund)
    workflow.add_node("check_in", handle_check_in)
    workflow.add_node("my_bookings", handle_my_bookings)
    workflow.add_node("baggage_info", handle_baggage_info)
    workflow.add_node("fare_comparison", handle_fare_comparison)
    workflow.add_node("travel_policy", handle_travel_policy)
    workflow.add_node("faq", handle_faq)
    workflow.add_node("weather", handle_weather)
    workflow.add_node("currency_conversion", handle_currency_conversion)
    workflow.add_node("help", handle_help)
    workflow.add_node("human_agent", handle_human_agent)
    workflow.add_node("general_query", handle_general_query)
    workflow.add_node("summary", generate_conversation_summary)

    # Set entry point
    workflow.set_entry_point("intent_recognition")

    # Intent recognition → entity extraction
    workflow.add_edge("intent_recognition", "entity_extraction")

    # Entity extraction → conditional routing
    workflow.add_conditional_edges(
        "entity_extraction",
        route_by_intent,
        {
            "greeting": "greeting",
            "book_flight": "book_flight",
            "flight_status": "flight_status",
            "cancel_booking": "cancel_booking",
            "modify_booking": "modify_booking",
            "refund": "refund",
            "check_in": "check_in",
            "my_bookings": "my_bookings",
            "baggage_info": "baggage_info",
            "fare_comparison": "fare_comparison",
            "travel_policy": "travel_policy",
            "faq": "faq",
            "weather": "weather",
            "currency_conversion": "currency_conversion",
            "help": "help",
            "human_agent": "human_agent",
            "general_query": "general_query",
        },
    )

    # All handlers → summary
    for handler in [
        "greeting", "book_flight", "flight_status", "cancel_booking",
        "modify_booking", "refund", "check_in", "my_bookings", "baggage_info",
        "fare_comparison", "travel_policy", "faq", "weather", "currency_conversion", "help", "human_agent", "general_query",
    ]:
        workflow.add_edge(handler, "summary")

    # Summary → END
    workflow.add_edge("summary", END)

    return workflow.compile()


# Compiled graph instance (lazily initialized)
_graph_instance = None


def get_graph():
    """Get the compiled graph (singleton)."""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
