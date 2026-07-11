"""
tests/unit/test_week7_weather.py

Weather scoring + scheduling tests.
FakeLLM stub ensures no network calls — suite runs in <1s.
"""
import unittest
from datetime import date, time

from ai_travel_agent.models.itinerary import (
    Environment, Itinerary, ItineraryActivity, DayPlan, TimeSlot, WeatherForecast,
)
from ai_travel_agent.services.weather_scorer import WeatherRating, score_day, score_trip
from ai_travel_agent.services.weather_scheduler import (
    WeatherScheduler, _adaptation_rate, weather_adaptation_rate_metric,
)


# ── stubs ─────────────────────────────────────────────────────────────────────

class FakeLLM:
    """No network calls — stub generate() for deterministic tests."""
    def generate(self, prompt: str, system: str = "", **kw) -> str:
        return "Bring an umbrella."

    def generate_json(self, *a, **kw) -> dict:
        return {}


# ── helpers ───────────────────────────────────────────────────────────────────

def make_act(id_: str, title: str, start: time, end: time,
             env: Environment = Environment.MIXED) -> ItineraryActivity:
    return ItineraryActivity(
        time_slot=TimeSlot.MORNING,
        attraction_id=id_, title=title, description="", location_name="Test",
        start_time=start, end_time=end,
        activity_category="attraction", environment=env,
    )


def make_day(number: int, acts: list, the_date: date) -> DayPlan:
    return DayPlan(date=the_date, day_number=number, activities=acts)


def make_itin(days: list[DayPlan]) -> Itinerary:
    return Itinerary(
        id="t1", title="Test Trip", destination="Paris",
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 7),
        num_travelers=2, days=days,
    )


# ── scoring tests ─────────────────────────────────────────────────────────────

class TestWeatherScoring(unittest.TestCase):

    def test_clear_mild_day_is_good(self):
        f = WeatherForecast(the_date=date(2026, 8, 1), temp_c=22,
                            rain_probability=0.05, wind_kph=10, condition="clear")
        self.assertEqual(score_day(f).rating, WeatherRating.GOOD)

    def test_heavy_rain_is_poor(self):
        f = WeatherForecast(the_date=date(2026, 8, 1), temp_c=20,
                            rain_probability=0.9, wind_kph=15, condition="storm")
        self.assertEqual(score_day(f).rating, WeatherRating.POOR)

    def test_moderate_rain_is_moderate_or_poor(self):
        f = WeatherForecast(the_date=date(2026, 8, 1), temp_c=20,
                            rain_probability=0.45, wind_kph=15, condition="cloudy")
        self.assertIn(score_day(f).rating, (WeatherRating.MODERATE, WeatherRating.POOR))

    def test_extreme_heat_penalized(self):
        f = WeatherForecast(the_date=date(2026, 8, 1), temp_c=40,
                            rain_probability=0.0, wind_kph=5, condition="clear")
        self.assertLess(score_day(f).comfort_score, 100)


# ── scheduling tests ──────────────────────────────────────────────────────────

class TestWeatherAwareScheduling(unittest.TestCase):

    def setUp(self):
        self.forecasts = [
            WeatherForecast(the_date=date(2026, 8, 1), temp_c=22,
                            rain_probability=0.85, wind_kph=10, condition="storm"),  # POOR
            WeatherForecast(the_date=date(2026, 8, 2), temp_c=24,
                            rain_probability=0.05, wind_kph=8,  condition="clear"),  # GOOD
        ]
        outdoor = make_act("out1", "Rooftop Park Walk", time(10), time(12), env=Environment.OUTDOOR)
        indoor  = make_act("in1",  "City Museum",       time(10), time(12), env=Environment.INDOOR)
        day1 = make_day(1, [outdoor], date(2026, 8, 1))
        day2 = make_day(2, [indoor],  date(2026, 8, 2))
        self.itinerary = make_itin([day1, day2])

    # A/B: weather-aware scheduler improves adaptation rate
    def test_ab_comparison_weather_aware_improves_adaptation_rate(self):
        scores = score_trip(self.forecasts)
        rate_before = _adaptation_rate(self.itinerary, scores)
        result = WeatherScheduler(llm=FakeLLM()).adapt(self.itinerary, self.forecasts)
        self.assertGreaterEqual(result.adaptation_rate_after, rate_before)
        self.assertEqual(result.adaptation_rate_before, rate_before)

    # Outdoor activity moves off the rainy day
    def test_swap_moves_outdoor_activity_off_poor_day(self):
        result = WeatherScheduler(llm=FakeLLM()).adapt(self.itinerary, self.forecasts)
        day1_envs = [a.environment for a in result.itinerary.days[0].activities]
        self.assertIn(Environment.INDOOR, day1_envs)

    # Narrative generated for bad-weather days
    def test_narrative_generated_for_bad_weather_day(self):
        result = WeatherScheduler(llm=FakeLLM()).adapt(self.itinerary, self.forecasts)
        self.assertIn(1, result.narratives)
        self.assertGreater(len(result.narratives[1]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
