'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import type { FlightInfo } from '@/types';

const FlightMap = dynamic(() => import('./FlightMap'), { ssr: false });

interface FlightCardProps {
  flight: FlightInfo;
  number: number;
  onSelect: (flightId: string, number: number) => void;
}

export default function FlightCard({ flight, number, onSelect }: FlightCardProps) {
  const [showMap, setShowMap] = useState(false);
  const depTime = new Date(flight.departure_time).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
  const arrTime = new Date(flight.arrival_time).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
  const durH = Math.floor(flight.duration_minutes / 60);
  const durM = flight.duration_minutes % 60;
  const hasCoords = flight.departure_lat != null && flight.departure_lon != null &&
    flight.arrival_lat != null && flight.arrival_lon != null;

  return (
    <div className="flight-card" onClick={() => onSelect(flight.id, number)}>
      <div className="flight-card-header">
        <span className="flight-number">✈️ {flight.flight_number}</span>
        <span className="flight-price">₹{flight.price.toLocaleString()}</span>
      </div>
      <div className="flight-route">
        <div>
          <div className="flight-time">{depTime}</div>
          <div className="flight-city">{flight.departure_airport_city}</div>
        </div>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div className="flight-plane">✈️</div>
          <div className="flight-duration">{durH}h {durM}m</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="flight-time">{arrTime}</div>
          <div className="flight-city">{flight.arrival_airport_city}</div>
        </div>
      </div>
      {showMap && hasCoords && (
        <FlightMap
          departureCity={flight.departure_airport_city}
          departureCode={flight.departure_airport_code}
          departureLat={flight.departure_lat!}
          departureLon={flight.departure_lon!}
          arrivalCity={flight.arrival_airport_city}
          arrivalCode={flight.arrival_airport_code}
          arrivalLat={flight.arrival_lat!}
          arrivalLon={flight.arrival_lon!}
        />
      )}
      <div className="flight-footer">
        <span>💺 {flight.available_seats} seats available</span>
        <span>🧳 {flight.cabin_baggage_kg}kg + {flight.checked_baggage_kg}kg</span>
        {hasCoords && (
          <button
            className="flight-map-btn"
            onClick={(e) => { e.stopPropagation(); setShowMap(!showMap); }}
          >
            {showMap ? '🗺️ Hide map' : '🗺️ Show map'}
          </button>
        )}
        <button
          className="flight-select-btn"
          onClick={(e) => { e.stopPropagation(); onSelect(flight.id, number); }}
        >
          Select
        </button>
      </div>
    </div>
  );
}
