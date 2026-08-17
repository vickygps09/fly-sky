'use client';

import { useState, useEffect, useRef } from 'react';
import type { FlightInfo, Seat, User, BookingResult } from '@/types';
import { getSeats, submitBooking } from '@/lib/api';

interface BookingModalProps {
  flightInfo: FlightInfo;
  passengerCount: number;
  user: User | null;
  sessionId: string;
  onClose: () => void;
  onBookingComplete: (result: BookingResult) => void;
}

const BAGGAGE_COSTS: Record<number, number> = { 0: 0, 5: 300, 10: 500, 20: 900 };

export default function BookingModal({
  flightInfo,
  passengerCount,
  user,
  sessionId,
  onClose,
  onBookingComplete,
}: BookingModalProps) {
  const [seats, setSeats] = useState<Seat[]>([]);
  const [selectedSeats, setSelectedSeats] = useState<Record<string, boolean>>({});
  const [meals, setMeals] = useState<Record<number, string>>({});
  const [baggage, setBaggage] = useState(0);
  const [insurance, setInsurance] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const passengerRefs = useRef<Record<number, { name: HTMLInputElement; age: HTMLInputElement; gender: HTMLSelectElement }>>({});

  useEffect(() => {
    // Initialize meals
    const initialMeals: Record<number, string> = {};
    for (let i = 0; i < passengerCount; i++) initialMeals[i] = 'none';
    setMeals(initialMeals);

    // Fetch seats
    getSeats(flightInfo.id).then((data) => {
      setSeats(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [flightInfo.id, passengerCount]);

  const depTime = new Date(flightInfo.departure_time).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  });

  const selectSeat = (seatNumber: string) => {
    setSelectedSeats((prev) => {
      const next = { ...prev };
      if (next[seatNumber]) {
        delete next[seatNumber];
      } else {
        const count = Object.keys(next).length;
        if (count >= passengerCount) {
          const firstSeat = Object.keys(next)[0];
          delete next[firstSeat];
        }
        next[seatNumber] = true;
      }
      return next;
    });
  };

  const selectMeal = (paxIndex: number, meal: string) => {
    setMeals((prev) => ({ ...prev, [paxIndex]: meal }));
  };

  const computeTotal = () => {
    let total = flightInfo.price * passengerCount;
    const seatPrices: Record<string, number> = {};
    for (const seat of seats) seatPrices[seat.seat_number] = seat.price || 0;
    for (const seatNum of Object.keys(selectedSeats)) total += seatPrices[seatNum] || 0;
    total += BAGGAGE_COSTS[baggage] || 0;
    if (insurance) total += 199;
    return total;
  };

  const handleSubmit = async () => {
    setError('');
    const passengers = [];
    for (let i = 0; i < passengerCount; i++) {
      const refs = passengerRefs.current[i];
      if (!refs) continue;
      const name = refs.name.value.trim();
      if (!name || name.length < 2) {
        setError(`Please enter a valid name for Passenger ${i + 1}`);
        return;
      }
      const age = refs.age.value;
      const gender = refs.gender.value;
      const seatNumbers = Object.keys(selectedSeats);
      passengers.push({
        full_name: name,
        age: age ? parseInt(age) : null,
        gender: gender || null,
        seat_number: seatNumbers[i] || null,
        meal_preference: meals[i] || 'none',
        is_primary: i === 0,
      });
    }

    const emailEl = document.getElementById('contact-email') as HTMLInputElement;
    const phoneEl = document.getElementById('contact-phone') as HTMLInputElement;
    const email = emailEl.value.trim();
    const phone = phoneEl.value.trim();
    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }
    const phoneClean = phone.replace(/[\s\-()]/g, '');
    if (!phoneClean.match(/^\+?\d{10,15}$/)) {
      setError('Please enter a valid mobile number');
      return;
    }

    setSubmitting(true);
    try {
      const result = await submitBooking(
        sessionId,
        user?.user_id || null,
        flightInfo.id,
        passengers,
        email,
        phoneClean,
        insurance,
        baggage
      );
      onBookingComplete(result);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  };

  return (
    <div className="modal" style={{ display: 'flex' }}>
      <div className="modal-content booking-content">
        <div className="modal-header">
          <h2>📝 Passenger Details</h2>
          <button onClick={onClose} className="modal-close">&times;</button>
        </div>

        {error && <p style={{ color: 'var(--danger)', fontSize: '13px', marginBottom: '10px' }}>{error}</p>}

        <div className="booking-form">
          {/* Flight Summary */}
          <div className="booking-flight-summary">
            <div>
              <div className="bfs-route">{flightInfo.departure_airport_city} → {flightInfo.arrival_airport_city}</div>
              <div className="bfs-detail">✈️ {flightInfo.flight_number} · {depTime}</div>
            </div>
            <div className="bfs-price">₹{flightInfo.price.toLocaleString()}</div>
          </div>

          {/* Passenger Details */}
          <div className="form-section-title">👤 Passenger Details</div>
          {Array.from({ length: passengerCount }).map((_, i) => (
            <div key={i} className="passenger-card" style={{ marginBottom: '10px' }}>
              <div className="passenger-card-header">
                <div className="passenger-badge">{i + 1}</div>
                {passengerCount === 1 ? 'Passenger' : `Passenger ${i + 1}`}{i === 0 ? ' (Primary)' : ''}
              </div>
              <div className="form-row-3">
                <div className="form-field">
                  <label>Full Name</label>
                  <input type="text" placeholder="First Last" required
                    ref={(el) => { if (el) passengerRefs.current[i] = { ...(passengerRefs.current[i] || {}), name: el }; }} />
                </div>
                <div className="form-field">
                  <label>Age</label>
                  <input type="number" placeholder="25" min={1} max={120}
                    ref={(el) => { if (el) passengerRefs.current[i] = { ...(passengerRefs.current[i] || {}), age: el }; }} />
                </div>
                <div className="form-field">
                  <label>Gender</label>
                  <select
                    ref={(el) => { if (el) passengerRefs.current[i] = { ...(passengerRefs.current[i] || {}), gender: el }; }}>
                    <option value="">Select</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            </div>
          ))}

          {/* Contact Details */}
          <div className="form-section-title">📧 Contact Details</div>
          <div className="form-row-2">
            <div className="form-field">
              <label>Email</label>
              <input type="email" id="contact-email" placeholder="john@example.com" defaultValue={user?.email || ''} />
            </div>
            <div className="form-field">
              <label>Mobile Number</label>
              <input type="tel" id="contact-phone" placeholder="+91 98765 43210" defaultValue={user?.phone || ''} />
            </div>
          </div>

          {/* Seat Selection */}
          <div className="form-section-title">💺 Seat Selection</div>
          <div className="seat-selection">
            <div className="seat-legend">
              <div className="seat-legend-item"><div className="seat-legend-dot available" />Available</div>
              <div className="seat-legend-item"><div className="seat-legend-dot window" />Window</div>
              <div className="seat-legend-item"><div className="seat-legend-dot occupied" />Occupied</div>
              <div className="seat-legend-item"><div className="seat-legend-dot selected" />Selected</div>
            </div>
            {loading ? (
              <div style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>Loading seats...</div>
            ) : seats.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '12px', color: 'var(--text-muted)', fontSize: '13px' }}>No seat map available</div>
            ) : (
              <div className="seat-grid">
                {seats.map((seat) => {
                  const isSelected = !!selectedSeats[seat.seat_number];
                  const classes = seat.is_occupied
                    ? 'occupied'
                    : isSelected
                      ? 'selected'
                      : seat.is_window
                        ? 'available window'
                        : 'available';
                  return (
                    <div
                      key={seat.seat_number}
                      className={`seat-item ${classes}`}
                      data-seat={seat.seat_number}
                      onClick={() => !seat.is_occupied && selectSeat(seat.seat_number)}
                    >
                      {seat.seat_number}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Meal Preference */}
          <div className="form-section-title">🍽️ Meal Preference</div>
          <div>
            {Array.from({ length: passengerCount }).map((_, i) => (
              <div key={i} style={{ marginBottom: '8px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
                  {passengerCount === 1 ? 'Passenger' : `Passenger ${i + 1}`}
                </div>
                <div className="meal-pills">
                  {[
                    { val: 'none', label: 'No Meal' },
                    { val: 'veg', label: '🥗 Veg' },
                    { val: 'non_veg', label: '🍗 Non-Veg' },
                    { val: 'jain', label: '🌱 Jain' },
                  ].map((m) => (
                    <div
                      key={m.val}
                      className={`meal-pill ${meals[i] === m.val ? 'selected' : ''}`}
                      onClick={() => selectMeal(i, m.val)}
                    >
                      {m.label}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Baggage Add-on */}
          <div className="form-section-title">🧳 Extra Baggage</div>
          <div className="baggage-options">
            {[
              { kg: 0, label: '0 kg', price: 'Free' },
              { kg: 5, label: '+5 kg', price: '₹300' },
              { kg: 10, label: '+10 kg', price: '₹500' },
              { kg: 20, label: '+20 kg', price: '₹900' },
            ].map((opt) => (
              <div
                key={opt.kg}
                className={`baggage-option ${baggage === opt.kg ? 'selected' : ''}`}
                onClick={() => setBaggage(opt.kg)}
              >
                <div className="baggage-option-weight">{opt.label}</div>
                <div className="baggage-option-price">{opt.price}</div>
              </div>
            ))}
          </div>

          {/* Travel Insurance */}
          <div className="form-section-title">🛡️ Travel Insurance</div>
          <div
            className={`addon-row ${insurance ? 'selected' : ''}`}
            onClick={() => setInsurance(!insurance)}
          >
            <div className="addon-info">
              <span className="addon-icon">🛡️</span>
              <div>
                <div className="addon-name">Travel Insurance</div>
                <div className="addon-desc">Coverage for trip cancellation, lost baggage &amp; medical</div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="addon-price">₹199</span>
              <div className="addon-checkbox">
                {insurance && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
              </div>
            </div>
          </div>

          {/* Total */}
          <div className="booking-total-bar">
            <span className="booking-total-label">Total Amount</span>
            <span className="booking-total-amount">₹{computeTotal().toLocaleString()}</span>
          </div>

          {/* Actions */}
          <div className="booking-form-actions">
            <button className="btn-secondary" onClick={onClose} disabled={submitting}>Cancel</button>
            <button className="btn-primary" style={{ flex: 2 }} onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Creating booking...' : 'Continue to Payment →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
