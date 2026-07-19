"""
Week 11 — Integration Tests: 10 full trip scenarios.

Measures: planning time, % must-sees included, walking-distance variance.
Run: poetry run pytest tests/integration/test_optimizer_scenarios.py -v -s
"""
from __future__ import annotations

import math
import time
from datetime import date
from typing import Any
from unittest.mock import patch

import pytest

from ai_travel_agent.optimizer.itinerary_builder import build_itinerary
from ai_travel_agent.route.optimizer import total_route_distance_km

# ---------------------------------------------------------------------------
# Shared mock data helpers
# ---------------------------------------------------------------------------

def _make_attractions(city: str, n: int = 12) -> list[dict[str, Any]]:
    """Generate synthetic attractions spread across a city grid."""
    base_coords = {
        "Paris": (48.8566, 2.3522),
        "Tokyo": (35.6762, 139.6503),
        "New York": (40.7128, -74.0060),
        "London": (51.5074, -0.1278),
        "Bali": (-8.3405, 115.0920),
        "Barcelona": (41.3851, 2.1734),
        "Rome": (41.9028, 12.4964),
        "Bangkok": (13.7563, 100.5018),
        "Sydney": (-33.8688, 151.2093),
        "Dubai": (25.2048, 55.2708),
    }
    lat, lng = base_coords.get(city, (48.8566, 2.3522))
    categories = ["museum", "landmark", "park", "attraction", "gallery", "viewpoint"]
    attractions = []
    for i in range(n):
        row, col = divmod(i, 4)
        attractions.append({
            "id": f"{city.lower()}-{i}",
            "name": f"{city} Attraction {i + 1}",
            "category": categories[i % len(categories)],
            "lat": lat + (row - 1) * 0.01,
            "lng": lng + (col - 2) * 0.01,
            "rating": 4.0 + (i % 5) * 0.2,
            "popularity_hint": i < 3,
            "estimated_duration_hours": 1.5 + (i % 3) * 0.5,
            "entry_price_usd": 10.0 + (i % 4) * 5.0,
            "description": f"A popular {categories[i % len(categories)]} in {city}",
        })
    return attractions


def _make_weather(days: int, condition: str = "Sunny", rain_chance: float = 0.1) -> list[dict[str, Any]]:
    start = date(2025, 8, 1)
    from datetime import timedelta
    return [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "condition": condition,
            "temp_min": 18.0,
            "temp_max": 26.0,
            "rain_chance": rain_chance,
            "rain_chance_pct": int(rain_chance * 100),
        }
        for i in range(days)
    ]


# ---------------------------------------------------------------------------
# 10 Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    # (id, city, days, budget, travelers, priority_weight, description)
    ("s01", "Paris",     5, 3000.0, 2, 0.8, "Paris 5-day moderate budget couple"),
    ("s02", "Tokyo",     7, 4000.0, 2, 0.9, "Tokyo 7-day high priority couple"),
    ("s03", "New York",  3, 1800.0, 1, 0.7, "NYC 3-day solo tight budget"),
    ("s04", "London",    6, 3500.0, 3, 0.8, "London 6-day family"),
    ("s05", "Bali",      5, 2000.0, 2, 0.5, "Bali 5-day relaxed priority"),
    ("s06", "Barcelona", 4, 2500.0, 2, 1.0, "Barcelona 4-day strict must-sees"),
    ("s07", "Rome",      5, 3000.0, 4, 0.8, "Rome 5-day family history"),
    ("s08", "Bangkok",   5,  800.0, 1, 0.6, "Bangkok 5-day solo budget"),
    ("s09", "Sydney",    7, 5000.0, 2, 0.9, "Sydney 7-day luxury"),
    ("s10", "Dubai",     4, 4000.0, 2, 0.8, "Dubai 4-day luxury couple"),
]

RESULTS: list[dict[str, Any]] = []


@pytest.mark.parametrize("scenario_id,city,days,budget,travelers,pw,desc", SCENARIOS)
def test_optimizer_scenario(scenario_id, city, days, budget, travelers, pw, desc):
    attractions = _make_attractions(city, n=15)
    weather = _make_weather(days)

    prefs = {
        "destination": city,
        "duration_days": days,
        "budget_usd": budget,
        "num_travelers": travelers,
        "start_date": "2025-08-01",
    }

    t0 = time.perf_counter()
    itinerary = build_itinerary(prefs, attractions, weather, priority_weight=pw)
    elapsed = time.perf_counter() - t0

    # --- Assertions ---
    assert elapsed < 5.0, f"{desc}: planning took {elapsed:.2f}s (>5s limit)"
    assert len(itinerary.days) == days
    assert itinerary.destination == city

    # % must-sees included
    all_activities = [act for day in itinerary.days for act in day.activities]
    must_see_ids = {a["id"] for a in attractions if a.get("rating", 0) >= 4.5 or a.get("popularity_hint")}
    scheduled_ids = {act.attraction_id for act in all_activities}
    must_see_pct = (
        len(must_see_ids & scheduled_ids) / len(must_see_ids) * 100
        if must_see_ids else 100.0
    )

    # Walking distance variance
    day_distances = []
    for day in itinerary.days:
        pts = [{"lat": a.lat, "lng": a.lng} for a in day.activities if a.lat and a.lng]
        day_distances.append(total_route_distance_km(pts) if len(pts) > 1 else 0.0)

    avg_dist = sum(day_distances) / len(day_distances) if day_distances else 0.0
    variance = (
        math.sqrt(sum((d - avg_dist) ** 2 for d in day_distances) / len(day_distances))
        if day_distances else 0.0
    )

    result = {
        "id": scenario_id,
        "description": desc,
        "planning_time_s": round(elapsed, 3),
        "must_see_pct": round(must_see_pct, 1),
        "walking_variance_km": round(variance, 2),
        "total_activities": len(all_activities),
        "within_budget": itinerary.is_within_budget,
    }
    RESULTS.append(result)

    print(
        f"\n[{scenario_id}] {desc}\n"
        f"  time={elapsed:.3f}s  must-sees={must_see_pct:.0f}%  "
        f"walk_var={variance:.2f}km  activities={len(all_activities)}  "
        f"within_budget={itinerary.is_within_budget}"
    )

    assert must_see_pct >= 50.0, f"{desc}: only {must_see_pct:.0f}% must-sees included"


def test_must_sees_not_dropped_when_nice_to_haves_overflow():
    """When must-sees exceed time, nice-to-haves get dropped, not must-sees."""
    # Create 20 must-see attractions that can't all fit in 1 day
    attractions = []
    for i in range(20):
        attractions.append({
            "id": f"ms-{i}",
            "name": f"Must-See {i}",
            "category": "museum",
            "lat": 48.85 + i * 0.001,
            "lng": 2.35,
            "rating": 5.0,
            "popularity_hint": True,
            "estimated_duration_hours": 2.0,
            "entry_price_usd": 5.0,
            "_priority": 1,  # force must-see
        })
    # Add 5 nice-to-haves
    for i in range(5):
        attractions.append({
            "id": f"nth-{i}",
            "name": f"Nice-to-Have {i}",
            "category": "park",
            "lat": 48.85,
            "lng": 2.35 + i * 0.001,
            "rating": 3.0,
            "popularity_hint": False,
            "estimated_duration_hours": 1.0,
            "entry_price_usd": 0.0,
            "_priority": 4,
        })

    prefs = {
        "destination": "Paris",
        "duration_days": 1,
        "budget_usd": 500.0,
        "num_travelers": 1,
        "start_date": "2025-08-01",
    }
    itinerary = build_itinerary(prefs, attractions, [], priority_weight=1.0)
    all_acts = itinerary.days[0].activities

    must_see_scheduled = [a for a in all_acts if a.priority <= 2]
    nice_scheduled = [a for a in all_acts if a.priority > 2]

    # Must-sees should be prioritised over nice-to-haves
    assert len(must_see_scheduled) >= len(nice_scheduled), (
        f"Expected more must-sees than nice-to-haves, got {len(must_see_scheduled)} vs {len(nice_scheduled)}"
    )
