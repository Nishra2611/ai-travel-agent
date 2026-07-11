"""
ai_travel_agent/services/travel_time_client.py

Travel time estimation between two coordinates.
Uses OSRM public API — free, no key, no billing.
Consistent with geocode_client.py which also uses Nominatim (free OSM stack).

Falls back to Haversine estimate when OSRM is unreachable.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

OSRM_URL = "http://router.project-osrm.org/route/v1/driving"
_TIMEOUT = 8


@retry(wait=wait_fixed(1.1), stop=stop_after_attempt(3))
def get_travel_time_minutes(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> int:
    """Return driving minutes between two lat/lng pairs. Raises on failure."""
    coords = f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
    resp = httpx.get(
        f"{OSRM_URL}/{coords}",
        params={"overview": "false", "steps": "false"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"OSRM no route: {data.get('code')}")
    duration = float(data["routes"][0]["duration"])
    return max(1, round(duration / 60))


def get_travel_time_safe(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    fallback_speed_kmh: float = 30.0,
) -> int:
    """Never raises. Returns OSRM result or Haversine fallback."""
    try:
        return get_travel_time_minutes(origin_lat, origin_lng, dest_lat, dest_lng)
    except Exception as exc:
        logger.warning("OSRM unavailable (%s) — Haversine fallback", exc)
        return _haversine_minutes(
            origin_lat, origin_lng, dest_lat, dest_lng, fallback_speed_kmh
        )


def _haversine_minutes(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    speed_kmh: float,
) -> int:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    km = r * 2 * math.asin(math.sqrt(a))
    return max(5, round((km / speed_kmh) * 60))
