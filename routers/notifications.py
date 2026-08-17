"""Notifications router — SMS, Email, WhatsApp."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from schemas import NotificationSend
from chatbot.tools import send_notification
from services.email_service import send_email, send_booking_confirmation

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class TestEmailRequest(BaseModel):
    to_email: str
    subject: str = "Test Email from SkyBook AI"
    body: str = "This is a test email from SkyBook AI."


@router.post("/send", response_model=dict)
def send(data: NotificationSend, db: Session = Depends(get_db)):
    result = send_notification(
        db=db,
        recipient=data.recipient,
        body=data.body,
        notification_type=data.notification_type,
        subject=data.subject,
        booking_id=data.booking_id,
    )
    return result


@router.post("/test-email", response_model=dict)
def test_email(data: TestEmailRequest):
    """Send a test email to verify SMTP/Resend configuration."""
    return send_email(data.to_email, data.subject, data.body)


@router.get("/logs", response_model=list[dict])
def list_logs(db: Session = Depends(get_db)):
    from models import NotificationLog
    logs = db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(50).all()
    return [
        {
            "id": l.id,
            "type": l.notification_type.value,
            "recipient": l.recipient,
            "subject": l.subject,
            "status": l.status,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
