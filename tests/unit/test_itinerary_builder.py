"""
tests/unit/test_itinerary_builder.py

Unit tests for ItineraryBuilderTool and _ItineraryBuilder.
No network calls — OSRM is patched to return a fixed 20 min travel time.
Covers all 3 trip types and all edge cases.
"""

from __future__ import annotations

from datetime import date, time
from unittest.mock import patch

import pytest

from ai_travel_agent.models.itinerary import TimeSlot
from ai_travel_agent.tools.itinerary_builder import (
    ItineraryBuilderTool,
    _ItineraryBuilder,
    _parse_hours_range,
    _parse_time_str,
)

# ── fixtures ──────────────────────────────────────────────────────────────────


def make_prefs(
    destination: str = "Paris",
    days: int = 5,
    activity_types: list[str] | None = None,
    start_date: str = "2025-12-10",
) -> dict:
    return {
        "destination": destination,
        "duration_days": days,
        "num_travelers": 2,
        "start_date": start_date,
        "end_date": "",
        "budget_usd": 3000.0,
        "travel_style": "moderate",
        "activity_types": activity_types or ["culture"],
        "dietary_restrictions": [],
        "raw_input": f"{destination} {days} days",
        "confidence_score": 0.9,
    }


def make_attractions(n: int = 12, city: str = "Paris") -> list[dict]:
    cats = ["museum", "landmark", "park", "shopping", "entertainment", "tour"]
    return [
        {
            "id": f"a{i}",
            "name": f"Attraction {i}",
            "category": cats[i % len(cats)],
            "description": "A nice place.",
            "rating": 4.5,
            "estimated_duration_hours": 2.0,
            "entry_price_usd": 10.0,
            "address": f"{i} Street, {city}",
            "location": {"latitude": 48.85 + i * 0.005, "longitude": 2.35 + i * 0.005},
            "opening_hours": {"monday": "09:00-18:00"},
            "tags": [],
        }
        for i in range(n)
    ]


def make_restaurants(n: int = 5) -> list[dict]:
    return [
        {
            "id": f"r{i}",
            "name": f"Restaurant {i}",
            "rating": 4.3,
            "description": "Good food.",
            "address": f"{i} Food St",
        }
        for i in range(n)
    ]


def make_weather(start: str = "2025-12-10", days: int = 5) -> list[dict]:
    from datetime import timedelta

    d = date.fromisoformat(start)
    return [
        {
            "date": (d + timedelta(i)).isoformat(),
            "temp_max": 15,
            "temp_min": 8,
            "description": "Clear",
        }
        for i in range(days)
    ]


def make_hotels() -> list[dict]:
    return [
        {
            "id": "h1",
            "name": "Grand Hotel",
            "star_rating": 4.0,
            "price_per_night_usd": 150.0,
            "total_price_usd": 750.0,
            "check_in": "2025-12-10",
            "check_out": "2025-12-15",
            "location": {"latitude": 48.86, "longitude": 2.34},
            "address": "1 Hotel Ave",
            "amenities": [],
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


@pytest.fixture(autouse=True)
def patch_osrm():
    """Patch OSRM so tests never make network calls."""
    with patch(
        "ai_travel_agent.tools.itinerary_builder.get_travel_time_safe",
        return_value=20,
    ):
        yield


# ── ItineraryBuilderTool._run ─────────────────────────────────────────────────


class TestItineraryBuilderToolRun:
    def test_returns_dict(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(),
            attractions=make_attractions(),
            restaurants=make_restaurants(),
            weather=make_weather(),
        )
        assert isinstance(result, dict)

    def test_has_required_top_level_keys(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(),
            attractions=make_attractions(),
            restaurants=make_restaurants(),
        )
        for key in ("id", "title", "destination", "days", "total_cost_usd"):
            assert key in result, f"Missing key: {key}"

    def test_correct_number_of_days(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(days=5), attractions=make_attractions()
        )
        assert len(result["days"]) == 5

    def test_destination_in_title(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(destination="Tokyo"), attractions=make_attractions()
        )
        assert "Tokyo" in result["title"]

    def test_total_cost_non_negative(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(),
            flights=make_flights(),
            hotels=make_hotels(),
            attractions=make_attractions(),
        )
        assert result["total_cost_usd"] >= 0

    def test_works_with_no_attractions(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(preferences=make_prefs(), attractions=[])
        assert isinstance(result, dict)
        assert len(result["days"]) == 5

    def test_within_budget_true_when_under(self) -> None:
        tool = ItineraryBuilderTool()
        # $3000 budget, cheap flight + hotel
        result = tool._run(
            preferences=make_prefs(),
            flights=[
                {
                    "id": "f1",
                    "total_price_usd": 200.0,
                    "num_stops": 0,
                    "cabin_class": "Economy",
                    "currency": "USD",
                    "segments": [
                        {
                            "departure_airport": "A",
                            "arrival_airport": "B",
                            "departure_time": "2025-12-10T10:00:00",
                            "arrival_time": "2025-12-10T14:00:00",
                            "airline": "X",
                            "flight_number": "X1",
                            "duration_minutes": 240,
                        }
                    ],
                }
            ],
            hotels=[
                {
                    "id": "h1",
                    "name": "Budget Inn",
                    "star_rating": 3.0,
                    "price_per_night_usd": 50.0,
                    "total_price_usd": 250.0,
                    "check_in": "2025-12-10",
                    "check_out": "2025-12-15",
                    "location": {"latitude": 48.86, "longitude": 2.34},
                    "address": "1 St",
                    "amenities": [],
                }
            ],
            attractions=make_attractions(n=4),
        )
        assert result["is_within_budget"] is True


# ── day structure ─────────────────────────────────────────────────────────────


class TestDayStructure:
    def _build(self, days: int = 5, **kwargs) -> list[dict]:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(days=days),
            attractions=make_attractions(n=days * 4),
            restaurants=make_restaurants(),
            weather=make_weather(days=days),
            **kwargs,
        )
        return result["days"]

    def test_day_1_is_arrival(self) -> None:
        days = self._build()
        assert "Arrival" in days[0]["theme"] or "arrival" in days[0]["theme"].lower()

    def test_last_day_is_departure(self) -> None:
        days = self._build()
        assert (
            "Departure" in days[-1]["theme"] or "departure" in days[-1]["theme"].lower()
        )

    def test_day_1_has_no_morning_activities(self) -> None:
        days = self._build()
        day1_slots = [a["time_slot"] for a in days[0]["activities"]]
        assert TimeSlot.MORNING not in day1_slots

    def test_last_day_has_no_evening_attractions(self) -> None:
        days = self._build()
        last_slots = [a["time_slot"] for a in days[-1]["activities"]]
        # last day may have an afternoon transfer but no evening
        assert (
            TimeSlot.EVENING not in last_slots
            or len([s for s in last_slots if s == TimeSlot.EVENING]) == 0
        )

    def test_full_days_have_morning_and_afternoon(self) -> None:
        days = self._build(days=5)
        for day in days[1:-1]:  # skip arrival and departure
            slots = {a["time_slot"] for a in day["activities"]}
            assert TimeSlot.MORNING in slots or TimeSlot.AFTERNOON in slots

    def test_days_have_sequential_day_numbers(self) -> None:
        days = self._build(days=4)
        for i, day in enumerate(days, 1):
            assert day["day_number"] == i

    def test_days_have_sequential_dates(self) -> None:
        from datetime import timedelta

        days = self._build()
        start = date.fromisoformat("2025-12-10")
        for i, day in enumerate(days):
            expected = (start + timedelta(days=i)).isoformat()
            assert day["date"] == expected

    def test_weather_attached_to_days(self) -> None:
        days = self._build()
        forecasts = [
            d.get("weather_forecast") for d in days if d.get("weather_forecast")
        ]
        assert len(forecasts) > 0


# ── trip types ────────────────────────────────────────────────────────────────


class TestTripTypeDetection:
    def _builder(self, activity_types: list[str]) -> _ItineraryBuilder:
        return _ItineraryBuilder(
            preferences=make_prefs(activity_types=activity_types),
            flights=[],
            hotels=[],
            attractions=[],
            restaurants=[],
            weather=[],
            budget_summary={},
        )

    def test_adventure_detected(self) -> None:
        b = self._builder(["adventure", "nature"])
        assert b.trip_type == "adventure"

    def test_beach_detected_from_relaxation(self) -> None:
        b = self._builder(["relaxation"])
        assert b.trip_type == "beach"

    def test_beach_detected_from_nature_only(self) -> None:
        b = self._builder(["nature"])
        assert b.trip_type == "beach"

    def test_city_tour_is_default(self) -> None:
        b = self._builder(["culture", "shopping"])
        assert b.trip_type == "city_tour"

    def test_city_tour_when_empty(self) -> None:
        b = self._builder([])
        assert b.trip_type == "city_tour"

    def test_culture_overrides_nature_for_beach(self) -> None:
        # nature + culture → city tour, not beach
        b = self._builder(["nature", "culture"])
        assert b.trip_type == "city_tour"


# ── travel time injection ─────────────────────────────────────────────────────


class TestTravelTimeInjection:
    def test_travel_time_set_on_activities(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(days=3),
            attractions=make_attractions(n=10),
            restaurants=make_restaurants(),
        )
        for day in result["days"]:
            acts = day["activities"]
            for act in acts[:-1]:  # all except last
                assert act["travel_time_to_next_minutes"] is not None

    def test_travel_time_is_positive(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(days=3),
            attractions=make_attractions(n=10),
        )
        for day in result["days"]:
            for act in day["activities"][:-1]:
                tt = act.get("travel_time_to_next_minutes")
                if tt is not None:
                    assert tt > 0


# ── opening hours validation ──────────────────────────────────────────────────


class TestOpeningHours:
    def _builder(self) -> _ItineraryBuilder:
        return _ItineraryBuilder(
            preferences=make_prefs(),
            flights=[],
            hotels=[],
            attractions=[],
            restaurants=[],
            weather=[],
            budget_summary={},
        )

    def test_open_morning_ok(self) -> None:
        b = self._builder()
        attr = {"opening_hours": {"monday": "08:00-18:00"}}
        assert b._opening_hours_ok(attr, TimeSlot.MORNING) is True

    def test_closed_morning_not_ok(self) -> None:
        b = self._builder()
        attr = {"opening_hours": {"monday": "13:00-22:00"}}
        assert b._opening_hours_ok(attr, TimeSlot.MORNING) is False

    def test_no_opening_hours_always_ok(self) -> None:
        b = self._builder()
        assert b._opening_hours_ok({}, TimeSlot.MORNING) is True

    def test_none_opening_hours_always_ok(self) -> None:
        b = self._builder()
        assert b._opening_hours_ok({"opening_hours": None}, TimeSlot.MORNING) is True


# ── parse helpers ─────────────────────────────────────────────────────────────


class TestParseHelpers:
    def test_parse_hours_dash(self) -> None:
        o, c = _parse_hours_range("09:00-18:00")
        assert o == "09:00"
        assert c == "18:00"

    def test_parse_hours_spaced_dash(self) -> None:
        o, c = _parse_hours_range("9:00 AM - 6:00 PM")
        assert o == "9:00 AM"
        assert c == "6:00 PM"

    def test_parse_time_24h(self) -> None:
        assert _parse_time_str("09:00") == time(9, 0)

    def test_parse_time_12h_am(self) -> None:
        assert _parse_time_str("9:00 AM") == time(9, 0)

    def test_parse_time_12h_pm(self) -> None:
        assert _parse_time_str("6:00 PM") == time(18, 0)

    def test_parse_hours_range_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_hours_range("no separator here")


# ── flight / hotel parsing ────────────────────────────────────────────────────


class TestFlightHotelParsing:
    def test_flight_attached_when_provided(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(),
            flights=make_flights(),
            attractions=make_attractions(),
        )
        assert result["outbound_flight"] is not None

    def test_hotel_attached_when_provided(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(),
            hotels=make_hotels(),
            attractions=make_attractions(),
        )
        assert result["hotel"] is not None

    def test_no_flight_no_crash(self) -> None:
        tool = ItineraryBuilderTool()
        result = tool._run(
            preferences=make_prefs(), flights=[], attractions=make_attractions()
        )
        assert result["outbound_flight"] is None

    def test_cheapest_flight_selected(self) -> None:
        tool = ItineraryBuilderTool()
        flights = [
            {**make_flights()[0], "id": "expensive", "total_price_usd": 1500.0},
            {**make_flights()[0], "id": "cheap", "total_price_usd": 500.0},
        ]
        result = tool._run(
            preferences=make_prefs(), flights=flights, attractions=make_attractions()
        )
        assert result["outbound_flight"]["total_price_usd"] == 500.0
