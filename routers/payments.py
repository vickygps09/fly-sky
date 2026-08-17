"""Payments router — Payment initiation, confirmation, refund status, coupon validation."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from schemas import PaymentInitiate, PaymentConfirm, TransactionOut, RefundOut
from chatbot.tools import initiate_payment, confirm_payment, get_refund_status, validate_coupon

router = APIRouter(prefix="/api/payments", tags=["Payments"])


class CouponValidateRequest(BaseModel):
    code: str
    booking_amount: float


@router.post("/validate-coupon", response_model=dict)
def validate_coupon_endpoint(data: CouponValidateRequest, db: Session = Depends(get_db)):
    """Validate a coupon or promo code and return discount details."""
    result = validate_coupon(db, data.code, data.booking_amount)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("error", "Invalid coupon code"))
    return result


@router.post("/initiate", response_model=dict)
def initiate(data: PaymentInitiate, db: Session = Depends(get_db)):
    result = initiate_payment(db, data.booking_id, data.payment_method)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/confirm", response_model=dict)
def confirm(data: PaymentConfirm, db: Session = Depends(get_db)):
    result = confirm_payment(db, data.transaction_id, data.success)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/refund/{pnr}", response_model=dict)
def refund_status(pnr: str, db: Session = Depends(get_db)):
    result = get_refund_status(db, pnr)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
