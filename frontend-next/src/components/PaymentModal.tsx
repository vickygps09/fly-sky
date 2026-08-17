'use client';

import { useState } from 'react';
import type { BookingResult } from '@/types';
import { initiatePayment, confirmPayment, validateCoupon } from '@/lib/api';

interface PaymentModalProps {
  payment: BookingResult;
  onClose: () => void;
  onSuccess: () => void;
}

export default function PaymentModal({ payment, onClose, onSuccess }: PaymentModalProps) {
  const [method, setMethod] = useState<'card' | 'upi' | 'netbanking'>('card');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [couponCode, setCouponCode] = useState('');
  const [couponApplied, setCouponApplied] = useState<{ code: string; discountAmount: number; finalAmount: number } | null>(null);
  const [couponLoading, setCouponLoading] = useState(false);
  const [couponError, setCouponError] = useState('');

  // Card form state (controlled inputs + live card preview)
  const [cardNum, setCardNum] = useState('');
  const [cardName, setCardName] = useState('');
  const [cardExpiry, setCardExpiry] = useState('');
  const [cardCvv, setCardCvv] = useState('');
  const [upiId, setUpiId] = useState('');
  const [bankVal, setBankVal] = useState('');

  const p = payment;
  const depTime = new Date(p.departure_time).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  });

  const originalAmount = p.total_amount;
  const displayAmount = couponApplied ? couponApplied.finalAmount : originalAmount;
  const discountAmount = couponApplied ? couponApplied.discountAmount : 0;

  const handleCardNumChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 16);
    setCardNum(v.replace(/(\d{4})(?=\d)/g, '$1 '));
  };

  const handleExpiryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let v = e.target.value.replace(/\D/g, '').slice(0, 4);
    if (v.length >= 3) v = v.slice(0, 2) + '/' + v.slice(2);
    setCardExpiry(v);
  };

  // Display card number: mask all but last 4 groups
  const displayCardNum = (() => {
    const raw = cardNum.replace(/\s/g, '');
    if (!raw) return '•••• •••• •••• ••••';
    const padded = raw.padEnd(16, '•');
    return `${padded.slice(0, 4)} ${padded.slice(4, 8)} ${padded.slice(8, 12)} ${padded.slice(12, 16)}`;
  })();

  const handleApplyCoupon = async () => {
    setCouponError('');
    if (!couponCode.trim()) {
      setCouponError('Please enter a coupon code');
      return;
    }
    setCouponLoading(true);
    try {
      const result = await validateCoupon(couponCode.trim(), originalAmount);
      setCouponApplied({
        code: result.code,
        discountAmount: result.discount_amount,
        finalAmount: result.final_amount,
      });
    } catch (err) {
      setCouponApplied(null);
      setCouponError((err as Error).message);
    } finally {
      setCouponLoading(false);
    }
  };

  const handleRemoveCoupon = () => {
    setCouponApplied(null);
    setCouponCode('');
    setCouponError('');
  };

  const handlePayment = async () => {
    setError('');
    const rawCardNum = cardNum.replace(/\s/g, '');

    if (method === 'card') {
      if (rawCardNum.length < 16) { setError('Please enter a valid 16-digit card number'); return; }
      if (!cardName.trim()) { setError('Please enter cardholder name'); return; }
      if (!cardExpiry.match(/^\d{2}\/\d{2}$/)) { setError('Please enter valid expiry (MM/YY)'); return; }
      if (cardCvv.length < 3) { setError('Please enter valid CVV'); return; }
    } else if (method === 'upi') {
      if (!upiId.trim() || !upiId.includes('@')) { setError('Please enter a valid UPI ID'); return; }
    } else if (method === 'netbanking') {
      if (!bankVal) { setError('Please select your bank'); return; }
    }

    setProcessing(true);
    try {
      const initResp = await initiatePayment(p.booking_id, method);
      await new Promise((r) => setTimeout(r, 2000));
      await confirmPayment(p.booking_id, initResp.transaction_id, method);
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
      setProcessing(false);
    }
  };

  return (
    <div className="modal" style={{ display: 'flex' }}>
      <div className="modal-content payment-content">
        {processing && (
          <div className="payment-processing-overlay">
            <div className="payment-spinner" />
            <p>Processing your payment securely...</p>
          </div>
        )}
        <div className="modal-header">
          <h2>💳 Payment</h2>
          <button onClick={onClose} className="modal-close">&times;</button>
        </div>

        {error && <p style={{ color: 'var(--danger)', fontSize: '13px', marginBottom: '10px' }}>{error}</p>}

        <div className="payment-summary">
          <h3>🎫 Booking Summary</h3>
          <div className="payment-row"><span>PNR</span><strong>{p.pnr}</strong></div>
          <div className="payment-row"><span>Flight</span><span>{p.flight_number}</span></div>
          <div className="payment-row"><span>Route</span><span>{p.departure_city} → {p.arrival_city}</span></div>
          <div className="payment-row"><span>Date</span><span>{depTime}</span></div>
          <div className="payment-row"><span>Passenger</span><span>{p.passenger_name}</span></div>
          {p.travel_insurance && <div className="payment-row"><span>Insurance</span><span>✅ Included</span></div>}
          {p.extra_baggage_kg > 0 && <div className="payment-row"><span>Extra Baggage</span><span>+{p.extra_baggage_kg} kg</span></div>}
        </div>

        {/* Coupon / Promo Code Section */}
        <div className="coupon-section">
          <label className="coupon-label">🎫 Have a coupon or promo code?</label>
          {couponApplied ? (
            <div className="coupon-applied">
              <div className="coupon-applied-info">
                <span className="coupon-badge">✅ {couponApplied.code}</span>
                <span className="coupon-discount">−₹{couponApplied.discountAmount.toLocaleString()}</span>
              </div>
              <button className="coupon-remove-btn" onClick={handleRemoveCoupon}>Remove</button>
            </div>
          ) : (
            <div className="coupon-input-row">
              <input
                type="text"
                className="coupon-input"
                placeholder="Enter code (e.g., SAVE20)"
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                onKeyDown={(e) => { if (e.key === 'Enter') handleApplyCoupon(); }}
                disabled={couponLoading}
              />
              <button className="coupon-apply-btn" onClick={handleApplyCoupon} disabled={couponLoading}>
                {couponLoading ? 'Checking...' : 'Apply'}
              </button>
            </div>
          )}
          {couponError && <p className="coupon-error">{couponError}</p>}
        </div>

        {/* Price breakdown with discount */}
        <div className="payment-total-section">
          {discountAmount > 0 && (
            <>
              <div className="payment-row payment-row-original"><span>Original Amount</span><span>₹{originalAmount.toLocaleString()}</span></div>
              <div className="payment-row payment-row-discount"><span>Discount ({couponApplied?.code})</span><span>−₹{discountAmount.toLocaleString()}</span></div>
            </>
          )}
          <div className="payment-total"><span>Total Payable</span><span>₹{displayAmount.toLocaleString()}</span></div>
        </div>

        <div className="payment-methods">
          <div className={`payment-method ${method === 'card' ? 'selected' : ''}`} onClick={() => setMethod('card')}>
            <span className="payment-method-icon">💳</span>
            <span className="payment-method-name">Credit / Debit Card</span>
          </div>
          <div className={`payment-method ${method === 'upi' ? 'selected' : ''}`} onClick={() => setMethod('upi')}>
            <span className="payment-method-icon">📱</span>
            <span className="payment-method-name">UPI</span>
          </div>
          <div className={`payment-method ${method === 'netbanking' ? 'selected' : ''}`} onClick={() => setMethod('netbanking')}>
            <span className="payment-method-icon">🏦</span>
            <span className="payment-method-name">Net Banking</span>
          </div>
        </div>

        {method === 'card' && (
          <>
            {/* Live credit card preview */}
            <div className="credit-card-visual">
              <div className="cc-top">
                <div className="cc-chip" />
                <span className="cc-contactless">((•))</span>
              </div>
              <div className="cc-number">{displayCardNum}</div>
              <div className="cc-bottom">
                <div>
                  <div className="cc-label">Card Holder</div>
                  <div className="cc-value">{cardName.trim() || 'YOUR NAME'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="cc-label">Expires</div>
                  <div className="cc-value">{cardExpiry || 'MM/YY'}</div>
                </div>
                <div className="cc-network-logo">
                  <div className="circle1" />
                  <div className="circle2" />
                </div>
              </div>
            </div>

            <div className="payment-card-form">
              <div className="form-field">
                <label>Card Number</label>
                <input type="text" placeholder="1234 5678 9012 3456" maxLength={19}
                  value={cardNum} onChange={handleCardNumChange} autoComplete="off" />
              </div>
              <div className="form-field">
                <label>Cardholder Name</label>
                <input type="text" placeholder="Name on card"
                  value={cardName} onChange={(e) => setCardName(e.target.value)} autoComplete="off" />
              </div>
              <div className="form-row-2">
                <div className="form-field">
                  <label>Expiry (MM/YY)</label>
                  <input type="text" placeholder="12/28" maxLength={5}
                    value={cardExpiry} onChange={handleExpiryChange} autoComplete="off" />
                </div>
                <div className="form-field">
                  <label>CVV</label>
                  <input type="password" placeholder="•••" maxLength={4}
                    value={cardCvv} onChange={(e) => setCardCvv(e.target.value)} autoComplete="off" />
                </div>
              </div>
            </div>
          </>
        )}

        {method === 'upi' && (
          <div className="payment-card-form">
            <div className="form-field">
              <label>UPI ID</label>
              <input type="text" placeholder="yourname@upi"
                value={upiId} onChange={(e) => setUpiId(e.target.value)} autoComplete="off" />
            </div>
          </div>
        )}

        {method === 'netbanking' && (
          <div className="payment-card-form">
            <div className="form-field">
              <label>Select Bank</label>
              <select value={bankVal} onChange={(e) => setBankVal(e.target.value)}>
                <option value="">Choose your bank...</option>
                <option value="sbi">State Bank of India</option>
                <option value="hdfc">HDFC Bank</option>
                <option value="icici">ICICI Bank</option>
                <option value="axis">Axis Bank</option>
                <option value="kotak">Kotak Mahindra Bank</option>
                <option value="yes">Yes Bank</option>
              </select>
            </div>
          </div>
        )}

        <div className="payment-secure-badge">
          🔒 <span>Secured by 256-bit SSL encryption</span>
        </div>

        <button className="btn-primary payment-pay-btn" onClick={handlePayment} disabled={processing}>
          {processing ? 'Processing...' : `Pay ₹${displayAmount.toLocaleString()} →`}
        </button>
      </div>
    </div>
  );
}
