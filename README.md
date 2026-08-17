# SkyBook AI ✈️ — Airline Ticket Reservation Chatbot

> Enterprise-level airline reservation chatbot powered by **LangGraph** with 100% free-tier services.

## Quick Start

```bash
# 1. Setup
cd airline-chatbot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — add your free Gemini API key from https://aistudio.google.com/apikey

# 3. Run
python main.py

# 4. Open
# http://localhost:8000
```

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@skybook.ai | admin123 |
| User | john@example.com | user123 |
| Demo PNR | DEMO01 | — |

## Try These Commands

- "I need a flight from Bangalore to Delhi tomorrow"
- "Check SB101 status"
- "Check-in for DEMO01"
- "Cancel booking DEMO01"
- "Where is my refund for DEMO01?"
- "Baggage information"
- "I want to talk to a human agent"

## Tech Stack

- **AI**: LangGraph + Google Gemini (free tier) / Groq (free tier)
- **Backend**: FastAPI + SQLAlchemy + SQLite
- **Frontend**: HTML/CSS/JS (no build step)
- **Auth**: JWT + bcrypt
- **External APIs**: Open-Meteo (weather), open.er-api.com (currency) — all free

## Documentation

- [Architecture & Technology Details](ARCHITECTURE.md)
- [API Docs](http://localhost:8000/api/docs) (available when running)

## Project Structure

```
airline-chatbot/
├── main.py              # FastAPI app
├── config.py            # Settings
├── database.py          # DB setup
├── models.py            # 13 ORM models
├── schemas.py           # Pydantic schemas
├── auth.py              # JWT auth
├── seed_data.py         # Sample data
├── chatbot/             # LangGraph workflow
│   ├── state.py         # Chat state
│   ├── llm.py           # LLM provider
│   ├── prompts.py       # Prompt templates
│   ├── tools.py         # Tool functions
│   ├── nodes.py         # Intent handlers
│   └── graph.py         # Graph workflow
├── routers/             # API routes
│   ├── auth.py          # Auth endpoints
│   ├── flights.py       # Flight endpoints
│   ├── bookings.py      # Booking endpoints
│   ├── payments.py      # Payment endpoints
│   ├── notifications.py # Notification endpoints
│   ├── admin.py         # Admin endpoints
│   └── chat.py          # Chatbot endpoints
└── frontend/            # Chat UI
    ├── index.html
    └── static/
        ├── css/style.css
        └── js/app.js
```

## Docker

```bash
docker build -t skybook-ai .
docker run -p 8000:8000 --env-file .env skybook-ai
```
