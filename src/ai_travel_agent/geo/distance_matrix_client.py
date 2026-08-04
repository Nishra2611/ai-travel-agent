"""
ai_travel_agent/geo/distance_matrix_client.py — Week 9

Pairwise travel time/distance between attractions/hotels, using the OSRM
Table Service — same stack as ai_travel_agent/clients/travel_time_client.py
(Week 5/6), which already hits OSRM's Route Service for single pairs and
falls back to Haversine via get_travel_time_safe. This file is the N-point
generalization of that: one OSRM Table call computes the full distance/
duration matrix for up to ~100 points in a single request, instead of
looping get_travel_time_safe over every pair (which would be O(n^2)
separate HTTP calls).

Why OSRM Table and not Google Distance Matrix: same reasoning as
travel_time_client.py -- GOOGLE_PLACES_API_KEY doesn't cover Distance
Matrix (separate API, separate billing), OSRM is free/keyless, and staying
on one routing stack means one failure mode to handle instead of two.
get_distance_matrix_safe follows the exact same safe-fallback shape as
get_travel_time_safe: OSRM being down or rate-limited never crashes the
graph, it silently degrades to Haversine-estimated distances (with duration
estimated from an assumed walking speed).

Drop this file at: ai_travel_agent/geo/distance_matrix_client.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import requests

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

OSRM_TABLE_URL = "http://router.project-osrm.org/table/v1/{profile}/{coords}"
REQUEST_TIMEOUT_SECONDS = 8
MAX_POINTS_PER_CALL = 100  # OSRM demo server's practical ceiling

# Used for the Haversine fallback's duration estimate when OSRM is
# unavailable -- rough average walking speed in m/s.
ASSUMED_WALKING_SPEED_MPS = 1.35
EARTH_RADIUS_METERS = 6_371_000


@dataclass
class GeoPoint:
    id: str
    name: str
    latitude: float
    longitude: float


@dataclass
class DistanceEntry:
    origin_id: str
    destination_id: str
    distance_meters: float
    duration_seconds: float
    source: str  # "osrm" | "haversine_fallback"


@dataclass
class DistanceMatrix:
    points: list[GeoPoint]
    entries: list[DistanceEntry]
    source: str  # "osrm" | "haversine_fallback" -- whole-matrix source, mixed never happens (one call, one outcome)

    def duration_between(self, origin_id: str, destination_id: str) -> float | None:
        for e in self.entries:
            if e.origin_id == origin_id and e.destination_id == destination_id:
                return e.duration_seconds
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "entries": [
                {
                    "origin_id": e.origin_id,
                    "destination_id": e.destination_id,
                    "distance_meters": round(e.distance_meters, 1),
                    "duration_seconds": round(e.duration_seconds, 1),
                }
                for e in self.entries
            ],
        }


def get_distance_matrix_safe(
    points: list[GeoPoint], profile: str = "walking"
) -> DistanceMatrix:
    """
    Never raises. Tries OSRM Table Service first; on any failure (network
    error, timeout, non-200, malformed response, or more points than
    MAX_POINTS_PER_CALL) falls back to Haversine-estimated distances for
    every pair, same contract as get_travel_time_safe.
    """
    if len(points) < 2:
        return DistanceMatrix(points=points, entries=[], source="osrm")

    if len(points) > MAX_POINTS_PER_CALL:
        logger.warning(
            "too many points for one OSRM table call, falling back to haversine",
            extra={"num_points": len(points), "max": MAX_POINTS_PER_CALL},
        )
        return _haversine_matrix(points)

    try:
        return _osrm_table_call(points, profile)
    except (
        Exception
    ) as exc:  # noqa: BLE001 -- deliberate: any failure mode falls back silently
        logger.warning(
            "OSRM table call failed, falling back to haversine",
            extra={"error": str(exc)},
        )
        return _haversine_matrix(points)


def _osrm_table_call(points: list[GeoPoint], profile: str) -> DistanceMatrix:
    coords = ";".join(f"{p.longitude},{p.latitude}" for p in points)
    url = OSRM_TABLE_URL.format(profile=profile, coords=coords)
    response = requests.get(
        url,
        params={"annotations": "distance,duration"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(f"OSRM returned code={data.get('code')}")

    durations = data["durations"]
    distances = data.get("distances") or [[None] * len(points) for _ in points]

    entries = []
    for i, origin in enumerate(points):
        for j, destination in enumerate(points):
            if i == j:
                continue
            duration = durations[i][j]
            distance = distances[i][j]
            if duration is None:
                continue  # OSRM couldn't route this pair (e.g. island with no bridge)
            entries.append(
                DistanceEntry(
                    origin_id=origin.id,
                    destination_id=destination.id,
                    distance_meters=(
                        distance
                        if distance is not None
                        else _haversine_meters(origin, destination)
                    ),
                    duration_seconds=duration,
                    source="osrm",
                )
            )
    return DistanceMatrix(points=points, entries=entries, source="osrm")


def _haversine_matrix(points: list[GeoPoint]) -> DistanceMatrix:
    entries = []
    for origin in points:
        for destination in points:
            if origin.id == destination.id:
                continue
            distance = _haversine_meters(origin, destination)
            duration = distance / ASSUMED_WALKING_SPEED_MPS
            entries.append(
                DistanceEntry(
                    origin_id=origin.id,
                    destination_id=destination.id,
                    distance_meters=distance,
                    duration_seconds=duration,
                    source="haversine_fallback",
                )
            )
    return DistanceMatrix(points=points, entries=entries, source="haversine_fallback")


def _haversine_meters(a: GeoPoint, b: GeoPoint) -> float:
    lat1, lon1, lat2, lon2 = map(
        math.radians, [a.latitude, a.longitude, b.latitude, b.longitude]
    )
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(h))
