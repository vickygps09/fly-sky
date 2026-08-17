'use client';

import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface FlightMapProps {
  departureCity: string;
  departureCode: string;
  departureLat: number;
  departureLon: number;
  arrivalCity: string;
  arrivalCode: string;
  arrivalLat: number;
  arrivalLon: number;
}

// Custom airport icons
const airportIcon = (color: string) =>
  L.divIcon({
    html: `<div style="background:${color};width:16px;height:16px;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>`,
    className: '',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });

export default function FlightMap({
  departureCity,
  departureCode,
  departureLat,
  departureLon,
  arrivalCity,
  arrivalCode,
  arrivalLat,
  arrivalLon,
}: FlightMapProps) {
  const centerLat = (departureLat + arrivalLat) / 2;
  const centerLon = (departureLon + arrivalLon) / 2;
  const distance = Math.sqrt(
    Math.pow(departureLat - arrivalLat, 2) + Math.pow(departureLon - arrivalLon, 2)
  );
  const zoom = distance > 15 ? 4 : distance > 8 ? 5 : 6;

  return (
    <MapContainer
      center={[centerLat, centerLon]}
      zoom={zoom}
      style={{ height: '180px', width: '100%', borderRadius: '10px', marginTop: '8px', zIndex: 0 }}
      scrollWheelZoom={false}
      dragging={false}
      doubleClickZoom={false}
      attributionControl={false}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Marker position={[departureLat, departureLon]} icon={airportIcon('#10b981')}>
        <Popup>
          {departureCity} ({departureCode})
        </Popup>
      </Marker>
      <Marker position={[arrivalLat, arrivalLon]} icon={airportIcon('#ef4444')}>
        <Popup>
          {arrivalCity} ({arrivalCode})
        </Popup>
      </Marker>
      <Polyline
        positions={[
          [departureLat, departureLon],
          [arrivalLat, arrivalLon],
        ]}
        pathOptions={{ color: '#6366f1', weight: 2, dashArray: '6 4' }}
      />
    </MapContainer>
  );
}
