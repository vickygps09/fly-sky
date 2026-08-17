"""Auth router — Registration, Login, Guest login, OTP verification."""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import hash_password, verify_password, create_access_token, generate_otp, require_user
from schemas import UserRegister, UserLogin, GuestLogin, OTPVerify, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        is_guest=False,
        is_verified=False,
        otp_code=generate_otp(),
        otp_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send notifications: Email (with OTP), SMS, WhatsApp
    notification_results = {}

    # 1. Welcome email with OTP
    try:
        from services.email_service import send_welcome_email
        email_result = send_welcome_email(user.email, user.name, otp_code=user.otp_code)
        notification_results["email"] = email_result
    except Exception as e:
        print(f"⚠️  Registration email failed: {e}")
        notification_results["email"] = {"success": False, "error": str(e)}

    # 2. SMS welcome message (if phone provided)
    if data.phone:
        try:
            from services.sms_service import send_sms
            sms_body = f"Welcome to SkyBook AI, {data.name}! Your account is created. OTP: {user.otp_code}"
            sms_result = send_sms(data.phone, sms_body)
            notification_results["sms"] = sms_result
        except Exception as e:
            print(f"⚠️  Registration SMS failed: {e}")
            notification_results["sms"] = {"success": False, "error": str(e)}

    # 3. WhatsApp welcome message (if phone provided)
    if data.phone:
        try:
            from services.sms_service import send_whatsapp
            wa_body = f"Welcome to SkyBook AI, {data.name}! Your account has been created successfully. Your OTP is {user.otp_code}. Valid for 10 minutes."
            wa_result = send_whatsapp(data.phone, wa_body)
            notification_results["whatsapp"] = wa_result
        except Exception as e:
            print(f"⚠️  Registration WhatsApp failed: {e}")
            notification_results["whatsapp"] = {"success": False, "error": str(e)}

    # Log notifications to DB
    try:
        from models import NotificationLog, NotificationType
        for ntype, nresult in notification_results.items():
            recipient = data.email if ntype == "email" else (data.phone or "")
            log = NotificationLog(
                user_id=user.id,
                notification_type=NotificationType(ntype) if ntype in ("email", "sms", "whatsapp") else NotificationType.EMAIL,
                recipient=recipient,
                subject="Welcome to SkyBook AI" if ntype == "email" else None,
                body=f"Registration notification via {ntype}",
                status="sent" if nresult.get("success") else "failed",
            )
            db.add(log)
        db.commit()
    except Exception as e:
        print(f"⚠️  Failed to log notifications: {e}")

    token = create_access_token({"sub": user.id, "email": user.email, "name": user.name})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email,
        is_guest=False,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": user.id, "email": user.email, "name": user.name})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email,
        is_guest=user.is_guest,
    )


@router.post("/guest", response_model=TokenResponse)
def guest_login(data: GuestLogin, db: Session = Depends(get_db)):
    """Create a temporary guest user."""
    user = models.User(
        name=data.name,
        email=f"guest_{data.name.lower().replace(' ', '_')}@guest.skybook.ai",
        phone=data.phone,
        is_guest=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id, "email": user.email, "name": user.name})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        email=user.email,
        is_guest=True,
    )


@router.post("/verify-otp")
def verify_otp(data: OTPVerify, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp_code or user.otp_code != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if user.otp_expires and user.otp_expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    user.is_verified = True
    user.otp_code = None
    user.otp_expires = None
    db.commit()

    return {"message": "Email verified successfully", "verified": True}


@router.get("/me", response_model=UserOut)
def get_me(user: models.User = Depends(require_user)):
    return user
