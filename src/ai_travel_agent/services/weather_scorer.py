"""
Week 7 — Weather comfort scorer.

comfort_score in [0, 100]:
  - starts at 100
  - rain_probability penalty: up to -75 (75 * probability)
  - wind penalty:   up to -20 (clipped, ramps above 20 kph)
  - temperature discomfort penalty: up to -30 (ideal band 18–26 °C)

Score bands → WeatherRating used by the scheduler to decide swaps.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum

from ai_travel_agent.models.itinerary import WeatherForecast


class WeatherRating(str, Enum):
    GOOD = "good"        # score >= 70: outdoor-friendly
    MODERATE = "moderate"  # 40–69: caution
    POOR = "poor"          # < 40: push indoor activities


IDEAL_LOW, IDEAL_HIGH = 18.0, 26.0


@dataclass
class WeatherScore:
    the_date: date
    comfort_score: float
    rating: WeatherRating
    reasons: list[str]


def score_day(forecast: WeatherForecast) -> WeatherScore:
    score, reasons = 100.0, []

    rain_penalty = forecast.rain_probability * 75.0
    if forecast.rain_probability >= 0.3:
        reasons.append(f"{forecast.rain_probability * 100:.0f}% rain chance")
    score -= rain_penalty

    wind_penalty = min(20.0, max(0.0, (forecast.wind_kph - 20) / 2))
    if forecast.wind_kph >= 30:
        reasons.append(f"windy ({forecast.wind_kph:.0f} kph)")
    score -= wind_penalty

    if forecast.temp_c < IDEAL_LOW:
        t_pen = min(30.0, (IDEAL_LOW - forecast.temp_c) * 3.0)
        reasons.append(f"cold ({forecast.temp_c:.0f}°C)")
    elif forecast.temp_c > IDEAL_HIGH:
        t_pen = min(30.0, (forecast.temp_c - IDEAL_HIGH) * 3.0)
        reasons.append(f"hot ({forecast.temp_c:.0f}°C)")
    else:
        t_pen = 0.0
    score -= t_pen

    score = max(0.0, min(100.0, score))
    rating = WeatherRating.GOOD if score >= 70 else (WeatherRating.MODERATE if score >= 40 else WeatherRating.POOR)
    return WeatherScore(forecast.the_date, round(score, 1), rating, reasons)


def score_trip(forecasts: list[WeatherForecast]) -> dict:
    """date -> WeatherScore, O(1) lookup for the scheduler."""
    return {f.the_date: score_day(f) for f in forecasts}
