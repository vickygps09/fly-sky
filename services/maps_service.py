"""Maps Service — Airport locations, directions, and distance using free APIs.

Uses OpenStreetMap Nominatim for geocoding (free, no API key needed)
and OSRM for routing/distance (free, no API key needed).
"""

import json
import urllib.request
import urllib.parse
from typing import Optional
from config import settings


def geocode_location(query: str) -> dict:
    """Geocode a place name to lat/lon using OpenStreetMap Nominatim."""
    try:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": 1,
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "SkyBookAI/1.0 (airline chatbot)",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data:
            return {"error": f"Could not find location: {query}"}
        result = data[0]
        return {
            "query": query,
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "display_name": result.get("display_name", query),
        }
    except Exception as e:
        return {"error": f"Geocoding failed: {str(e)}"}


def get_airport_location(airport_name: str, city: str = "") -> dict:
    """Get the geographic coordinates of an airport."""
    query = f"{airport_name} airport" if city else f"{airport_name}"
    if city:
        query = f"{airport_name}, {city}"
    return geocode_location(query)


def get_distance_and_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Get driving distance and duration between two points using OSRM."""
    try:
        url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )
        req = urllib.request.Request(url, headers={
            "User-Agent": "SkyBookAI/1.0",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("routes"):
            route = data["routes"][0]
            distance_km = round(route["distance"] / 1000, 1)
            duration_min = round(route["duration"] / 60)
            return {
                "distance_km": distance_km,
                "duration_minutes": duration_min,
                "duration_text": f"{duration_min // 60}h {duration_min % 60}m",
            }
        return {"error": "No route found"}
    except Exception as e:
        return {"error": f"Routing failed: {str(e)}"}


def get_directions_to_airport(
    origin: str,
    airport_name: str,
    airport_city: str = "",
) -> dict:
    """Get directions from an origin location to an airport."""
    origin_loc = geocode_location(origin)
    if "error" in origin_loc:
        return origin_loc

    airport_loc = get_airport_location(airport_name, airport_city)
    if "error" in airport_loc:
        return airport_loc

    route = get_distance_and_duration(
        origin_loc["lat"], origin_loc["lon"],
        airport_loc["lat"], airport_loc["lon"],
    )
    if "error" in route:
        return route

    return {
        "origin": origin_loc["display_name"],
        "destination": airport_loc["display_name"],
        "origin_coords": {"lat": origin_loc["lat"], "lon": origin_loc["lon"]},
        "destination_coords": {"lat": airport_loc["lat"], "lon": airport_loc["lon"]},
        "distance_km": route["distance_km"],
        "duration_minutes": route["duration_minutes"],
        "duration_text": route["duration_text"],
        "maps_url": (
            f"https://www.openstreetmap.org/directions?"
            f"from={origin_loc['lat']},{origin_loc['lon']}"
            f"&to={airport_loc['lat']},{airport_loc['lon']}"
        ),
    }


def get_static_map_url(lat: float, lon: float, zoom: int = 13) -> str:
    """Get a static map image URL for a location using OpenStreetMap."""
    return (
        f"https://staticmap.openstreetmap.de/staticmap.php?"
        f"center={lat},{lon}&zoom={zoom}&size=400x300"
        f"&markers={lat},{lon},red-pushpin"
    )
