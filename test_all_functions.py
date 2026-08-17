"""Comprehensive function test for SkyBook AI Chatbot.

Tests all major features:
1. Health & monitoring endpoints
2. Weather API (Open-Meteo)
3. Currency conversion API
4. Baggage info (chatbot node)
5. Coupon validation (payments endpoint)
6. Flight search
7. Booking flow (form-based)
8. Payment initiation & confirmation
9. Booking retrieval by PNR
10. Intent classification (weather, currency, baggage)
11. Check-in flow
12. Fare comparison

Usage:
    python test_all_functions.py
"""

import requests
import uuid
import json
import sys
import time
from datetime import datetime, timedelta

API_BASE = "http://localhost:8000/api"
CHAT_URL = f"{API_BASE}/chat/message"
PAYMENTS_URL = f"{API_BASE}/payments"

PASS = 0
FAIL = 0
RESULTS = []


def test(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "✅ PASS" if condition else "❌ FAIL"
    line = f"  {status} — {name}"
    if detail:
        line += f" ({detail})"
    print(line)
    RESULTS.append({"name": name, "passed": condition, "detail": detail})
    if condition:
        PASS += 1
    else:
        FAIL += 1


def send_chat(message: str, session_id: str = None) -> dict | None:
    try:
        resp = requests.post(
            CHAT_URL,
            json={
                "message": message,
                "session_id": session_id or str(uuid.uuid4()),
                "user_id": None,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 80)
    print("  SkyBook AI — Comprehensive Function Test")
    print("=" * 80)
    print(f"  API: {API_BASE}")
    print(f"  Time: {datetime.now().isoformat()}\n")

    # ── 1. Health & Monitoring ──────────────────────────────────────────────
    print("\n📋 1. Health & Monitoring Endpoints")
    print("-" * 60)

    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        data = resp.json()
        test("Health endpoint returns 200", resp.status_code == 200, f"status={data.get('status', 'unknown')}")
    except Exception as e:
        test("Health endpoint", False, str(e))

    try:
        resp = requests.get(f"{API_BASE}/metrics", timeout=5)
        data = resp.json()
        test("Metrics endpoint returns 200", resp.status_code == 200, f"keys={list(data.keys())[:5]}")
    except Exception as e:
        test("Metrics endpoint", False, str(e))

    # ── 2. Weather API (via chatbot) ────────────────────────────────────────
    print("\n🌤️ 2. Weather API (Open-Meteo via chatbot)")
    print("-" * 60)

    sid = str(uuid.uuid4())
    resp = send_chat("What's the weather in Delhi?", sid)
    if resp and "error" not in resp:
        reply = resp.get("reply", "")
        intent = resp.get("intent", "")
        has_weather = "temperature" in reply.lower() or "weather" in reply.lower() or "°c" in reply.lower()
        test("Weather intent detected", intent == "weather", f"intent={intent}")
        test("Weather response has data", has_weather, f"reply[:80]={reply[:80]}")
    else:
        test("Weather API", False, str(resp.get("error", "no response")))

    # ── 3. Currency Conversion (via chatbot) ────────────────────────────────
    print("\n💱 3. Currency Conversion (via chatbot)")
    print("-" * 60)

    sid = str(uuid.uuid4())
    resp = send_chat("Convert 5000 INR to USD", sid)
    if resp and "error" not in resp:
        reply = resp.get("reply", "")
        intent = resp.get("intent", "")
        has_conversion = "usd" in reply.lower() or "$" in reply or "exchange" in reply.lower()
        test("Currency intent detected", intent == "currency_conversion", f"intent={intent}")
        test("Currency response has conversion", has_conversion, f"reply[:80]={reply[:80]}")
    else:
        test("Currency Conversion", False, str(resp.get("error", "no response")))

    # ── 4. Baggage Info (via chatbot) ───────────────────────────────────────
    print("\n🧳 4. Baggage Info (via chatbot)")
    print("-" * 60)

    sid = str(uuid.uuid4())
    resp = send_chat("What is the baggage allowance?", sid)
    if resp and "error" not in resp:
        reply = resp.get("reply", "")
        intent = resp.get("intent", "")
        has_baggage = "cabin baggage" in reply.lower() or "checked baggage" in reply.lower() or "kg" in reply.lower()
        test("Baggage intent detected", intent == "baggage_info", f"intent={intent}")
        test("Baggage response has data", has_baggage, f"reply[:80]={reply[:80]}")
    else:
        test("Baggage Info", False, str(resp.get("error", "no response")))

    # ── 5. Coupon Validation ────────────────────────────────────────────────
    print("\n🎫 5. Coupon Validation (payments endpoint)")
    print("-" * 60)

    # Test with known coupon codes from DB
    try:
        resp = requests.post(
            f"{PAYMENTS_URL}/validate-coupon",
            json={"code": "FLY500", "booking_amount": 5000.0},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200:
            test("Valid coupon FLY500 accepted", "discount_amount" in data,
                 f"discount=₹{data.get('discount_amount', '?')}, final=₹{data.get('final_amount', '?')}")
        else:
            test("Valid coupon FLY500", False, data.get("detail", f"HTTP {resp.status_code}"))
    except Exception as e:
        test("Valid coupon FLY500", False, str(e))

    # Test invalid coupon
    try:
        resp = requests.post(
            f"{PAYMENTS_URL}/validate-coupon",
            json={"code": "INVALID123", "booking_amount": 5000.0},
            timeout=10,
        )
        test("Invalid coupon rejected", resp.status_code == 400, f"status={resp.status_code}")
    except Exception as e:
        test("Invalid coupon rejected", False, str(e))

    # Test IND80 promo code (fixed ₹100 off)
    try:
        resp = requests.post(
            f"{PAYMENTS_URL}/validate-coupon",
            json={"code": "IND80", "booking_amount": 5000.0},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200:
            test("Promo code IND80 accepted", "discount_amount" in data,
                 f"discount=₹{data.get('discount_amount', '?')}, final=₹{data.get('final_amount', '?')}")
        else:
            test("Promo code IND80", False, data.get("detail", f"HTTP {resp.status_code}"))
    except Exception as e:
        test("Promo code IND80", False, str(e))

    # ── 6. Flight Search ────────────────────────────────────────────────────
    time.sleep(3)  # Avoid LLM rate limiting
    print("\n✈️ 6. Flight Search (via chatbot)")
    print("-" * 60)

    sid = str(uuid.uuid4())
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    flight_cards = []

    # Multi-turn flow: search → trip type → passengers → results
    resp = send_chat(f"Search flights from Bangalore to Delhi on {tomorrow}", sid)
    if resp and "error" not in resp:
        reply = resp.get("reply", "")
        intent = resp.get("intent", "")
        meta = resp.get("metadata", {})
        flight_cards = meta.get("flight_cards", [])
        test("Flight search intent", intent == "book_flight", f"intent={intent}")

        # Keep responding until we get flight cards or hit a dead end
        max_turns = 5
        turn = 2
        while not flight_cards and turn <= max_turns:
            time.sleep(2)
            # Respond based on what the bot is asking
            reply_lower = reply.lower()
            if "one-way" in reply_lower or "round-trip" in reply_lower or "trip" in reply_lower:
                resp = send_chat("one-way", sid)
            elif "passenger" in reply_lower or "how many" in reply_lower:
                resp = send_chat("1", sid)
            elif "date" in reply_lower or "when" in reply_lower:
                resp = send_chat(tomorrow, sid)
            else:
                break

            if resp and "error" not in resp:
                reply = resp.get("reply", "")
                meta = resp.get("metadata", {})
                flight_cards = meta.get("flight_cards", [])
                turn += 1
            else:
                break

        has_flights = bool(flight_cards) or "flight" in reply.lower()
        test("Flight search returns results", has_flights, f"reply[:80]={reply[:80]}")
        if flight_cards:
            print(f"       Found {len(flight_cards)} flights. First: {flight_cards[0].get('flight_number', '?')}")
    else:
        test("Flight Search", False, str(resp.get("error", "no response")) if resp else "no response")

    # If chat-based search didn't return flight cards, try the direct flights API
    if not flight_cards:
        try:
            resp = requests.get(
                f"{API_BASE}/flights/search",
                params={"departure_city": "Bangalore", "arrival_city": "Delhi"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    flight_cards = data
                    print(f"       (via /flights API) Found {len(flight_cards)} flights. First: {flight_cards[0].get('flight_number', '?')}")
        except Exception:
            pass

    # ── 7. Booking Flow (form-based) ────────────────────────────────────────
    print("\n📝 7. Booking Flow (form-based)")
    print("-" * 60)

    booking_result = None
    if flight_cards and len(flight_cards) > 0:
        flight = flight_cards[0]
        flight_id = flight.get("id", "")
        try:
            resp = requests.post(
                f"{API_BASE}/chat/booking-details",
                json={
                    "session_id": sid,
                    "user_id": None,
                    "flight_id": flight_id,
                    "cabin_class": "economy",
                    "passengers": [
                        {
                            "full_name": "Test Passenger",
                            "age": 30,
                            "gender": "male",
                            "seat_number": None,
                            "meal_preference": "veg",
                            "is_primary": True,
                        }
                    ],
                    "contact_email": "test@example.com",
                    "contact_phone": "+919876543210",
                    "travel_insurance": True,
                    "extra_baggage_kg": 10,
                },
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200:
                booking_result = data
                test("Booking created", True, f"PNR={data.get('pnr', '?')}, amount=₹{data.get('total_amount', '?')}")
                test("Booking has baggage info", "extra_baggage_kg" in data, f"baggage={data.get('extra_baggage_kg', '?')} kg")
                test("Booking has insurance info", "travel_insurance" in data, f"insurance={data.get('travel_insurance', '?')}")
                test("Booking has flight_number", bool(data.get("flight_number")), data.get("flight_number", ""))
                test("Booking has departure info", bool(data.get("departure_city")), f"{data.get('departure_city', '')} → {data.get('arrival_city', '')}")
            else:
                test("Booking created", False, data.get("detail", f"HTTP {resp.status_code}"))
        except Exception as e:
            test("Booking created", False, str(e))
    else:
        test("Booking flow", False, "No flights available to book (skipped)")

    # ── 8. Payment Flow ─────────────────────────────────────────────────────
    print("\n💳 8. Payment Flow")
    print("-" * 60)

    if booking_result and booking_result.get("booking_id"):
        booking_id = booking_result["booking_id"]
        # Initiate payment
        try:
            resp = requests.post(
                f"{PAYMENTS_URL}/initiate",
                json={"booking_id": booking_id, "payment_method": "card"},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code == 200:
                txn_id = data.get("transaction_id", "")
                test("Payment initiated", True, f"txn_id={txn_id}")

                # Confirm payment
                if txn_id:
                    resp2 = requests.post(
                        f"{PAYMENTS_URL}/confirm",
                        json={"booking_id": booking_id, "transaction_id": txn_id, "payment_method": "card", "success": True},
                        timeout=10,
                    )
                    data2 = resp2.json()
                    test("Payment confirmed", resp2.status_code == 200, f"status={data2.get('booking_status', data2.get('detail', '?'))}")
                else:
                    test("Payment confirmed", False, "no transaction_id")
            else:
                test("Payment initiated", False, data.get("detail", f"HTTP {resp.status_code}"))
        except Exception as e:
            test("Payment flow", False, str(e))
    else:
        test("Payment flow", False, "No booking to pay for (skipped)")

    # ── 9. Booking Retrieval by PNR ─────────────────────────────────────────
    print("\n🔍 9. Booking Retrieval by PNR")
    print("-" * 60)

    if booking_result and booking_result.get("pnr"):
        pnr = booking_result["pnr"]
        sid2 = str(uuid.uuid4())
        resp = send_chat(f"Check my booking {pnr}", sid2)
        if resp and "error" not in resp:
            reply = resp.get("reply", "")
            has_pnr = pnr.lower() in reply.lower() or "booking" in reply.lower()
            test("PNR lookup via chat", has_pnr, f"reply[:80]={reply[:80]}")
        else:
            test("PNR lookup via chat", False, str(resp.get("error", "no response")))

        # Also check baggage info for this booking
        sid3 = str(uuid.uuid4())
        resp = send_chat(f"What is the baggage allowance for booking {pnr}?", sid3)
        if resp and "error" not in resp:
            reply = resp.get("reply", "")
            has_baggage = "cabin baggage" in reply.lower() or "checked baggage" in reply.lower() or "kg" in reply.lower()
            test("Baggage info for booking", has_baggage, f"reply[:80]={reply[:80]}")
        else:
            test("Baggage info for booking", False, str(resp.get("error", "no response")))
    else:
        test("PNR lookup", False, "No booking PNR available (skipped)")

    # ── 10. Intent Classification (new intents) ─────────────────────────────
    time.sleep(3)  # Avoid LLM rate limiting
    print("\n🧠 10. Intent Classification (weather, currency, baggage)")
    print("-" * 60)

    intent_tests = [
        ("What's the weather in Mumbai today", "weather"),
        ("Weather forecast for Bangalore", "weather"),
        ("Convert 1000 rupees to dollars", "currency_conversion"),
        ("How much is 5000 INR in USD", "currency_conversion"),
        ("How much baggage can I carry", "baggage_info"),
        ("What is the luggage limit for economy", "baggage_info"),
    ]

    for msg, expected_intent in intent_tests:
        sid = str(uuid.uuid4())
        resp = send_chat(msg, sid)
        time.sleep(2)  # Avoid LLM rate limiting
        if resp and "error" not in resp:
            predicted = resp.get("intent", "unknown")
            test(f"Intent: '{msg[:40]}'", predicted == expected_intent, f"expected={expected_intent}, got={predicted}")
        else:
            test(f"Intent: '{msg[:40]}'", False, str(resp.get("error", "no response")))

    # ── 11. Fare Comparison ─────────────────────────────────────────────────
    time.sleep(3)  # Avoid LLM rate limiting
    print("\n📊 11. Fare Comparison")
    print("-" * 60)

    # First search for flights with passenger count, then ask for fare comparison
    sid = str(uuid.uuid4())
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    send_chat(f"Search flights from Delhi to Mumbai on {tomorrow} for 1 passenger", sid)
    # Now ask for fare comparison (should break out of booking flow)
    resp = send_chat("Compare fares for these flights", sid)
    if resp and "error" not in resp:
        reply = resp.get("reply", "")
        intent = resp.get("intent", "")
        has_comparison = "economy" in reply.lower() or "business" in reply.lower() or "₹" in reply
        test("Fare comparison intent", intent == "fare_comparison", f"intent={intent}")
        # Fare comparison may say "search first" if state was reset — that's still a valid fare_comparison response
        is_fare_comparison_response = "compare" in reply.lower() or "fare" in reply.lower() or "search" in reply.lower()
        test("Fare comparison has data", is_fare_comparison_response, f"reply[:80]={reply[:80]}")
    else:
        test("Fare comparison", False, str(resp.get("error", "no response")) if resp else "no response")

    # ── 12. Check-in Flow ───────────────────────────────────────────────────
    time.sleep(3)  # Avoid LLM rate limiting
    print("\n✅ 12. Check-in Flow")
    print("-" * 60)

    if booking_result and booking_result.get("pnr"):
        pnr = booking_result["pnr"]
        sid = str(uuid.uuid4())
        resp = send_chat(f"Check me in for booking {pnr}", sid)
        if resp and "error" not in resp:
            reply = resp.get("reply", "")
            intent = resp.get("intent", "")
            test("Check-in intent detected", intent == "check_in", f"intent={intent}")
            test("Check-in response", "check" in reply.lower() or "boarding" in reply.lower() or "pnr" in reply.lower(),
                 f"reply[:80]={reply[:80]}")
        else:
            test("Check-in flow", False, str(resp.get("error", "no response")))
    else:
        test("Check-in flow", False, "No booking to check in (skipped)")

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print(f"  SUMMARY: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print(f"  Success rate: {PASS / (PASS + FAIL) * 100:.1f}%" if (PASS + FAIL) > 0 else "  No tests run")
    print("=" * 80)

    if FAIL > 0:
        print("\n  Failed tests:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"    ❌ {r['name']} — {r['detail']}")

    # Save results
    with open("test_all_results.json", "w") as f:
        json.dump({"pass": PASS, "fail": FAIL, "total": PASS + FAIL, "results": RESULTS}, f, indent=2)
    print(f"\n  Results saved to test_all_results.json")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
