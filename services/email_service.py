"""Email Service — Supports SMTP and Resend (free tier).

If SMTP credentials are configured, sends via SMTP.
If RESEND_API_KEY is set, sends via Resend API (free: 3000 emails/month).
Otherwise, falls back to console logging (mock mode).
"""
import smtplib
import ssl
import json
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from config import settings


def _build_html_email(subject: str, body: str) -> str:
    """Build a styled HTML email body."""
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Inter', -apple-system, sans-serif; background: #f0f2f5; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: linear-gradient(135deg, #1a1a2e, #0f3460); padding: 24px; text-align: center; }}
  .header h1 {{ color: #fff; margin: 0; font-size: 1.5rem; }}
  .header p {{ color: rgba(255,255,255,0.7); margin: 4px 0 0; font-size: 0.85rem; }}
  .content {{ padding: 32px; }}
  .content h2 {{ color: #1a1a2e; margin: 0 0 16px; }}
  .content p {{ color: #374151; line-height: 1.6; margin: 8px 0; }}
  .info-box {{ background: #f3f4f6; border-radius: 8px; padding: 16px; margin: 16px 0; }}
  .info-box .label {{ color: #6b7280; font-size: 0.8rem; text-transform: uppercase; }}
  .info-box .value {{ color: #1a1a2e; font-weight: 600; font-size: 1.1rem; }}
  .btn {{ display: inline-block; background: #4f46e5; color: #fff; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
  .footer {{ text-align: center; padding: 16px; color: #9ca3af; font-size: 0.8rem; }}
  .footer a {{ color: #4f46e5; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>✈️ SkyBook AI</h1>
      <p>Your Intelligent Airline Assistant</p>
    </div>
    <div class="content">
      <h2>{subject}</h2>
      <p>{body}</p>
    </div>
    <div class="footer">
      <p>This is an automated message from SkyBook AI. Please do not reply.</p>
      <p>© 2025 SkyBook Airlines · <a href="mailto:support@skybookairlines.com">support@skybookairlines.com</a></p>
    </div>
  </div>
</body>
</html>"""


def _build_ticket_html(
    pnr: str,
    flight_number: str,
    airline_name: str,
    departure_city: str,
    departure_code: str,
    arrival_city: str,
    arrival_code: str,
    departure_time: str,
    arrival_time: str,
    duration_minutes: int,
    passenger_name: str,
    cabin_class: str,
    total_amount: float,
    passengers: list = None,
    booking_date: str = "",
) -> str:
    """Build an IndiGo-style booking confirmation HTML email."""
    duration_h = duration_minutes // 60
    duration_m = duration_minutes % 60
    passengers = passengers or []
    num_pax = len(passengers) if passengers else 1

    base_fare = total_amount * 0.75
    taxes_fees = total_amount * 0.25

    passenger_rows = ""
    for p in passengers:
        seat = p.get("seat_number") or "—"
        passenger_rows += f"""<tr>
            <td style="padding: 10px 16px; border-bottom: 1px solid #eee; font-size: 14px;">{p.get("full_name", "")}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #eee; font-size: 14px; text-align: center;">{p.get("age", "—")}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #eee; font-size: 14px; text-align: center;">{p.get("gender", "—")}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #eee; font-size: 14px; text-align: center; font-weight: 600;">{seat}</td>
          </tr>"""

    if not passenger_rows:
        passenger_rows = f"""<tr>
            <td style="padding: 10px 16px; font-size: 14px;">{passenger_name}</td>
            <td style="padding: 10px 16px; font-size: 14px; text-align: center;">—</td>
            <td style="padding: 10px 16px; font-size: 14px; text-align: center;">—</td>
            <td style="padding: 10px 16px; font-size: 14px; text-align: center; font-weight: 600;">—</td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: 'Segoe UI', Arial, Helvetica, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
  .email-container {{ max-width: 580px; margin: 0 auto; background: #fff; }}

  /* Header */
  .header {{ background: #0066b3; padding: 18px 24px; }}
  .header .logo {{ color: #fff; font-size: 24px; font-weight: 800; }}
  .header .logo span {{ color: #ff6600; }}
  .header .tagline {{ color: #b3d1e8; font-size: 12px; margin-top: 2px; }}

  /* PNR Section */
  .pnr-section {{ padding: 20px 24px; border-bottom: 1px solid #e0e0e0; }}
  .pnr-section .pnr-row {{ display: flex; justify-content: space-between; align-items: center; }}
  .pnr-section .pnr-label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }}
  .pnr-section .pnr-value {{ font-size: 24px; font-weight: 800; color: #0066b3; font-family: 'Courier New', monospace; letter-spacing: 1px; }}
  .pnr-section .status-badge {{ background: #00875a; color: #fff; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 3px; }}
  .pnr-section .payment-status {{ font-size: 13px; color: #666; margin-top: 8px; }}
  .pnr-section .payment-status strong {{ color: #00875a; }}

  /* Section heading */
  .section-heading {{
    background: #f8f8f8;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: 700;
    color: #0066b3;
    border-bottom: 2px solid #0066b3;
    border-top: 1px solid #e0e0e0;
  }}

  /* Flight card */
  .flight-card {{ padding: 20px 24px; border-bottom: 1px solid #e0e0e0; }}
  .flight-route {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }}
  .flight-point {{ text-align: center; flex: 1; }}
  .flight-point .code {{ font-size: 28px; font-weight: 800; color: #333; }}
  .flight-point .city {{ font-size: 12px; color: #888; margin-top: 2px; }}
  .flight-point .time {{ font-size: 13px; color: #333; margin-top: 4px; }}
  .flight-arrow {{ flex: 1; text-align: center; }}
  .flight-arrow .line {{ height: 1px; background: #ccc; position: relative; margin: 0 12px; }}
  .flight-arrow .line::before {{ content: '✈'; position: absolute; top: -10px; left: 50%; transform: translateX(-50%); font-size: 16px; }}
  .flight-arrow .dur {{ font-size: 11px; color: #999; margin-top: 8px; }}

  .flight-details-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  .flight-details-table td {{ padding: 8px 12px; font-size: 13px; border: 1px solid #e8e8e8; }}
  .flight-details-table .lbl {{ background: #fafafa; color: #666; font-weight: 600; width: 30%; }}

  /* Passenger table */
  .passenger-section {{ padding: 16px 24px; border-bottom: 1px solid #e0e0e0; }}
  .passenger-table {{ width: 100%; border-collapse: collapse; }}
  .passenger-table th {{ background: #0066b3; color: #fff; padding: 10px 16px; font-size: 12px; text-transform: uppercase; text-align: left; }}
  .passenger-table th.center {{ text-align: center; }}

  /* Fare section */
  .fare-section {{ padding: 16px 24px; border-bottom: 1px solid #e0e0e0; }}
  .fare-table {{ width: 100%; border-collapse: collapse; }}
  .fare-table td {{ padding: 9px 0; font-size: 14px; border-bottom: 1px solid #f0f0f0; }}
  .fare-table .lbl {{ color: #555; }}
  .fare-table .amt {{ text-align: right; font-weight: 600; color: #333; }}
  .fare-table .total-row td {{ border-top: 2px solid #0066b3; border-bottom: none; padding-top: 12px; }}
  .fare-table .total-row .lbl {{ font-size: 15px; font-weight: 700; color: #0066b3; }}
  .fare-table .total-row .amt {{ font-size: 18px; font-weight: 800; color: #0066b3; }}

  /* Contact details */
  .contact-section {{ padding: 16px 24px; border-bottom: 1px solid #e0e0e0; }}
  .contact-section .contact-row {{ font-size: 13px; color: #555; margin: 4px 0; }}
  .contact-section .contact-row strong {{ color: #333; }}

  /* Important info */
  .info-section {{ padding: 16px 24px; background: #fffde7; border-bottom: 1px solid #e0e0e0; }}
  .info-section p {{ font-size: 12px; color: #666; line-height: 1.7; margin: 6px 0; }}
  .info-section p strong {{ color: #333; }}

  /* Footer */
  .footer {{ padding: 20px 24px; text-align: center; background: #f8f8f8; }}
  .footer p {{ font-size: 11px; color: #999; margin: 4px 0; line-height: 1.6; }}
  .footer a {{ color: #0066b3; text-decoration: none; }}
  .footer .links a {{ display: inline-block; margin: 0 6px; }}

  @media (max-width: 480px) {{
    .flight-route {{ flex-direction: column; gap: 12px; }}
    .flight-arrow .line {{ width: 100%; }}
    .pnr-section .pnr-row {{ flex-direction: column; gap: 8px; align-items: flex-start; }}
  }}
</style>
</head>
<body>
  <div class="email-container">

    <!-- Header -->
    <div class="header">
      <div class="logo">Sky<span>Book</span> AI</div>
      <div class="tagline">Your Intelligent Airline Assistant</div>
    </div>

    <!-- PNR / Booking Reference -->
    <div class="pnr-section">
      <div class="pnr-row">
        <div>
          <div class="pnr-label">PNR / Booking Reference</div>
          <div class="pnr-value">{pnr}</div>
        </div>
        <div class="status-badge">CONFIRMED</div>
      </div>
      <div class="payment-status">Payment Status: <strong>Complete</strong></div>
    </div>

    <!-- Flight Summary -->
    <div class="section-heading">Flight Summary</div>
    <div class="flight-card">
      <div class="flight-route">
        <div class="flight-point">
          <div class="code">{departure_code}</div>
          <div class="city">{departure_city}</div>
          <div class="time">{departure_time}</div>
        </div>
        <div class="flight-arrow">
          <div class="line"></div>
          <div class="dur">{duration_h}h {duration_m}m · Direct</div>
        </div>
        <div class="flight-point">
          <div class="code">{arrival_code}</div>
          <div class="city">{arrival_city}</div>
          <div class="time">{arrival_time}</div>
        </div>
      </div>
      <table class="flight-details-table">
        <tr>
          <td class="lbl">Flight</td>
          <td>{flight_number}</td>
          <td class="lbl">Airline</td>
          <td>{airline_name}</td>
        </tr>
        <tr>
          <td class="lbl">Cabin Class</td>
          <td>{cabin_class}</td>
          <td class="lbl">Passengers</td>
          <td>{num_pax}</td>
        </tr>
        <tr>
          <td class="lbl">Departure</td>
          <td>{departure_city} ({departure_code})</td>
          <td class="lbl">Arrival</td>
          <td>{arrival_city} ({arrival_code})</td>
        </tr>
        <tr>
          <td class="lbl">Duration</td>
          <td>{duration_h}h {duration_m}m</td>
          <td class="lbl">Booking Date</td>
          <td>{booking_date or "Today"}</td>
        </tr>
      </table>
    </div>

    <!-- Passenger Details -->
    <div class="section-heading">Passenger Details</div>
    <div class="passenger-section">
      <table class="passenger-table">
        <thead>
          <tr>
            <th>Passenger Name</th>
            <th class="center">Age</th>
            <th class="center">Gender</th>
            <th class="center">Seat</th>
          </tr>
        </thead>
        <tbody>{passenger_rows}
        </tbody>
      </table>
    </div>

    <!-- Fare Summary -->
    <div class="section-heading">Fare Summary</div>
    <div class="fare-section">
      <table class="fare-table">
        <tr>
          <td class="lbl">Airfare Charge ({num_pax} passenger{'s' if num_pax > 1 else ''})</td>
          <td class="amt">₹{base_fare:,.0f}</td>
        </tr>
        <tr>
          <td class="lbl">Taxes &amp; Fees</td>
          <td class="amt">₹{taxes_fees:,.0f}</td>
        </tr>
        <tr>
          <td class="lbl">Convenience Fee</td>
          <td class="amt">₹0</td>
        </tr>
        <tr class="total-row">
          <td class="lbl">Total Fare</td>
          <td class="amt">₹{total_amount:,.0f}</td>
        </tr>
      </table>
    </div>

    <!-- Contact Details -->
    <div class="section-heading">Contact Details</div>
    <div class="contact-section">
      <div class="contact-row"><strong>Passenger:</strong> {passenger_name}</div>
      <div class="contact-row"><strong>PNR:</strong> {pnr}</div>
      <div class="contact-row"><strong>Need help?</strong> Contact us at <a href="mailto:support@skybookairlines.com" style="color: #0066b3;">support@skybookairlines.com</a></div>
    </div>

    <!-- Important Information -->
    <div class="section-heading">Important Information</div>
    <div class="info-section">
      <p><strong>Check-in:</strong> Web check-in opens 24 hours before departure and closes 1 hour before departure.</p>
      <p><strong>Airport Arrival:</strong> Please report at the airport at least 2 hours before departure.</p>
      <p><strong>Boarding:</strong> Boarding gates close 25 minutes before departure. Late arrivals will not be accepted.</p>
      <p><strong>Baggage:</strong> Cabin baggage up to 7kg allowed. Check-in baggage as per airline policy.</p>
      <p><strong>ID Proof:</strong> Carry a valid government-issued photo ID for verification at the airport.</p>
      <p><strong>Flight Status:</strong> Check flight status on our website or app before departure.</p>
    </div>

    <!-- Footer -->
    <div class="footer">
      <div class="links">
        <a href="https://skybook.ai">Website</a> ·
        <a href="mailto:support@skybookairlines.com">Support</a> ·
        <a href="https://skybook.ai/check-in">Web Check-in</a>
      </div>
      <p>This is a system-generated e-ticket. Please carry a printout or show this email on your mobile at the airport.</p>
      <p>© 2025 SkyBook Airlines. All rights reserved.</p>
    </div>

  </div>
</body>
</html>"""


def send_via_smtp(to_email: str, subject: str, body: str, html: bool = True) -> dict:
    """Send email via SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    text_part = MIMEText(body, "plain")
    msg.attach(text_part)

    if html:
        html_part = MIMEText(_build_html_email(subject, body), "html")
        msg.attach(html_part)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())

    return {"success": True, "method": "smtp", "recipient": to_email}


def send_via_resend(to_email: str, subject: str, body: str, html_content: str = None) -> dict:
    """Send email via Resend API (free tier: 3000 emails/month)."""
    import httpx
    if html_content is None:
        html_content = _build_html_email(subject, body)
    from_email = settings.RESEND_FROM_EMAIL or settings.SMTP_FROM_EMAIL

    r = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": f"{settings.SMTP_FROM_NAME} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": body,
        },
        timeout=30,
    )
    r.raise_for_status()
    result = r.json()

    return {"success": True, "method": "resend", "recipient": to_email, "id": result.get("id")}


def send_email(
    to_email: str,
    subject: str,
    body: str,
    notification_type: str = "email",
    html_content: str = None,
) -> dict:
    """Send an email using the best available method.

    Priority: SMTP > Resend API > Console (mock)
    """
    if not to_email or "@" not in to_email:
        return {"success": False, "error": "Invalid email address"}

    # Try SMTP first
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS:
        try:
            return send_via_smtp(to_email, subject, body)
        except Exception as e:
            print(f"⚠️  SMTP send failed: {e}. Falling back.")

    # Try Resend API
    if settings.RESEND_API_KEY:
        try:
            return send_via_resend(to_email, subject, body, html_content=html_content)
        except Exception as e:
            print(f"⚠️  Resend send failed: {e}. Falling back to console.")

    # Fallback: console logging
    print(f"\n{'='*60}")
    print(f"📧 [MOCK EMAIL] To: {to_email}")
    print(f"   Subject: {subject}")
    print(f"   Body: {body[:200]}")
    print(f"{'='*60}\n")
    return {"success": True, "method": "mock", "recipient": to_email}


def send_booking_confirmation(
    to_email: str,
    pnr: str,
    flight_number: str,
    route: str,
    departure_time: str,
    passenger_name: str,
    total_amount: float,
    airline_name: str = "SkyBook Airlines",
    departure_city: str = "",
    departure_code: str = "",
    arrival_city: str = "",
    arrival_code: str = "",
    arrival_time: str = "",
    duration_minutes: int = 0,
    cabin_class: str = "Economy",
    passengers: list = None,
) -> dict:
    """Send a booking confirmation email with full e-ticket details."""
    subject = f"✈️ E-Ticket Confirmed — PNR {pnr} · {flight_number}"
    body = (
        f"Your booking has been confirmed!\n\n"
        f"PNR: {pnr}\n"
        f"Flight: {flight_number} ({airline_name})\n"
        f"Route: {route}\n"
        f"Departure: {departure_time}\n"
        f"Arrival: {arrival_time}\n"
        f"Passenger: {passenger_name}\n"
        f"Cabin: {cabin_class}\n"
        f"Total Amount: ₹{total_amount:,.2f}\n\n"
        f"You can check-in online 24 hours before departure.\n"
        f"Thank you for choosing SkyBook Airlines!"
    )
    html_content = _build_ticket_html(
        pnr=pnr,
        flight_number=flight_number,
        airline_name=airline_name,
        departure_city=departure_city or route.split("→")[0].strip() if "→" in route else route,
        departure_code=departure_code,
        arrival_city=arrival_city or route.split("→")[1].strip() if "→" in route else "",
        arrival_code=arrival_code,
        departure_time=departure_time,
        arrival_time=arrival_time,
        duration_minutes=duration_minutes,
        passenger_name=passenger_name,
        cabin_class=cabin_class,
        total_amount=total_amount,
        passengers=passengers,
    )
    return send_email(to_email, subject, body, "booking_confirmation", html_content=html_content)


def send_cancellation_notice(
    to_email: str,
    pnr: str,
    flight_number: str,
    refund_amount: float,
) -> dict:
    """Send a booking cancellation email."""
    subject = f"❌ Booking Cancelled — PNR {pnr}"
    body = (
        f"Your booking has been cancelled.\n\n"
        f"PNR: {pnr}\n"
        f"Flight: {flight_number}\n"
        f"Refund Amount: ₹{refund_amount:,.2f}\n"
        f"Refund will be processed in 5-7 business days.\n\n"
        f"If you did not request this cancellation, please contact support immediately."
    )
    return send_email(to_email, subject, body, "cancellation")


def send_checkin_confirmation(
    to_email: str,
    pnr: str,
    flight_number: str,
    route: str,
    seat: str,
    gate: str,
    boarding_time: str,
) -> dict:
    """Send a check-in confirmation email with boarding pass info."""
    subject = f"✅ Check-in Successful — PNR {pnr}"
    body = (
        f"Your web check-in is complete!\n\n"
        f"PNR: {pnr}\n"
        f"Flight: {flight_number}\n"
        f"Route: {route}\n"
        f"Seat: {seat}\n"
        f"Gate: {gate}\n"
        f"Boarding Time: {boarding_time}\n\n"
        f"Please arrive at the airport at least 2 hours before departure.\n"
        f"Have a pleasant flight!"
    )
    return send_email(to_email, subject, body, "check_in")


def send_refund_update(
    to_email: str,
    pnr: str,
    refund_amount: float,
    status: str,
) -> dict:
    """Send a refund status update email."""
    subject = f"💰 Refund Update — PNR {pnr}"
    body = (
        f"Your refund status has been updated.\n\n"
        f"PNR: {pnr}\n"
        f"Refund Amount: ₹{refund_amount:,.2f}\n"
        f"Status: {status.upper()}\n\n"
        f"If you have any questions, please contact our support team."
    )
    return send_email(to_email, subject, body, "refund_update")


def send_welcome_email(to_email: str, name: str, otp_code: str = None) -> dict:
    """Send a welcome / registration confirmation email with OTP if provided."""
    subject = f"Welcome to SkyBook AI, {name}! ✈️"
    if otp_code:
        body = (
            f"Welcome to SkyBook AI, {name}!\n\n"
            f"Your account has been successfully created.\n\n"
            f"Your OTP for email verification is: {otp_code}\n"
            f"This OTP is valid for 10 minutes.\n\n"
            f"Please verify your email to start booking flights.\n\n"
            f"Happy travels!\n"
            f"SkyBook AI Team"
        )
    else:
        body = (
            f"Welcome to SkyBook AI, {name}!\n\n"
            f"Your account has been successfully created.\n\n"
            f"You can now start booking flights, check statuses, and more.\n\n"
            f"Happy travels!\n"
            f"SkyBook AI Team"
        )
    return send_email(to_email, subject, body, "welcome")
