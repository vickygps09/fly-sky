"""LLM & RAG Evaluation Script — Computes precision, recall, F1-score for intent recognition and entity extraction.

Run: python evaluate.py

Tests the chatbot pipeline against a labeled test dataset and reports:
- Intent classification: precision, recall, F1 (per-class + macro/weighted)
- Entity extraction: precision, recall, F1 (per-field + overall)
- RAG city retrieval: accuracy, confidence analysis
- End-to-end flow accuracy
"""
import json
import sys
import os
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot.rag import city_retriever
from chatbot.nodes import intent_recognition, entity_extraction
from chatbot.state import ChatState
from langchain_core.messages import HumanMessage


# ── Test Dataset ────────────────────────────────────────────────────────────

INTENT_TEST_CASES = [
    # (message, expected_intent)
    ("Hi there", "greeting"),
    ("Hello", "greeting"),
    ("Hey, can you help me?", "help"),
    ("I want to book a flight", "book_flight"),
    ("I need a flight from Bangalore to Delhi", "book_flight"),
    ("Search flights from Mumbai to Chennai", "book_flight"),
    ("Find me a flight tomorrow", "book_flight"),
    ("Cancel my booking DEMO01", "cancel_booking"),
    ("I want to cancel my flight", "cancel_booking"),
    ("What is the status of SB101?", "flight_status"),
    ("Check flight status for SB167", "flight_status"),
    ("Flight status", "flight_status"),
    ("I want to modify my booking", "modify_booking"),
    ("Change my flight date", "modify_booking"),
    ("Reschedule my flight", "modify_booking"),
    ("Where is my refund for DEMO01?", "refund"),
    ("Refund status", "refund"),
    ("I want to check in for my flight", "check_in"),
    ("Web check-in for DEMO01", "check_in"),
    ("Boarding pass", "check_in"),
    ("What is the baggage allowance?", "baggage_info"),
    ("How much luggage can I carry?", "baggage_info"),
    ("Compare fares for Bangalore to Delhi", "fare_comparison"),
    ("Show me fare options", "fare_comparison"),
    ("I want to talk to a human agent", "human_agent"),
    ("Connect me to a representative", "human_agent"),
    ("What can you do?", "help"),
    ("Help me", "help"),
    ("What is the weather in Delhi?", "general_query"),
    ("Tell me about your airline", "general_query"),
]

ENTITY_TEST_CASES = [
    # (message, expected_entities)
    ("I need a flight from Bangalore to Delhi tomorrow",
     {"departure_city": "Bangalore", "arrival_city": "Delhi"}),
    ("Search flights from Mumbai to Chennai",
     {"departure_city": "Mumbai", "arrival_city": "Chennai"}),
    ("Fly from Bombay to Madras on 2025-08-20",
     {"departure_city": "Mumbai", "arrival_city": "Chennai"}),
    ("I want to fly from Bengaluru to Kolkata",
     {"departure_city": "Bangalore", "arrival_city": "Kolkata"}),
    ("Book a flight from Delhi to Goa",
     {"departure_city": "Delhi", "arrival_city": "Goa"}),
    ("Flight from BLR to DEL tomorrow",
     {"departure_city": "Bangalore", "arrival_city": "Delhi"}),
    ("I need a flight from Hyderabad to Jaipur for 3 passengers",
     {"departure_city": "Hyderabad", "arrival_city": "Jaipur", "passengers": 3}),
    ("Search flights from Calcutta to Cochin",
     {"departure_city": "Kolkata", "arrival_city": "Kochi"}),
    ("Find flights from Ahmedabad to Delhi tomorrow 2 passengers business class",
     {"departure_city": "Ahmedabad", "arrival_city": "Delhi", "passengers": 2, "cabin_class": "business"}),
    ("Cancel booking DEMO01",
     {"booking_id": "DEMO01"}),
    ("Check SB101 status",
     {"flight_number": "SB101"}),
]

RAG_TEST_CASES = [
    # (query, expected_city)
    ("Bangalore", "Bangalore"),
    ("Bengaluru", "Bangalore"),
    ("BLR", "Bangalore"),
    ("Delhi", "Delhi"),
    ("New Delhi", "Delhi"),
    ("DEL", "Delhi"),
    ("Mumbai", "Mumbai"),
    ("Bombay", "Mumbai"),
    ("BOM", "Mumbai"),
    ("Chennai", "Chennai"),
    ("Madras", "Chennai"),
    ("MAA", "Chennai"),
    ("Hyderabad", "Hyderabad"),
    ("HYD", "Hyderabad"),
    ("Kolkata", "Kolkata"),
    ("Calcutta", "Kolkata"),
    ("CCU", "Kolkata"),
    ("Goa", "Goa"),
    ("GOI", "Goa"),
    ("Kochi", "Kochi"),
    ("Cochin", "Kochi"),
    ("COK", "Kochi"),
    ("Jaipur", "Jaipur"),
    ("JAI", "Jaipur"),
    ("Ahmedabad", "Ahmedabad"),
    ("AMD", "Ahmedabad"),
    # Typos / fuzzy
    ("Bengaluru", "Bangalore"),
    ("Benglore", "Bangalore"),
    ("Mumbia", "Mumbai"),
    ("Chennnai", "Chennai"),
    ("Delhii", "Delhi"),
    ("Kolkota", "Kolkata"),
    ("Hydrabad", "Hyderabad"),
    ("Jaipr", "Jaipur"),
]


# ── Metrics ─────────────────────────────────────────────────────────────────

def compute_prf(tp: int, fp: int, fn: int) -> dict:
    """Compute precision, recall, F1-score."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def evaluate_intents() -> dict:
    """Evaluate intent recognition accuracy."""
    print("\n" + "=" * 70)
    print("📊 INTENT RECOGNITION EVALUATION")
    print("=" * 70)

    per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    total_correct = 0
    total = len(INTENT_TEST_CASES)

    for message, expected in INTENT_TEST_CASES:
        state: ChatState = {
            "messages": [HumanMessage(content=message)],
            "intent": None,
            "entities": {},
            "flow_step": None,
            "session_id": "eval",
            "user_id": None,
            "conversation_history": [],
            "conversation_summary": None,
            "search_results": None,
            "selected_flight": None,
            "pending_booking": None,
            "booking_result": None,
            "response": "",
            "response_metadata": None,
            "escalated": False,
            "db_session": None,
        }
        state = intent_recognition(state)
        predicted = state.get("intent", "unknown")

        if predicted == expected:
            total_correct += 1
            per_class[expected]["tp"] += 1
        else:
            per_class[expected]["fn"] += 1
            per_class[predicted]["fp"] += 1

        status = "✅" if predicted == expected else "❌"
        print(f"  {status} '{message[:40]:<40}' expected={expected:<16} got={predicted}")

    # Per-class metrics
    print(f"\n  {'Intent':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'FN':>5}")
    print("  " + "-" * 65)

    all_precisions = []
    all_recalls = []
    all_f1s = []
    class_results = {}

    for cls in sorted(per_class.keys()):
        m = compute_prf(per_class[cls]["tp"], per_class[cls]["fp"], per_class[cls]["fn"])
        class_results[cls] = m
        all_precisions.append(m["precision"])
        all_recalls.append(m["recall"])
        all_f1s.append(m["f1"])
        print(f"  {cls:<20} {m['precision']:>10.2%} {m['recall']:>10.2%} {m['f1']:>10.2%} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5}")

    macro_precision = sum(all_precisions) / len(all_precisions) if all_precisions else 0
    macro_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0
    macro_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0
    accuracy = total_correct / total

    print("  " + "-" * 65)
    print(f"  {'MACRO':<20} {macro_precision:>10.2%} {macro_recall:>10.2%} {macro_f1:>10.2%}")
    print(f"\n  Accuracy: {total_correct}/{total} = {accuracy:.2%}")

    return {
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_class": class_results,
        "total": total,
        "correct": total_correct,
    }


def evaluate_entities() -> dict:
    """Evaluate entity extraction accuracy."""
    print("\n" + "=" * 70)
    print("📊 ENTITY EXTRACTION EVALUATION")
    print("=" * 70)

    per_field = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    total_correct = 0
    total = len(ENTITY_TEST_CASES)

    for message, expected in ENTITY_TEST_CASES:
        state: ChatState = {
            "messages": [HumanMessage(content=message)],
            "intent": "book_flight",
            "entities": {},
            "flow_step": None,
            "session_id": "eval",
            "user_id": None,
            "conversation_history": [],
            "conversation_summary": None,
            "search_results": None,
            "selected_flight": None,
            "pending_booking": None,
            "booking_result": None,
            "response": "",
            "response_metadata": None,
            "escalated": False,
            "db_session": None,
        }
        state = entity_extraction(state)
        predicted = state.get("entities", {})

        # Compare each expected field
        all_match = True
        for field, expected_val in expected.items():
            pred_val = predicted.get(field)
            # Normalize comparison
            if isinstance(expected_val, str):
                match = pred_val and pred_val.lower() == expected_val.lower()
            else:
                match = pred_val == expected_val

            if match:
                per_field[field]["tp"] += 1
            else:
                per_field[field]["fn"] += 1
                if pred_val is not None:
                    per_field[field]["fp"] += 1
                all_match = False

        # Note: extra fields are NOT counted as false positives since
        # the LLM may extract additional useful entities (e.g., trip_type)
        # that weren't in the expected set but are still correct

        if all_match:
            total_correct += 1

        status = "✅" if all_match else "❌"
        print(f"  {status} '{message[:50]:<50}'")
        if not all_match:
            for field, expected_val in expected.items():
                pred_val = predicted.get(field, "MISSING")
                if (isinstance(expected_val, str) and (not pred_val or pred_val.lower() != expected_val.lower())) or \
                   (not isinstance(expected_val, str) and pred_val != expected_val):
                    print(f"       {field}: expected={expected_val}, got={pred_val}")

    # Per-field metrics
    print(f"\n  {'Field':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'FN':>5}")
    print("  " + "-" * 65)

    all_precisions = []
    all_recalls = []
    all_f1s = []
    field_results = {}

    for field in sorted(per_field.keys()):
        m = compute_prf(per_field[field]["tp"], per_field[field]["fp"], per_field[field]["fn"])
        field_results[field] = m
        all_precisions.append(m["precision"])
        all_recalls.append(m["recall"])
        all_f1s.append(m["f1"])
        print(f"  {field:<20} {m['precision']:>10.2%} {m['recall']:>10.2%} {m['f1']:>10.2%} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5}")

    macro_precision = sum(all_precisions) / len(all_precisions) if all_precisions else 0
    macro_recall = sum(all_recalls) / len(all_recalls) if all_recalls else 0
    macro_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0
    accuracy = total_correct / total

    print("  " + "-" * 65)
    print(f"  {'MACRO':<20} {macro_precision:>10.2%} {macro_recall:>10.2%} {macro_f1:>10.2%}")
    print(f"\n  Exact Match Accuracy: {total_correct}/{total} = {accuracy:.2%}")

    return {
        "accuracy": accuracy,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "per_field": field_results,
        "total": total,
        "correct": total_correct,
    }


def evaluate_rag() -> dict:
    """Evaluate RAG city retrieval accuracy."""
    print("\n" + "=" * 70)
    print("📊 RAG CITY RETRIEVAL EVALUATION")
    print("=" * 70)

    # Initialize retriever
    city_retriever.load_from_db()

    total_correct = 0
    total = len(RAG_TEST_CASES)
    method_counts = defaultdict(int)
    confidence_scores = []

    for query, expected in RAG_TEST_CASES:
        result = city_retriever.retrieve(query)
        predicted = result["city"] if result else None
        method = result["method"] if result else "none"
        confidence = result["confidence"] if result else 0.0

        match = predicted and predicted.lower() == expected.lower()
        if match:
            total_correct += 1
            method_counts[method] += 1
            confidence_scores.append(confidence)

        status = "✅" if match else "❌"
        print(f"  {status} '{query:<15}' expected={expected:<15} got={predicted or 'None':<15} method={method:<12} conf={confidence:.2f}")

    accuracy = total_correct / total
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

    print(f"\n  Accuracy: {total_correct}/{total} = {accuracy:.2%}")
    print(f"  Avg Confidence (correct): {avg_confidence:.2%}")
    print(f"  Retrieval Methods:")
    for method, count in sorted(method_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {method:<15}: {count}")

    return {
        "accuracy": accuracy,
        "avg_confidence": avg_confidence,
        "method_counts": dict(method_counts),
        "total": total,
        "correct": total_correct,
    }


def evaluate_route_extraction() -> dict:
    """Evaluate RAG route extraction (from X to Y)."""
    print("\n" + "=" * 70)
    print("📊 RAG ROUTE EXTRACTION EVALUATION")
    print("=" * 70)

    route_cases = [
        ("from Bangalore to Delhi", "Bangalore", "Delhi"),
        ("from Mumbai to Chennai", "Mumbai", "Chennai"),
        ("from Bombay to Madras", "Mumbai", "Chennai"),
        ("from Bengaluru to Kolkata", "Bangalore", "Kolkata"),
        ("from BLR to DEL", "Bangalore", "Delhi"),
        ("from Goa to Kochi", "Goa", "Kochi"),
        ("from Hyderabad to Jaipur", "Hyderabad", "Jaipur"),
        ("from Calcutta to Cochin", "Kolkata", "Kochi"),
        ("from Ahmedabad to Delhi tomorrow", "Ahmedabad", "Delhi"),
    ]

    total_correct = 0
    total = len(route_cases)

    for message, exp_dep, exp_arr in route_cases:
        dep, arr = city_retriever.extract_route(message)
        match = dep and arr and dep.lower() == exp_dep.lower() and arr.lower() == exp_arr.lower()
        if match:
            total_correct += 1

        status = "✅" if match else "❌"
        print(f"  {status} '{message:<40}' expected={exp_dep}→{exp_arr} got={dep}→{arr}")

    accuracy = total_correct / total
    print(f"\n  Route Accuracy: {total_correct}/{total} = {accuracy:.2%}")

    return {"accuracy": accuracy, "total": total, "correct": total_correct}


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "█" * 70)
    print("█  SkyBook AI — LLM & RAG Evaluation Report")
    print("█  Date: " + date.today().isoformat())
    print("█" * 70)

    intent_results = evaluate_intents()
    entity_results = evaluate_entities()
    rag_results = evaluate_rag()
    route_results = evaluate_route_extraction()

    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    print(f"  Intent Recognition:    Accuracy={intent_results['accuracy']:.2%}  Macro-F1={intent_results['macro_f1']:.2%}")
    print(f"  Entity Extraction:     Accuracy={entity_results['accuracy']:.2%}  Macro-F1={entity_results['macro_f1']:.2%}")
    print(f"  RAG City Retrieval:    Accuracy={rag_results['accuracy']:.2%}  Avg Confidence={rag_results['avg_confidence']:.2%}")
    print(f"  Route Extraction:      Accuracy={route_results['accuracy']:.2%}")

    # Save report as JSON
    report = {
        "date": date.today().isoformat(),
        "intent_recognition": intent_results,
        "entity_extraction": entity_results,
        "rag_city_retrieval": rag_results,
        "route_extraction": route_results,
    }

    report_path = os.path.join(os.path.dirname(__file__), "evaluation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  📄 Report saved to: {report_path}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
