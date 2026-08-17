'use client';

import type { BoardingPass } from '@/types';

interface BoardingPassModalProps {
  boardingPass: BoardingPass;
  onClose: () => void;
}

export default function BoardingPassModal({ boardingPass, onClose }: BoardingPassModalProps) {
  const bp = boardingPass;
  const depTime = new Date(bp.departure_time).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  });
  const boardTime = new Date(bp.boarding_time).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  });

  return (
    <div className="modal" style={{ display: 'flex' }}>
      <div className="modal-content boarding-content">
        <div className="modal-header">
          <h2>🛫 Boarding Pass</h2>
          <button onClick={onClose} className="modal-close">&times;</button>
        </div>
        <div className="boarding-pass">
          <div className="bp-header">
            <div className="bp-airline">{bp.airline_name || 'SkyBook Airlines'}</div>
            <div className="bp-flight">{bp.flight_number}</div>
          </div>
          <div className="bp-route">
            <div><div className="bp-city">{bp.departure_city}</div></div>
            <div className="bp-plane">✈️</div>
            <div style={{ textAlign: 'right' }}><div className="bp-city">{bp.arrival_city}</div></div>
          </div>
          <div className="bp-details">
            <div>
              <div className="bp-label">Passenger</div>
              <div className="bp-value">{bp.passenger_name}</div>
            </div>
            <div>
              <div className="bp-label">Seat</div>
              <div className="bp-value">{bp.seat}</div>
            </div>
            <div>
              <div className="bp-label">Gate</div>
              <div className="bp-value">{bp.gate}</div>
            </div>
            <div>
              <div className="bp-label">Date</div>
              <div className="bp-value">{depTime}</div>
            </div>
            <div>
              <div className="bp-label">Boarding</div>
              <div className="bp-value">{boardTime}</div>
            </div>
          </div>
          <div className="bp-footer">
            <div>
              <div className="bp-label">PNR</div>
              <div className="bp-pnr">{bp.pnr}</div>
            </div>
            <div className="bp-qr">🔳</div>
          </div>
        </div>
        <button className="btn-primary full-width" style={{ marginTop: '16px' }} onClick={() => window.print()}>
          🖨️ Print Boarding Pass
        </button>
      </div>
    </div>
  );
}
