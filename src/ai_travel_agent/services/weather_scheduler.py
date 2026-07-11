"""
Week 7 — WeatherScheduler.

Algorithm:
1. Score every day via weather_scorer.score_trip.
2. For each POOR-weather day, find outdoor attraction activities and try
   to swap them with an indoor attraction from a GOOD/MODERATE day within
   a configurable lookahead window.
3. If no swap candidate exists, flag it (weather can't always be fixed).
4. Generate a one-line narrative warning per affected day via Ollama.
5. Report adaptation_rate before/after for the A/B evaluation metric.
"""
from dataclasses import dataclass, field

from ai_travel_agent.models.itinerary import (
    DayPlan,
    Environment,
    Itinerary,
    ItineraryActivity,
    WeatherForecast,
)
from ai_travel_agent.services.ollama_client import OllamaClient
from ai_travel_agent.services.weather_scorer import (
    WeatherRating,
    WeatherScore,
    score_trip,
)


@dataclass
class WeatherSwap:
    day_from: int
    day_to: int
    activity_moved: str


@dataclass
class WeatherAdaptationResult:
    itinerary: Itinerary
    swaps: list[WeatherSwap] = field(default_factory=list)
    narratives: dict[int, str] = field(default_factory=dict)
    adaptation_rate_before: float = 1.0
    adaptation_rate_after: float = 1.0


def _is_matched(act: ItineraryActivity, rating: WeatherRating) -> bool:
    if act.environment == Environment.MIXED:
        return True
    if rating == WeatherRating.POOR:
        return act.environment == Environment.INDOOR
    return True  # GOOD/MODERATE: indoor or outdoor both fine


def _adaptation_rate(itinerary: Itinerary, scores: dict) -> float:
    total = matched = 0
    for day in itinerary.days:
        rating = scores[day.date].rating if day.date in scores else WeatherRating.MODERATE
        for a in day.activities:
            if a.activity_category != "attraction":
                continue
            total += 1
            if _is_matched(a, rating):
                matched += 1
    return round(matched / total, 3) if total else 1.0


class WeatherScheduler:
    def __init__(self, llm: OllamaClient | None = None, lookahead_days: int = 2):
        self.llm = llm or OllamaClient()
        self.lookahead_days = lookahead_days

    def adapt(self, itinerary: Itinerary, forecasts: list[WeatherForecast]) -> WeatherAdaptationResult:
        scores = score_trip(forecasts)
        rate_before = _adaptation_rate(itinerary, scores)
        by_day = {d.day_number: d for d in itinerary.days}
        swaps: list[WeatherSwap] = []

        for day in itinerary.days:
            ws: WeatherScore | None = scores.get(day.date)
            if not ws or ws.rating != WeatherRating.POOR:
                continue
            for act in list(day.activities):
                if act.activity_category != "attraction" or act.environment != Environment.OUTDOOR or act.locked:
                    continue
                target = self._find_swap_target(day, by_day, scores)
                if not target:
                    continue
                indoor = next((a for a in target.activities
                               if a.activity_category == "attraction"
                               and a.environment == Environment.INDOOR
                               and not a.locked), None)
                if not indoor:
                    continue
                self._swap(day, target, act, indoor)
                swaps.append(WeatherSwap(day.day_number, target.day_number, act.title))

        narratives = self._generate_narratives(itinerary, scores)
        return WeatherAdaptationResult(
            itinerary=itinerary,
            swaps=swaps,
            narratives=narratives,
            adaptation_rate_before=rate_before,
            adaptation_rate_after=_adaptation_rate(itinerary, scores),
        )

    # ── internals ──

    def _find_swap_target(self, poor: DayPlan, by_day: dict, scores: dict) -> DayPlan | None:
        for offset in range(1, self.lookahead_days + 1):
            for num in (poor.day_number + offset, poor.day_number - offset):
                cand = by_day.get(num)
                if not cand:
                    continue
                ws = scores.get(cand.date)
                if ws and ws.rating in (WeatherRating.GOOD, WeatherRating.MODERATE):
                    return cand
        return None

    @staticmethod
    def _swap(day_a: DayPlan, day_b: DayPlan, act_a: ItineraryActivity, act_b: ItineraryActivity):
        """Swap two activities between days; preserve original time slots."""
        act_a.start_time, act_b.start_time = act_b.start_time, act_a.start_time
        act_a.end_time, act_b.end_time = act_b.end_time, act_a.end_time
        idx_a, idx_b = day_a.activities.index(act_a), day_b.activities.index(act_b)
        day_a.activities[idx_a], day_b.activities[idx_b] = act_b, act_a

    def _generate_narratives(self, itinerary: Itinerary, scores: dict) -> dict[int, str]:
        out: dict[int, str] = {}
        for day in itinerary.days:
            ws: WeatherScore | None = scores.get(day.date)
            if not ws or ws.rating == WeatherRating.GOOD:
                continue
            prompt = (
                f"Day {day.day_number} forecast: {', '.join(ws.reasons) or 'mild weather'}, "
                f"comfort score {ws.comfort_score}/100. "
                f"Write ONE short, practical packing/planning tip for the traveler (max 20 words)."
            )
            out[day.day_number] = self.llm.generate(prompt, system="You are a concise travel assistant.")
        return out


def weather_adaptation_rate_metric(result: WeatherAdaptationResult) -> dict:
    """Ready-to-log metric block for the Week 12 evaluation dashboard."""
    return {
        "adaptation_rate_before": result.adaptation_rate_before,
        "adaptation_rate_after": result.adaptation_rate_after,
        "improvement_pp": round((result.adaptation_rate_after - result.adaptation_rate_before) * 100, 1),
        "swaps_made": len(result.swaps),
    }
