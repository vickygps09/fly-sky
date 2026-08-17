"""Chatbot Intent Classification Accuracy Test

Sends diverse user utterances to the chatbot API, collects predicted intents,
and computes Precision, Recall, and F1 score per intent class + macro/weighted averages.

Usage:
    python test_chatbot_accuracy.py
"""

import requests
import uuid
import json
import time
from collections import defaultdict

API_URL = "http://localhost:8000/api/chat/message"

# ── Test Dataset ────────────────────────────────────────────────────────────
# Each entry: (utterance, expected_intent)
# Covers many different ways users might phrase the same intent

TEST_CASES = [
    # ── greeting (10) ──
    ("Hi there", "greeting"),
    ("Hello", "greeting"),
    ("Hey", "greeting"),
    ("Good morning", "greeting"),
    ("Good evening", "greeting"),
    ("Greetings", "greeting"),
    ("Hiya", "greeting"),
    ("What's up", "greeting"),
    ("Hey there", "greeting"),
    ("Good afternoon", "greeting"),

    # ── book_flight (15) ──
    ("I need a flight from Mumbai to Delhi", "book_flight"),
    ("Book a flight from Bangalore to Chennai tomorrow", "book_flight"),
    ("Search flights from Delhi to Goa", "book_flight"),
    ("Find me a flight to Mumbai", "book_flight"),
    ("I want to fly from Pune to Kolkata", "book_flight"),
    ("Need a ticket from Bangalore to Delhi", "book_flight"),
    ("Looking for flights from Chennai to Hyderabad", "book_flight"),
    ("Can you book me a flight from Delhi to Bangalore", "book_flight"),
    ("I'd like to book a flight", "book_flight"),
    ("Show me flights from Mumbai to Pune on 2025-12-25", "book_flight"),
    ("Plan a trip from Delhi to Goa", "book_flight"),
    ("Get me a plane ticket from Kolkata to Mumbai", "book_flight"),
    ("I need to travel from Bangalore to Delhi next week", "book_flight"),
    ("Book 2 tickets from Chennai to Delhi", "book_flight"),
    ("Help me find a flight from Hyderabad to Bangalore", "book_flight"),

    # ── flight_status (10) ──
    ("What is the status of flight SB101", "flight_status"),
    ("Check flight status for SB102", "flight_status"),
    ("Is my flight SB103 on time", "flight_status"),
    ("Flight status of SB104", "flight_status"),
    ("Where is flight SB105 now", "flight_status"),
    ("Check SB106 status", "flight_status"),
    ("Tell me the status of SB107", "flight_status"),
    ("Has flight SB108 departed", "flight_status"),
    ("SB109 flight status", "flight_status"),
    ("Is SB110 delayed", "flight_status"),

    # ── cancel_booking (10) ──
    ("Cancel my booking ABC123", "cancel_booking"),
    ("I want to cancel my flight", "cancel_booking"),
    ("Cancel booking XYZ789", "cancel_booking"),
    ("Please cancel my reservation", "cancel_booking"),
    ("I need to cancel my ticket", "cancel_booking"),
    ("Cancel the booking PNR TEST45", "cancel_booking"),
    ("Can you cancel my flight booking", "cancel_booking"),
    ("I'd like to cancel my booking", "cancel_booking"),
    ("Cancel my trip", "cancel_booking"),
    ("Please cancel booking ABC123", "cancel_booking"),

    # ── modify_booking (10) ──
    ("Modify my booking ABC123", "modify_booking"),
    ("I want to change my flight", "modify_booking"),
    ("Change my booking XYZ789", "modify_booking"),
    ("Reschedule my flight", "modify_booking"),
    ("I need to modify my reservation", "modify_booking"),
    ("Change the date of my booking", "modify_booking"),
    ("I want to change my seat", "modify_booking"),
    ("Modify my flight booking", "modify_booking"),
    ("Can I change my flight to tomorrow", "modify_booking"),
    ("Reschedule booking ABC123", "modify_booking"),

    # ── refund (10) ──
    ("Where is my refund for ABC123", "refund"),
    ("Refund status for booking XYZ789", "refund"),
    ("I want to check my refund", "refund"),
    ("When will I get my refund", "refund"),
    ("Has my refund been processed", "refund"),
    ("Check refund status for ABC123", "refund"),
    ("I need a refund for my cancelled flight", "refund"),
    ("Refund for booking TEST45", "refund"),
    ("Tell me about my refund", "refund"),
    ("Is my refund processed for ABC123", "refund"),

    # ── check_in (10) ──
    ("Check-in for ABC123", "check_in"),
    ("I want to do web check-in", "check_in"),
    ("Web check-in for my flight", "check_in"),
    ("Check me in for booking ABC123", "check_in"),
    ("I need my boarding pass", "check_in"),
    ("Boarding pass for XYZ789", "check_in"),
    ("Can I check in online", "check_in"),
    ("Online check-in for ABC123", "check_in"),
    ("Get me my boarding pass", "check_in"),
    ("I'd like to check in for my flight", "check_in"),

    # ── baggage_info (10) ──
    ("What is the baggage allowance", "baggage_info"),
    ("How much luggage can I carry", "baggage_info"),
    ("Baggage info for economy class", "baggage_info"),
    ("What is the luggage limit", "baggage_info"),
    ("How many kg of baggage is allowed", "baggage_info"),
    ("Tell me about baggage policy", "baggage_info"),
    ("Baggage allowance for business class", "baggage_info"),
    ("How much checked baggage can I take", "baggage_info"),
    ("What is the cabin baggage limit", "baggage_info"),
    ("Luggage allowance information", "baggage_info"),

    # ── fare_comparison (8) ──
    ("Compare fares for flights", "fare_comparison"),
    ("Fare comparison between economy and business", "fare_comparison"),
    ("I want to compare flight prices", "fare_comparison"),
    ("Compare ticket prices", "fare_comparison"),
    ("What are the different fare options", "fare_comparison"),
    ("Show me fare comparison", "fare_comparison"),
    ("Compare prices for Bangalore to Delhi", "fare_comparison"),
    ("Which class is cheapest", "fare_comparison"),

    # ── help (8) ──
    ("Help", "help"),
    ("What can you do", "help"),
    ("Help me", "help"),
    ("What can you help me with", "help"),
    ("I need help", "help"),
    ("What are your capabilities", "help"),
    ("How can you assist me", "help"),
    ("Tell me what you can do", "help"),

    # ── human_agent (8) ──
    ("I want to talk to a human agent", "human_agent"),
    ("Connect me to a representative", "human_agent"),
    ("Talk to an agent", "human_agent"),
    ("I need to speak with a human", "human_agent"),
    ("Can I talk to a real person", "human_agent"),
    ("Transfer me to a human agent", "human_agent"),
    ("I want to speak to customer service", "human_agent"),
    ("Get me a human agent", "human_agent"),

    # ── my_bookings (8) ──
    ("Show my bookings", "my_bookings"),
    ("My bookings", "my_bookings"),
    ("Show my tickets", "my_bookings"),
    ("My reservations", "my_bookings"),
    ("What are my bookings", "my_bookings"),
    ("Show me my flight bookings", "my_bookings"),
    ("List my bookings", "my_bookings"),
    ("What flights do I have booked", "my_bookings"),

    # ── general_query (10) ──
    ("What is the weather in Delhi", "general_query"),
    ("Best time to visit Goa", "general_query"),
    ("Tell me a joke", "general_query"),
    ("What is the capital of India", "general_query"),
    ("Do you know about COVID travel restrictions", "general_query"),
    ("What is the exchange rate", "general_query"),
    ("Tell me about tourist places in Mumbai", "general_query"),
    ("What is the time zone in India", "general_query"),
    ("How is the traffic in Bangalore", "general_query"),
    ("Recommend a good hotel in Delhi", "general_query"),
]


def send_message(message: str, session_id: str) -> dict | None:
    """Send a message to the chatbot API and return the response."""
    try:
        resp = requests.post(
            API_URL,
            json={"message": message, "session_id": session_id, "user_id": None},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  [ERROR] HTTP {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def compute_metrics(test_results: list[tuple[str, str, str]]) -> dict:
    """Compute precision, recall, F1 per intent class + macro/weighted averages.

    test_results: list of (utterance, expected_intent, predicted_intent)
    """
    # Build confusion data
    all_intents = sorted(set(exp for _, exp, _ in test_results) | set(pred for _, _, pred in test_results))

    # Per-intent counts
    tp = defaultdict(int)  # true positive
    fp = defaultdict(int)  # false positive
    fn = defaultdict(int)  # false negative
    support = defaultdict(int)  # actual occurrences

    for _, expected, predicted in test_results:
        support[expected] += 1
        if predicted == expected:
            tp[expected] += 1
        else:
            fn[expected] += 1
            fp[predicted] += 1

    # Per-intent metrics
    per_intent = {}
    for intent in all_intents:
        precision = tp[intent] / (tp[intent] + fp[intent]) if (tp[intent] + fp[intent]) > 0 else 0.0
        recall = tp[intent] / (tp[intent] + fn[intent]) if (tp[intent] + fn[intent]) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_intent[intent] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp[intent],
            "fp": fp[intent],
            "fn": fn[intent],
            "support": support[intent],
        }

    # Macro averages (unweighted)
    macro_p = sum(per_intent[i]["precision"] for i in all_intents) / len(all_intents)
    macro_r = sum(per_intent[i]["recall"] for i in all_intents) / len(all_intents)
    macro_f1 = sum(per_intent[i]["f1"] for i in all_intents) / len(all_intents)

    # Weighted averages (by support)
    total_support = sum(support.values())
    weighted_p = sum(per_intent[i]["precision"] * support[i] for i in all_intents) / total_support
    weighted_r = sum(per_intent[i]["recall"] * support[i] for i in all_intents) / total_support
    weighted_f1 = sum(per_intent[i]["f1"] * support[i] for i in all_intents) / total_support

    # Accuracy
    correct = sum(1 for _, exp, pred in test_results if exp == pred)
    accuracy = correct / len(test_results)

    return {
        "per_intent": per_intent,
        "macro": {"precision": macro_p, "recall": macro_r, "f1": macro_f1},
        "weighted": {"precision": weighted_p, "recall": weighted_r, "f1": weighted_f1},
        "accuracy": accuracy,
        "total": len(test_results),
        "correct": correct,
    }


def main():
    print("=" * 80)
    print("  SkyBook AI Chatbot — Intent Classification Accuracy Test")
    print("=" * 80)
    print(f"\n  Total test cases: {len(TEST_CASES)}")
    print(f"  API endpoint: {API_URL}\n")
    print("  Sending messages to chatbot...\n")

    results = []
    session_id = str(uuid.uuid4())

    for i, (utterance, expected) in enumerate(TEST_CASES, 1):
        # Use a fresh session for each message to avoid multi-turn flow interference
        test_session = str(uuid.uuid4())
        response = send_message(utterance, test_session)

        if response is None:
            predicted = "ERROR"
            print(f"  [{i:3d}/{len(TEST_CASES)}] ❌ ERROR — '{utterance[:50]}'")
        else:
            predicted = response.get("intent", "unknown")
            status = "✅" if predicted == expected else "❌"
            print(f"  [{i:3d}/{len(TEST_CASES)}] {status} '{utterance[:50]}' → expected: {expected}, got: {predicted}")

        results.append((utterance, expected, predicted))

        # Small delay to avoid rate limiting (Gemini free tier: 15 RPM)
        time.sleep(1.0)

    # ── Compute metrics ──
    print("\n" + "=" * 80)
    print("  RESULTS — Precision, Recall, F1 Score")
    print("=" * 80)

    metrics = compute_metrics(results)

    print(f"\n  Overall Accuracy: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")
    print()

    # Per-intent table
    print(f"  {'Intent':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'TP':>5} {'FP':>5} {'FN':>5} {'Support':>8}")
    print("  " + "-" * 78)

    for intent in sorted(metrics["per_intent"].keys()):
        m = metrics["per_intent"][intent]
        print(f"  {intent:<20} {m['precision']:>10.1%} {m['recall']:>10.1%} {m['f1']:>10.1%} {m['tp']:>5} {m['fp']:>5} {m['fn']:>5} {m['support']:>8}")

    print("  " + "-" * 78)
    print(f"  {'MACRO AVG':<20} {metrics['macro']['precision']:>10.1%} {metrics['macro']['recall']:>10.1%} {metrics['macro']['f1']:>10.1%}")
    print(f"  {'WEIGHTED AVG':<20} {metrics['weighted']['precision']:>10.1%} {metrics['weighted']['recall']:>10.1%} {metrics['weighted']['f1']:>10.1%}")

    # ── Misclassifications ──
    misclassified = [(u, e, p) for u, e, p in results if e != p]
    if misclassified:
        print(f"\n  Misclassifications ({len(misclassified)}):")
        print("  " + "-" * 78)
        for u, e, p in misclassified:
            print(f"  '{u[:60]}' → expected: {e}, got: {p}")
    else:
        print("\n  ✅ All classifications correct!")

    # ── Save results to JSON ──
    output = {
        "total": metrics["total"],
        "correct": metrics["correct"],
        "accuracy": metrics["accuracy"],
        "macro": metrics["macro"],
        "weighted": metrics["weighted"],
        "per_intent": metrics["per_intent"],
        "misclassified": [{"utterance": u, "expected": e, "predicted": p} for u, e, p in misclassified],
    }
    with open("chatbot_test_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to chatbot_test_results.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
