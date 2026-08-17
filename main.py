"""SkyBook AI — Airline Ticket Reservation Chatbot

Main FastAPI application that ties together:
- Auth (registration, login, guest, OTP)
- Flights (search, seats, status, baggage)
- Bookings (create, modify, cancel, check-in, boarding pass)
- Payments (initiate, confirm, refund)
- Notifications (SMS, Email, WhatsApp — mock)
- Admin (dashboard, manage flights/bookings/refunds/users, chat history, analytics)
- Chatbot (LangGraph-powered AI assistant via REST + WebSocket)
- Frontend (chat UI served as static files)
"""

import os
import logging
import json
import time
from collections import defaultdict
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db, get_db
from routers import auth, flights, bookings, payments, notifications, admin, chat, external
from auth import require_admin
import models


# ── In-Memory Stats Tracker ─────────────────────────────────────────────────
class StatsTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.api_stats = defaultdict(lambda: {"total": 0, "success": 0, "failure": 0, "errors": []})
        self.llm_calls = {"total": 0, "success": 0, "failure": 0, "timeouts": 0}
        self.rag_retrieval = {"total": 0, "success": 0, "failure": 0}
        self.start_time = time.time()

    def record_api(self, path: str, status_code: int):
        s = self.api_stats[path]
        s["total"] += 1
        if status_code < 400:
            s["success"] += 1
        else:
            s["failure"] += 1
            if len(s["errors"]) < 20:
                s["errors"].append({"status": status_code, "time": time.strftime("%Y-%m-%d %H:%M:%S")})

    def record_llm(self, success: bool, timeout: bool = False):
        self.llm_calls["total"] += 1
        if timeout:
            self.llm_calls["timeouts"] += 1
        if success:
            self.llm_calls["success"] += 1
        else:
            self.llm_calls["failure"] += 1

    def record_rag(self, success: bool):
        self.rag_retrieval["total"] += 1
        if success:
            self.rag_retrieval["success"] += 1
        else:
            self.rag_retrieval["failure"] += 1

    def snapshot(self) -> dict:
        total_req = sum(s["total"] for s in self.api_stats.values())
        total_success = sum(s["success"] for s in self.api_stats.values())
        total_fail = sum(s["failure"] for s in self.api_stats.values())
        return {
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "api": {
                "total_requests": total_req,
                "total_success": total_success,
                "total_failure": total_fail,
                "availability": round(total_success / total_req * 100, 2) if total_req > 0 else 100.0,
                "per_endpoint": {k: dict(v) for k, v in self.api_stats.items()},
            },
            "llm": dict(self.llm_calls),
            "rag_retrieval": dict(self.rag_retrieval),
        }


stats_tracker = StatsTracker()

# ── Structured Logging ──────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production monitoring."""
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry)

logger = logging.getLogger("skybook")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Airline Ticket Reservation Chatbot powered by LangGraph",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ──────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing and request ID."""
    import uuid as _uuid
    request_id = str(_uuid.uuid4())[:8]
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    stats_tracker.record_api(request.url.path, response.status_code)
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {duration_ms}ms",
        extra={"request_id": request_id},
    )
    response.headers["X-Request-ID"] = request_id
    return response

# ── Register Routers ───────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(flights.router)
app.include_router(bookings.router)
app.include_router(payments.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(external.router)


# ── Static Frontend ────────────────────────────────────────────────────────

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the chat UI."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    return "<h1>SkyBook AI</h1><p>Frontend not found. Run from project root.</p>"


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Serve the admin dashboard."""
    admin_path = os.path.join(frontend_dir, "admin.html")
    if os.path.exists(admin_path):
        with open(admin_path, "r") as f:
            return f.read()
    return "<h1>SkyBook AI Admin</h1><p>Admin page not found.</p>"


# ── Health Check & Monitoring ───────────────────────────────────────────────

import psutil
import platform

_start_time = time.time()

@app.get("/api/health")
def health():
    """Basic health check."""
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/api/health/detailed")
def health_detailed():
    """Detailed health check with system metrics and dependency status."""
    db_ok = False
    try:
        db = next(get_db())
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
        db.close()
    except Exception:
        db_ok = False

    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()

    return {
        "status": "healthy" if db_ok else "degraded",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _start_time, 2),
        "dependencies": {
            "database": "connected" if db_ok else "disconnected",
            "llm_provider": settings.LLM_PROVIDER,
        },
        "system": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cpu_percent": cpu_percent,
            "memory_total_mb": round(mem.total / 1024 / 1024, 2),
            "memory_used_mb": round(mem.used / 1024 / 1024, 2),
            "memory_percent": mem.percent,
        },
    }


@app.get("/api/metrics")
def app_metrics():
    """Application-level metrics for monitoring dashboards."""
    db = next(get_db())
    try:
        import models as M
        from sqlalchemy import func as sql_func

        total_bookings = db.query(M.Booking).count()
        confirmed = db.query(M.Booking).filter(M.Booking.booking_status == M.BookingStatus.CONFIRMED).count()
        pending = db.query(M.Booking).filter(M.Booking.booking_status == M.BookingStatus.PENDING).count()
        cancelled = db.query(M.Booking).filter(M.Booking.booking_status == M.BookingStatus.CANCELLED).count()
        active_flights = db.query(M.Flight).filter(M.Flight.is_active == True).count()
        total_users = db.query(M.User).count()
        total_conversations = db.query(M.Conversation).count()
        total_revenue = db.query(sql_func.sum(M.Transaction.amount)).filter(
            M.Transaction.payment_status == M.PaymentStatus.SUCCESS
        ).scalar() or 0.0
        csat_avg = db.query(sql_func.avg(M.CSAT.rating)).scalar() or 0.0
        csat_count = db.query(M.CSAT).count()

        return {
            "bookings": {
                "total": total_bookings,
                "confirmed": confirmed,
                "pending": pending,
                "cancelled": cancelled,
            },
            "flights": {"active": active_flights},
            "users": {"total": total_users},
            "conversations": {"total": total_conversations},
            "revenue": {"total": round(total_revenue, 2)},
            "csat": {"average": round(csat_avg, 2), "count": csat_count},
            "uptime_seconds": round(time.time() - _start_time, 2),
        }
    finally:
        db.close()


@app.get("/api/admin/api-stats")
def api_stats(admin: models.User = Depends(require_admin)):
    """API availability, failure rates, LLM call stats, and RAG retrieval stats."""
    return stats_tracker.snapshot()


@app.get("/api/admin/ai-metrics")
def ai_metrics(admin: models.User = Depends(require_admin)):
    """Run AI evaluation: F1, precision, recall, accuracy, hallucination detection."""
    import threading
    from evaluate import (
        INTENT_TEST_CASES, ENTITY_TEST_CASES, RAG_TEST_CASES,
        compute_prf, evaluate_rag, evaluate_route_extraction,
    )
    from chatbot.nodes import intent_recognition, entity_extraction
    from chatbot.state import ChatState
    from langchain_core.messages import HumanMessage
    from chatbot.rag import city_retriever
    from collections import defaultdict

    # ── Intent Recognition ──
    per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    intent_correct = 0
    intent_total = len(INTENT_TEST_CASES)
    intent_results = []

    for message, expected in INTENT_TEST_CASES:
        state = ChatState(
            messages=[HumanMessage(content=message)],
            intent=None, entities={}, flow_step=None,
            session_id="eval", user_id=None,
            conversation_history=[], conversation_summary=None,
            search_results=None, selected_flight=None,
            pending_booking=None, booking_result=None,
            response="", response_metadata=None,
            escalated=False, db_session=None,
        )
        state = intent_recognition(state)
        predicted = state.get("intent", "unknown")
        match = predicted == expected
        if match:
            intent_correct += 1
            per_class[expected]["tp"] += 1
        else:
            per_class[expected]["fn"] += 1
            per_class[predicted]["fp"] += 1
        intent_results.append({"message": message, "expected": expected, "predicted": predicted, "pass": match})

    intent_class_metrics = {}
    all_p, all_r, all_f = [], [], []
    for cls in sorted(per_class.keys()):
        m = compute_prf(per_class[cls]["tp"], per_class[cls]["fp"], per_class[cls]["fn"])
        intent_class_metrics[cls] = m
        all_p.append(m["precision"])
        all_r.append(m["recall"])
        all_f.append(m["f1"])

    intent_metrics = {
        "accuracy": round(intent_correct / intent_total, 4),
        "macro_precision": round(sum(all_p) / len(all_p), 4) if all_p else 0,
        "macro_recall": round(sum(all_r) / len(all_r), 4) if all_r else 0,
        "macro_f1": round(sum(all_f) / len(all_f), 4) if all_f else 0,
        "per_class": intent_class_metrics,
        "total": intent_total,
        "correct": intent_correct,
        "results": intent_results,
    }

    # ── Entity Extraction ──
    ent_per_field = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    ent_correct = 0
    ent_total = len(ENTITY_TEST_CASES)
    ent_results = []

    for message, expected in ENTITY_TEST_CASES:
        state = ChatState(
            messages=[HumanMessage(content=message)],
            intent="book_flight", entities={}, flow_step=None,
            session_id="eval", user_id=None,
            conversation_history=[], conversation_summary=None,
            search_results=None, selected_flight=None,
            pending_booking=None, booking_result=None,
            response="", response_metadata=None,
            escalated=False, db_session=None,
        )
        state = entity_extraction(state)
        predicted = state.get("entities", {})
        all_match = True
        for field, expected_val in expected.items():
            pred_val = predicted.get(field)
            if isinstance(expected_val, str):
                match = pred_val and pred_val.lower() == expected_val.lower()
            else:
                match = pred_val == expected_val
            if match:
                ent_per_field[field]["tp"] += 1
            else:
                ent_per_field[field]["fn"] += 1
                if pred_val is not None:
                    ent_per_field[field]["fp"] += 1
                all_match = False
        if all_match:
            ent_correct += 1
        ent_results.append({"message": message, "expected": expected, "predicted": predicted, "pass": all_match})

    ent_field_metrics = {}
    ep, er, ef = [], [], []
    for field in sorted(ent_per_field.keys()):
        m = compute_prf(ent_per_field[field]["tp"], ent_per_field[field]["fp"], ent_per_field[field]["fn"])
        ent_field_metrics[field] = m
        ep.append(m["precision"])
        er.append(m["recall"])
        ef.append(m["f1"])

    entity_metrics = {
        "accuracy": round(ent_correct / ent_total, 4),
        "macro_precision": round(sum(ep) / len(ep), 4) if ep else 0,
        "macro_recall": round(sum(er) / len(er), 4) if er else 0,
        "macro_f1": round(sum(ef) / len(ef), 4) if ef else 0,
        "per_field": ent_field_metrics,
        "total": ent_total,
        "correct": ent_correct,
        "results": ent_results,
    }

    # ── RAG Retrieval ──
    rag_results = evaluate_rag()
    route_results = evaluate_route_extraction()

    # ── Hallucination Detection ──
    city_retriever.load_from_db()
    hallucination_cases = [
        "xyz", "foobar", "nonexistent", "qqqqq", "zzzzz",
        "fakecity", "nowhere", "nulltown", "imagination", "gibberish",
    ]
    hallucination_count = 0
    hallucination_details = []
    for query in hallucination_cases:
        result = city_retriever.retrieve(query)
        if result:
            hallucination_count += 1
            hallucination_details.append({"query": query, "matched": result["city"], "confidence": result["confidence"]})

    hallucination_metrics = {
        "total_tested": len(hallucination_cases),
        "hallucinations_detected": hallucination_count,
        "hallucination_rate": round(hallucination_count / len(hallucination_cases), 4),
        "details": hallucination_details,
    }

    return {
        "intent_recognition": intent_metrics,
        "entity_extraction": entity_metrics,
        "rag_retrieval": rag_results,
        "route_extraction": route_results,
        "hallucination": hallucination_metrics,
    }


# ── Startup Event ──────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    """Initialize database and seed data on startup."""
    init_db()

    # Migration: add latitude/longitude columns to airports table if missing
    db = next(get_db())
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)

        # Airports table
        ap_cols = [c["name"] for c in inspector.get_columns("airports")]
        if "latitude" not in ap_cols:
            db.execute(text("ALTER TABLE airports ADD COLUMN latitude FLOAT"))
            print("✅ Added latitude column to airports")
        if "longitude" not in ap_cols:
            db.execute(text("ALTER TABLE airports ADD COLUMN longitude FLOAT"))
            print("✅ Added longitude column to airports")

        # Flights table
        fl_cols = [c["name"] for c in inspector.get_columns("flights")]
        if "cabin_baggage_kg" not in fl_cols:
            db.execute(text("ALTER TABLE flights ADD COLUMN cabin_baggage_kg FLOAT DEFAULT 7.0"))
            print("✅ Added cabin_baggage_kg column to flights")
        if "checked_baggage_kg" not in fl_cols:
            db.execute(text("ALTER TABLE flights ADD COLUMN checked_baggage_kg FLOAT DEFAULT 15.0"))
            print("✅ Added checked_baggage_kg column to flights")

        db.commit()
    except Exception as e:
        print(f"ℹ️  Migration check: {e}")
        db.rollback()
    finally:
        db.close()

    # Seed data if database is empty
    db = next(get_db())
    try:
        import models as M
        if db.query(M.Airport).count() == 0:
            try:
                from seed_data import seed_database
                seed_database(db)
                print("✅ Database seeded with sample data")
            except Exception as seed_err:
                db.rollback()
                print(f"⚠️  Seed error (non-fatal): {seed_err}")
        else:
            print("ℹ️  Database already has data, skipping seed")
            # Migration: add coordinates to existing airports if missing
            coords_map = {
                "BLR": (13.1986, 77.7066), "DEL": (28.5562, 77.1000),
                "BOM": (19.0896, 72.8656), "MAA": (12.9941, 80.1709),
                "HYD": (17.2403, 78.4294), "CCU": (22.6547, 88.4467),
                "GOI": (15.3808, 73.8314), "COK": (10.1520, 76.4019),
                "JAI": (26.8242, 75.8122), "AMD": (23.0772, 72.6347),
            }
            updated = 0
            for airport in db.query(M.Airport).all():
                if airport.latitude is None and airport.code in coords_map:
                    lat, lon = coords_map[airport.code]
                    airport.latitude = lat
                    airport.longitude = lon
                    updated += 1
            if updated:
                db.commit()
                print(f"✅ Updated {updated} airports with coordinates")
    finally:
        db.close()


# ── Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
