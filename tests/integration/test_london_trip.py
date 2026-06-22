# Target: tests/integration/test_london_trip.py
#
# Mocking note: this patches each tool's HTTP-calling functions at the point
# where the TOOL imports them (not where they're defined), since that's the
# name actually bound in the tool's module namespace. If your attraction_finder.py
# / restaurant_finder.py import these helpers under different names, update the
# patch targets below to match — `python -c "import ai_travel_agent.tools.attraction_finder as m; print(dir(m))"`
# will show you what's actually importable from each module.

from unittest.mock import patch

import fakeredis
import pytest

from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool

TRIP_ID = "london-5day-integration"

MOCK_GEOCODE = {"lat": 51.5074, "lng": -0.1278, "display_name": "London, UK"}

MOCK_ATTRACTIONS = [
    {
        "name": "Tower of London",
        "lat": 51.5081,
        "lng": -0.0759,
        "category": "attraction",
        "hours": "09:00-17:30",
        "popularity_hint": True,
        "rating": 4.6,
    },
    {
        "name": "British Museum",
        "lat": 51.5194,
        "lng": -0.1270,
        "category": "museum",
        "hours": "10:00-17:00",
        "popularity_hint": True,
        "rating": 4.8,
    },
    {
        "name": "London Eye",
        "lat": 51.5033,
        "lng": -0.1196,
        "category": "attraction",
        "hours": "11:00-18:00",
        "popularity_hint": True,
        "rating": 4.4,
    },
]

MOCK_RESTAURANTS = [
    {
        "name": "Padella",
        "lat": 51.505,
        "lng": -0.091,
        "rating": 4.5,
        "price_level": 1,
        "address": "6 Southwark St, London",
        "types": ["restaurant"],
    },
    {
        "name": "Dishoom",
        "lat": 51.512,
        "lng": -0.127,
        "rating": 4.7,
        "price_level": 1,
        "address": "12 Upper St Martin's Ln, London",
        "types": ["restaurant"],
    },
]

MOCK_WEATHER = [
    {
        "date": "2025-06-18",
        "condition": "Sunny",
        "temp_min": 13.0,
        "temp_max": 21.0,
        "rain_chance_pct": 10,
        "humidity_pct": 55,
    },
    {
        "date": "2025-06-19",
        "condition": "Cloudy",
        "temp_min": 12.0,
        "temp_max": 19.0,
        "rain_chance_pct": 20,
        "humidity_pct": 60,
    },
    {
        "date": "2025-06-20",
        "condition": "Light rain",
        "temp_min": 11.0,
        "temp_max": 17.0,
        "rain_chance_pct": 65,
        "humidity_pct": 78,
    },
    {
        "date": "2025-06-21",
        "condition": "Partly cloudy",
        "temp_min": 13.0,
        "temp_max": 20.0,
        "rain_chance_pct": 30,
        "humidity_pct": 58,
    },
    {
        "date": "2025-06-22",
        "condition": "Sunny",
        "temp_min": 14.0,
        "temp_max": 22.0,
        "rain_chance_pct": 5,
        "humidity_pct": 50,
    },
]


@pytest.fixture
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_london_five_day_trip(fake_redis):
    with (
        patch(
            "ai_travel_agent.tools.attraction_finder.geocode", return_value=MOCK_GEOCODE
        ),
        patch(
            "ai_travel_agent.tools.attraction_finder.overpass_attractions_near",
            return_value=MOCK_ATTRACTIONS,
        ),
        patch("ai_travel_agent.tools.attraction_finder.web_search", return_value=[]),
        patch(
            "ai_travel_agent.tools.restaurant_finder.places_text_search",
            return_value=MOCK_RESTAURANTS,
        ),
        patch(
            "ai_travel_agent.tools.weather_checker.geocode", return_value=MOCK_GEOCODE
        ),
        patch.object(WeatherCheckerTool, "_forecast5", return_value=MOCK_WEATHER),
        patch("ai_travel_agent.utils.cache.get_redis_client", return_value=fake_redis),
    ):

        attractions = AttractionFinderTool()._run(city="London", country="UK", limit=10)
        assert 1 <= len(attractions) <= 10
        assert all({"name", "lat", "lng"}.issubset(a.keys()) for a in attractions)

        restaurants = RestaurantFinderTool()._run(
            city="London", cuisine="Italian", budget="$$", min_rating=4.0, limit=10
        )
        assert all(r["rating"] >= 4.0 for r in restaurants)

        import os

        os.environ["OPENWEATHERMAP_API_KEY"] = "test-key"
        weather = WeatherCheckerTool()._run(city="London", days=5)
        assert len(weather) == 5
        assert all(
            {"date", "condition", "temp_min", "temp_max"}.issubset(d.keys())
            for d in weather
        )

        budget = BudgetTrackerTool()
        budget._run(trip_id=TRIP_ID, action="set_budget", total_budget=1500.0)
        budget._run(
            trip_id=TRIP_ID,
            action="add_expense",
            category="accommodation",
            amount=600.0,
            description="4 nights hotel",
        )
        for r in restaurants[:2]:
            budget._run(
                trip_id=TRIP_ID,
                action="add_expense",
                category="food",
                amount=35.0,
                description=r["name"],
            )
        for a in attractions[:2]:
            budget._run(
                trip_id=TRIP_ID,
                action="add_expense",
                category="attractions",
                amount=20.0,
                description=a["name"],
            )

        summary = budget._run(trip_id=TRIP_ID, action="get_summary")
        expected_spent = 600.0 + 2 * 35.0 + 2 * 20.0
        assert summary["spent_total"] == expected_spent
        assert summary["remaining"] == 1500.0 - expected_spent
        assert set(summary["by_category"].keys()) == {
            "accommodation",
            "food",
            "attractions",
        }


def test_budget_isolated_per_trip(fake_redis):
    with patch("ai_travel_agent.utils.cache.get_redis_client", return_value=fake_redis):
        budget = BudgetTrackerTool()
        budget._run(trip_id="trip-one", action="set_budget", total_budget=500.0)
        budget._run(trip_id="trip-two", action="set_budget", total_budget=2000.0)

        s1 = budget._run(trip_id="trip-one", action="get_summary")
        s2 = budget._run(trip_id="trip-two", action="get_summary")

        assert s1["total_budget"] == 500.0
        assert s2["total_budget"] == 2000.0
