"""
Week 6 — ConflictDetector

Pure, deterministic checks (no LLM calls). Each check returns Conflict
objects; ConflictResolver decides what to do with them.
"""
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Callable

from ai_travel_agent.models.itinerary import DayPlan, Itinerary, ItineraryActivity


class ConflictType(str, Enum):
    TIME_OVERLAP = "time_overlap"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    OPENING_HOURS = "opening_hours"
    BUDGET_OVERRUN = "budget_overrun"
    MEAL_GAP = "meal_gap"
    TOO_MANY_ACTIVITIES = "too_many_activities"


class Severity(str, Enum):
    AUTO_FIXABLE = "auto_fixable"
    NEEDS_USER = "needs_user"


@dataclass
class Conflict:
    conflict_type: ConflictType
    severity: Severity
    day_number: int
    message: str
    activity_ids: list[str] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


class ConflictDetector:
    """Inject travel_time_fn: (from_latlng, to_latlng) -> minutes."""

    def __init__(
        self,
        travel_time_fn: Callable = lambda a, b: 15,
        max_activities_per_day: int = 5,
        lunch_window: tuple[time, time] = (time(12, 0), time(14, 30)),
        dinner_window: tuple[time, time] = (time(18, 0), time(21, 30)),
        min_transfer_buffer_min: int = 10,
    ):
        self.travel_time_fn = travel_time_fn
        self.max_activities = max_activities_per_day
        self.lunch_window = lunch_window
        self.dinner_window = dinner_window
        self.buffer = min_transfer_buffer_min

    # ── public API ──

    def detect_all(self, itinerary: Itinerary) -> list[Conflict]:
        out: list[Conflict] = []
        for day in itinerary.days:
            out += self._time_overlaps(day)
            out += self._impossible_travel(day)
            out += self._opening_hours(day)
            out += self._too_many_activities(day)
            out += self._meal_gaps(day)
        out += self._budget_overrun(itinerary)
        return out

    # ── checks ──

    def _sorted(self, day: DayPlan) -> list[ItineraryActivity]:
        return sorted(day.activities, key=lambda a: a.start_time or time(0))

    def _time_overlaps(self, day: DayPlan) -> list[Conflict]:
        acts = self._sorted(day)
        return [
            Conflict(ConflictType.TIME_OVERLAP, Severity.AUTO_FIXABLE, day.day_number,
                     f"'{a.title}' ends after '{b.title}' starts on day {day.day_number}",
                     [a.attraction_id or "", b.attraction_id or ""],
                     {"a_end": a.end_time.isoformat(), "b_start": b.start_time.isoformat()})
            for a, b in zip(acts, acts[1:])
            if a.end_time and b.start_time and a.end_time > b.start_time
        ]

    def _impossible_travel(self, day: DayPlan) -> list[Conflict]:
        out, acts = [], self._sorted(day)
        for a, b in zip(acts, acts[1:]):
            if not (a.end_time and b.start_time):
                continue
            gap = (datetime.combine(day.date, b.start_time)
                   - datetime.combine(day.date, a.end_time)).total_seconds() / 60
            if gap < 0:
                continue  # flagged by _time_overlaps
            needed = self.travel_time_fn(
                (a.latitude or 0, a.longitude or 0),
                (b.latitude or 0, b.longitude or 0),
            ) + self.buffer
            if gap < needed:
                out.append(Conflict(
                    ConflictType.IMPOSSIBLE_TRAVEL, Severity.AUTO_FIXABLE, day.day_number,
                    f"Only {gap:.0f}min between '{a.title}' and '{b.title}', need ~{needed}min",
                    [a.attraction_id or "", b.attraction_id or ""],
                    {"gap_min": gap, "needed_min": needed}))
        return out

    def _opening_hours(self, day: DayPlan) -> list[Conflict]:
        out = []
        for a in day.activities:
            if a.open_time and a.start_time and a.start_time < a.open_time:
                out.append(Conflict(
                    ConflictType.OPENING_HOURS, Severity.AUTO_FIXABLE, day.day_number,
                    f"'{a.title}' scheduled at {a.start_time} but opens at {a.open_time}",
                    [a.attraction_id or ""], {"required_start": a.open_time.isoformat()}))
            if a.close_time and a.end_time and a.end_time > a.close_time:
                out.append(Conflict(
                    ConflictType.OPENING_HOURS, Severity.AUTO_FIXABLE, day.day_number,
                    f"'{a.title}' ends at {a.end_time} but closes at {a.close_time}",
                    [a.attraction_id or ""], {"required_end": a.close_time.isoformat()}))
        return out

    def _too_many_activities(self, day: DayPlan) -> list[Conflict]:
        skip = {"restaurant", "flight", "hotel_checkin", "transfer"}
        non_util = [a for a in day.activities if a.activity_category not in skip]
        if len(non_util) > self.max_activities:
            return [Conflict(
                ConflictType.TOO_MANY_ACTIVITIES, Severity.NEEDS_USER, day.day_number,
                f"Day {day.day_number} has {len(non_util)} activities (max {self.max_activities})",
                [a.attraction_id or "" for a in non_util], {"count": len(non_util)})]
        return []

    def _meal_gaps(self, day: DayPlan) -> list[Conflict]:
        out = []
        meals = [a for a in day.activities if a.activity_category == "restaurant"]
        if not any(self.lunch_window[0] <= (m.start_time or time(0)) <= self.lunch_window[1] for m in meals):
            out.append(Conflict(ConflictType.MEAL_GAP, Severity.AUTO_FIXABLE, day.day_number,
                                f"No lunch scheduled in window on day {day.day_number}", [], {}))
        if not any(self.dinner_window[0] <= (m.start_time or time(0)) <= self.dinner_window[1] for m in meals):
            out.append(Conflict(ConflictType.MEAL_GAP, Severity.AUTO_FIXABLE, day.day_number,
                                f"No dinner scheduled in window on day {day.day_number}", [], {}))
        return out

    def _budget_overrun(self, itinerary: Itinerary) -> list[Conflict]:
        out = []
        total = sum(a.estimated_cost_usd for d in itinerary.days for a in d.activities)
        budget = itinerary.budget_usd or float("inf")
        if total > budget:
            out.append(Conflict(
                ConflictType.BUDGET_OVERRUN, Severity.NEEDS_USER, 0,
                f"Trip total ${total:.0f} exceeds budget ${budget:.0f}", [],
                {"total": total, "budget": budget,
                 "overrun_pct": round((total / budget - 1) * 100, 1)}))
        for d in itinerary.days:
            day_total = sum(a.estimated_cost_usd for a in d.activities)
            if d.daily_budget_usd and day_total > d.daily_budget_usd:
                out.append(Conflict(
                    ConflictType.BUDGET_OVERRUN, Severity.AUTO_FIXABLE, d.day_number,
                    f"Day {d.day_number} spend ${day_total:.0f} exceeds day budget ${d.daily_budget_usd:.0f}",
                    [a.attraction_id or "" for a in d.activities],
                    {"day_total": day_total, "day_budget": d.daily_budget_usd}))
        return out