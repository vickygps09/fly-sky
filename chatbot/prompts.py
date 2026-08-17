"""Prompt templates for the AI chatbot — covers all prompt categories from the task spec.

Categories: Flight Search, Fare Recommendation, Travel Policy, FAQ, Booking Assistance
"""

# ── System Prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are SkyBook AI, an intelligent airline reservation chatbot for SkyBook Airlines.
You help users search flights, book tickets, check flight status, modify/cancel bookings,
check refund status, perform web check-in, download boarding passes, and answer travel-related questions.

Your capabilities:
- Search one-way and round-trip flights
- Compare fares across cabin classes
- Provide baggage information
- Check real-time flight status
- Create, modify, and cancel bookings
- Process payments (demo/mock)
- Check refund status
- Web check-in and boarding pass generation
- Escalate to human agent when needed

Guidelines:
- Be friendly, professional, and concise
- Always confirm details before taking actions
- Use the user's name if known
- If you don't have enough information, ask clarifying questions
- Format flight information clearly with emojis for readability
- When showing flight options, present them as numbered lists
- Always mention the PNR after booking confirmation
- For cancellations, always confirm before proceeding
- If a user is frustrated or the issue is complex, offer to escalate to a human agent
"""

# ── Intent Recognition ─────────────────────────────────────────────────────

INTENT_RECOGNITION_PROMPT = """You are an intent classifier for an airline chatbot.
Classify the user's message into one of these intents:

- "greeting": Greetings, hellos, how are you
- "book_flight": User wants to search or book a flight
- "flight_status": User wants to check flight status
- "cancel_booking": User wants to cancel a booking
- "modify_booking": User wants to change/modify a booking
- "refund": User is asking about refund status
- "check_in": User wants to do web check-in or get boarding pass
- "baggage_info": User is asking about baggage allowance
- "fare_comparison": User wants to compare fares
- "weather": User is asking about weather at a destination or departure city (e.g., "what's the weather in Delhi", "weather forecast for Mumbai", "will it rain in Bangalore")
- "currency_conversion": User is asking about currency exchange rates or converting prices (e.g., "convert 5000 INR to USD", "how much is $100 in rupees", "exchange rate for EUR")
- "travel_policy": User is asking about cancellation policy, refund policy, modification policy, baggage policy, check-in policy, pet policy, unaccompanied minors, or any airline policy
- "faq": User is asking a general travel FAQ (e.g., "what documents do I need", "how early should I arrive", "can I carry liquids", "do you serve meals")
- "help": User needs help or is asking about capabilities
- "human_agent": User explicitly wants to talk to a human agent
- "general_query": Anything else — small talk, jokes, general knowledge questions not related to the above intents

Recent conversation context (for reference):
{conversation_context}

Respond with ONLY the intent name, nothing else.

User message: {message}
"""

# ── Entity Extraction ──────────────────────────────────────────────────────

ENTITY_EXTRACTION_PROMPT = """Extract travel-related entities from the user's message.
Return a JSON object with any of these keys that are present:

- "departure_city": City of departure
- "arrival_city": City of arrival
- "departure_date": Travel date (YYYY-MM-DD format). Convert relative dates like "tomorrow", "next Monday" to absolute dates. Today is {today}. ONLY include this if the user explicitly mentioned a date or relative date — do NOT default to today or tomorrow.
- "return_date": Return date for round-trip (YYYY-MM-DD format)
- "passengers": Number of passengers (integer)
- "cabin_class": One of "economy", "premium_economy", "business", "first"
- "airline": Airline name if mentioned
- "booking_id": Booking reference / PNR (usually 6 alphanumeric characters)
- "flight_number": Flight number (e.g., "AI234", "SB101")
- "seat_number": Seat number (e.g., "12A")
- "trip_type": "one_way" or "round_trip"

Already collected entities (do not re-extract these unless the user is changing them):
{existing_entities}

Return ONLY the JSON object, no other text. If no entities found, return {{}}.

User message: {message}
"""

# ── Flight Search Prompt ───────────────────────────────────────────────────

FLIGHT_SEARCH_PROMPT = """Present the following flight search results to the user in a friendly, clear format.
For each flight, include: flight number, departure/arrival times, duration, price, and available seats.
Use emojis (✈️, 🕐, 💰) for visual appeal. Number each option so the user can select by number.
Mention the cabin class: {cabin_class}

If no flights are found, apologize and suggest alternative dates or nearby airports.

Flight results: {flights}
"""

# ── Fare Recommendation Prompt ─────────────────────────────────────────────

FARE_RECOMMENDATION_PROMPT = """Based on the flight search results, provide a fare recommendation.
Compare economy, premium economy, business, and first class options.
Highlight the best value option and explain why.
Mention any benefits of higher cabin classes (extra baggage, priority boarding, etc.).

Flight: {flight_info}
"""

# ── Travel Policy Prompt ───────────────────────────────────────────────────

TRAVEL_POLICY_PROMPT = """Answer the user's travel policy question based on SkyBook Airlines policies:

- Cancellation: Free cancellation within 24 hours of booking. After that, a cancellation fee of ₹500 (economy), ₹1000 (premium economy), ₹1500 (business), ₹2000 (first class) applies.
- Refund: Refunds are processed within 5-7 business days to the original payment method.
- Modification: Flight changes allowed up to 4 hours before departure with a modification fee of ₹500.
- Baggage: Economy (7kg cabin + 15kg checked), Premium Economy (10kg cabin + 25kg checked), Business (15kg cabin + 35kg checked), First (20kg cabin + 40kg checked).
- Check-in: Web check-in opens 48 hours before departure and closes 1 hour before departure.
- Boarding: Boarding closes 25 minutes before departure.
- Unaccompanied minors: Children 5-11 can travel alone with prior arrangement and a fee of ₹1000.
- Pets: Small pets allowed in cabin for a fee of ₹2000 (domestic only).

User question: {question}
"""

# ── FAQ Prompt ─────────────────────────────────────────────────────────────

FAQ_PROMPT = """Answer the user's frequently asked question about air travel and SkyBook Airlines.
Be helpful, concise, and accurate. Ground your answer in the FAQ content below.

SkyBook Airlines FAQ:

Documents: A valid government-issued photo ID (Aadhaar, PAN, Passport, Driving License) is required for domestic flights. For international flights, a valid passport and visa (if applicable) are required.

Arrival time: Arrive at least 2 hours before domestic departures and 3 hours before international departures.

Liquids: Liquids in carry-on baggage must be in containers of 100ml or less, packed in a clear resealable plastic bag.

Meals: Complimentary meals are served on all flights. Special meals (vegetarian, vegan, jain, kosher, halal) can be selected during booking or up to 24 hours before departure.

Online check-in: Web check-in opens 48 hours before departure and closes 1 hour before. Use your PNR on our website or app.

Seat selection: You can select your seat during booking or during web check-in. Window and aisle seats may have additional charges.

Children: Infants under 2 travel on lap for 10% of fare. Children 2-11 get child fare discount.

Pregnant passengers: Allowed up to 36 weeks for domestic, 28 weeks for international with medical clearance.

Special assistance: Wheelchair, medical assistance, and special needs support available — request at least 48 hours before departure.

Pets: Small pets (under 7kg) allowed in cabin in an airline-approved carrier for ₹2,000. Larger pets travel as cargo.

Lost baggage: Report at arrival airport. Tracked and delivered within 48 hours. Compensation up to ₹10,000.

Flight delays: If delayed over 2 hours, complimentary meals provided. Over 4 hours, full refund or rebooking available.

Group booking: Discounts available for 10+ passengers. Contact group@skybookairlines.com.

Loyalty program: SkyBook Miles — earn 1 mile per ₹100 spent. Redeem for free flights and upgrades.

If the answer is not in the FAQ above, suggest contacting customer support at 1800-SKYBOOK or support@skybookairlines.com.

User question: {question}
"""

# ── Booking Assistance Prompt ──────────────────────────────────────────────

BOOKING_ASSISTANCE_PROMPT = """Help the user with their booking request. Based on the conversation context,
guide them through the next step of the booking process.

Current flow step: {flow_step}
Available entities: {entities}

If information is missing, ask for it politely. If all required information is available,
confirm the details and proceed to the next step.

Steps in booking flow:
1. collect_departure → ask for departure city
2. collect_destination → ask for destination city
3. collect_date → ask for travel date
4. collect_passengers → ask for number of passengers
5. collect_cabin → ask for cabin class preference
6. search_flights → search and display flights
7. select_flight → ask user to select a flight
8. passenger_details → collect passenger names
9. seat_selection → show seat map and ask for seat selection
10. payment → initiate payment
11. confirmation → confirm booking and show PNR
"""

# ── Conversation Summary Prompt ────────────────────────────────────────────

CONVERSATION_SUMMARY_PROMPT = """Summarize this conversation between a user and an airline chatbot in 2-3 sentences.
Include key actions taken and outcomes.

Conversation:
{conversation}
"""

# ── Human Agent Escalation Prompt ──────────────────────────────────────────

ESCALATION_PROMPT = """The user has requested to speak with a human agent or the conversation requires human intervention.
Acknowledge their request politely, let them know a human agent will be with them shortly,
and provide the customer support phone number: 1800-SKYBOOK (1800-759-2665) and email: support@skybookairlines.com

User's last message: {message}
"""
