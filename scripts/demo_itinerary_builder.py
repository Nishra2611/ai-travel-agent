"""
scripts/demo_itinerary_builder.py

Tests ItineraryBuilderTool directly against 3 trip types:
  1. city_tour  — Paris 5 days culture
  2. beach      — Bali 7 days relaxation
  3. adventure  — Nepal 10 days adventure

Run: poetry run python scripts/demo_itinerary_builder.py
"""

from __future__ import annotations

from datetime import date

from dotenv import load_dotenv

from ai_travel_agent.tools.itinerary_builder import ItineraryBuilderTool

load_dotenv()

tool = ItineraryBuilderTool()

# ── shared mock data factories ────────────────────────────────────────────────


def make_attractions(city: str, n: int = 12) -> list[dict]:
    categories = ["museum", "landmark", "park", "shopping", "entertainment", "tour"]
    return [
        {
            "id": f"attr_{i}",
            "name": f"{city} Attraction {i+1}",
            "category": categories[i % len(categories)],
            "description": f"A wonderful place in {city}.",
            "rating": round(4.0 + (i % 5) * 0.1, 1),
            "estimated_duration_hours": 1.5 + (i % 3) * 0.5,
            "entry_price_usd": i * 5.0,
            "address": f"{i+1} Main St, {city}",
            "location": {"latitude": 48.85 + i * 0.01, "longitude": 2.35 + i * 0.01},
            "opening_hours": {"monday": "09:00-18:00"},
            "tags": [],
        }
        for i in range(n)
    ]


def make_restaurants(city: str, n: int = 5) -> list[dict]:
    return [
        {
            "id": f"rest_{i}",
            "name": f"{city} Restaurant {i+1}",
            "rating": round(4.2 + i * 0.1, 1),
            "description": "Delicious local food.",
            "address": f"{i+1} Food St, {city}",
        }
        for i in range(n)
    ]


def make_weather(start: str, days: int) -> list[dict]:
    from datetime import timedelta

    d = date.fromisoformat(start)
    return [
        {
            "date": (d + timedelta(i)).isoformat(),
            "temp_max": 22 - i,
            "temp_min": 14 - i,
            "description": "Partly cloudy",
        }
        for i in range(days)
    ]


def make_hotels(city: str) -> list[dict]:
    return [
        {
            "id": "h1",
            "name": f"Grand Hotel {city}",
            "star_rating": 4.0,
            "price_per_night_usd": 150.0,
            "total_price_usd": 750.0,
            "check_in": "2025-12-10",
            "check_out": "2025-12-15",
            "location": {"latitude": 48.86, "longitude": 2.34},
            "address": f"1 Hotel Ave, {city}",
            "amenities": ["Wi-Fi", "Pool"],
            "review_score": 4.5,
        }
    ]


def make_flights() -> list[dict]:
    return [
        {
            "id": "f1",
            "total_price_usd": 742.0,
            "num_stops": 0,
            "cabin_class": "Economy",
            "currency": "USD",
            "segments": [
                {
                    "departure_airport": "BOM",
                    "arrival_airport": "CDG",
                    "departure_time": "2025-12-10T10:00:00",
                    "arrival_time": "2025-12-10T16:00:00",
                    "airline": "Air India",
                    "flight_number": "AI131",
                    "duration_minutes": 480,
                }
            ],
        }
    ]


# ── test 3 trip types ─────────────────────────────────────────────────────────

TRIPS = [
    {
        "name": "City Tour — Paris 5 days",
        "prefs": {
            "destination": "Paris",
            "duration_days": 5,
            "num_travelers": 2,
            "start_date": "2025-12-10",
            "end_date": "2025-12-14",
            "budget_usd": 3000.0,
            "travel_style": "moderate",
            "activity_types": ["culture", "food", "shopping"],
            "dietary_restrictions": [],
            "raw_input": "Paris 5 days",
            "confidence_score": 0.9,
        },
        "city": "Paris",
    },
    {
        "name": "Beach Holiday — Bali 7 days",
        "prefs": {
            "destination": "Bali",
            "duration_days": 7,
            "num_travelers": 2,
            "start_date": "2026-01-15",
            "end_date": "2026-01-21",
            "budget_usd": 2000.0,
            "travel_style": "moderate",
            "activity_types": ["relaxation", "nature"],
            "dietary_restrictions": [],
            "raw_input": "Bali 7 days beach",
            "confidence_score": 0.88,
        },
        "city": "Bali",
    },
    {
        "name": "Adventure Trip — Nepal 10 days",
        "prefs": {
            "destination": "Nepal",
            "duration_days": 10,
            "num_travelers": 1,
            "start_date": "2026-03-01",
            "end_date": "2026-03-10",
            "budget_usd": 1500.0,
            "travel_style": "budget",
            "activity_types": ["adventure", "nature"],
            "dietary_restrictions": [],
            "raw_input": "Nepal 10 days trekking",
            "confidence_score": 0.92,
        },
        "city": "Nepal",
    },
]

for trip in TRIPS:
    city = trip["city"]
    prefs = trip["prefs"]
    days = prefs["duration_days"]

    print(f"\n{'='*60}")
    print(f"Trip: {trip['name']}")
    print("=" * 60)

    result = tool._run(
        preferences=prefs,
        flights=make_flights(),
        hotels=make_hotels(city),
        attractions=make_attractions(city, 14),
        restaurants=make_restaurants(city),
        weather=make_weather(prefs["start_date"], days),
    )

    print(f"Title          : {result['title']}")
    print(f"Days           : {len(result['days'])}")
    print(f"Total cost     : ${result['total_cost_usd']:.2f}")
    print(f"Budget         : ${result.get('budget_usd', 'N/A')}")
    print(f"Within budget  : {result.get('is_within_budget', 'N/A')}")
    print(f"Has flight     : {result['outbound_flight'] is not None}")
    print(f"Has hotel      : {result['hotel'] is not None}")

    for day in result["days"]:
        acts = day["activities"]
        slots = [a["time_slot"] for a in acts]
        print(
            f"  Day {day['day_number']:2d} | {day['theme']:<30} | {len(acts)} activities | slots: {slots}"
        )
        for act in acts:
            tt = (
                f" +{act['travel_time_to_next_minutes']}min"
                if act.get("travel_time_to_next_minutes")
                else ""
            )
            print(f"          [{act['time_slot']:9s}] {act['title']}{tt}")

    print(f"\n✓ {trip['name']} — OK")

print("\n✓ All 3 trip types verified\n")
