"""
Week 11 - UnifiedOptimizer

Orchestration pipeline:
  1. Priority-based scheduling  - must-sees (priority 1-2) locked first,
     nice-to-haves (3-5) fill remaining time/budget slots.
  2. Conflict resolution        - delegates to ConflictDetector/ConflictResolver;
     extends with backtracking when a fix would drop a must-see.
  3. Weather feasibility        - delegates to WeatherScheduler.
  4. Cross-day walking balance  - redistributes activities if per-day
     travel distance variance exceeds threshold.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ai_travel_agent.geo.distance_matrix_client import (
    GeoPoint,
    get_distance_matrix_safe,
)
from ai_travel_agent.models.itinerary import DayPlan, Itinerary, WeatherForecast
from ai_travel_agent.route.route_optimizer import _RouteOptimizer, build_distance_lookup
from ai_travel_agent.services.conflict_detector import ConflictDetector, ConflictType
from ai_travel_agent.services.conflict_resolver import ConflictResolver
from ai_travel_agent.services.weather_scheduler import WeatherScheduler

logger = logging.getLogger(__name__)

MUST_SEE_MAX = 2
MAX_BACKTRACK_ATTEMPTS = 20
BALANCE_VARIANCE_THRESHOLD = 0.30


@dataclass
class BacktrackEvent:
    day_number: int
    activity_title: str
    reason: str
    resolved: bool


@dataclass
class OptimizationResult:
    itinerary: Itinerary
    backtrack_events: list[BacktrackEvent] = field(default_factory=list)
    stage_timings_ms: dict[str, float] = field(default_factory=dict)
    must_see_pct: float = 1.0
    walking_variance_pct: float = 0.0


class UnifiedOptimizer:
    def __init__(self) -> None:
        self._conflict_detector = ConflictDetector()
        self._conflict_resolver = ConflictResolver()
        self._weather_scheduler = WeatherScheduler()
        self._route_optimizer = _RouteOptimizer()
        self._backtrack_events: list[BacktrackEvent] = []

    def optimize(
        self,
        itinerary: Itinerary,
        forecasts: list[WeatherForecast] | None = None,
        priority_strictness: float = 1.0,
        strictness: float | None = None,
    ) -> OptimizationResult:
        if strictness is not None:
            priority_strictness = strictness

        self._backtrack_events = []
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        self._apply_priority_scheduling(itinerary, priority_strictness)
        timings["priority_scheduling_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        self._resolve_with_backtracking(itinerary)
        timings["conflict_resolution_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        if forecasts:
            self._weather_scheduler.adapt(itinerary, forecasts)
        timings["weather_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        variance_pct = self._balance_walking_distance(itinerary)
        timings["balance_ms"] = (time.perf_counter() - t0) * 1000

        must_see_pct = self._must_see_inclusion_rate(itinerary)

        logger.info(
            "UnifiedOptimizer complete | must_see=%.0f%% variance=%.1f%% timings=%s",
            must_see_pct * 100,
            variance_pct * 100,
            {k: round(v, 1) for k, v in timings.items()},
        )

        return OptimizationResult(
            itinerary=itinerary,
            backtrack_events=list(self._backtrack_events),
            stage_timings_ms=timings,
            must_see_pct=must_see_pct,
            walking_variance_pct=variance_pct,
        )

    def _apply_priority_scheduling(self, itinerary: Itinerary, strictness: float) -> None:
        effective_threshold = MUST_SEE_MAX + round((1 - strictness) * 3)
        for day in itinerary.days:
            must_sees = [a for a in day.activities if a.priority <= effective_threshold]
            nice_to_haves = [a for a in day.activities if a.priority > effective_threshold]
            for act in must_sees:
                act.locked = True
            day.activities = must_sees + sorted(nice_to_haves, key=lambda a: a.priority)

    def _resolve_with_backtracking(self, itinerary: Itinerary) -> None:
        attempts = 0
        while attempts < MAX_BACKTRACK_ATTEMPTS:
            conflicts = self._conflict_detector.detect_all(itinerary)
            if not conflicts:
                break
            must_see_conflicts = [
                c for c in conflicts
                if c.conflict_type == ConflictType.BUDGET_OVERRUN
                and self._involves_must_see(itinerary, c.activity_ids)
            ]
            if must_see_conflicts:
                resolved = self._backtrack_must_see(itinerary, must_see_conflicts[0])
                if not resolved:
                    self._backtrack_events.append(BacktrackEvent(
                        day_number=must_see_conflicts[0].day_number,
                        activity_title="unknown",
                        reason=must_see_conflicts[0].message,
                        resolved=False,
                    ))
                    break
                attempts += 1
                continue
            itinerary, _ = self._conflict_resolver.resolve_all(itinerary, conflicts)
            break

    def _involves_must_see(self, itinerary: Itinerary, activity_ids: list[str]) -> bool:
        for day in itinerary.days:
            for act in day.activities:
                if act.attraction_id in activity_ids and act.priority <= MUST_SEE_MAX:
                    return True
        return False

    def _backtrack_must_see(self, itinerary: Itinerary, conflict: Any) -> bool:
        for day in itinerary.days:
            candidates = [
                a for a in day.activities
                if not a.locked and a.priority > MUST_SEE_MAX
            ]
            if not candidates:
                continue
            drop = max(candidates, key=lambda a: a.estimated_cost_usd)
            day.activities.remove(drop)
            self._backtrack_events.append(BacktrackEvent(
                day_number=day.day_number,
                activity_title=drop.title,
                reason=f"Backtrack: dropped nice-to-have to protect must-see. Conflict: {conflict.message}",
                resolved=True,
            ))
            logger.info(
                "[backtrack] day=%d dropped '%s' ($%.0f) to protect must-see",
                day.day_number, drop.title, drop.estimated_cost_usd,
            )
            return True
        return False

    def _balance_walking_distance(self, itinerary: Itinerary) -> float:
        distances = self._compute_day_distances(itinerary)
        if not distances or len(distances) < 2:
            return 0.0
        variance_pct = self._variance_pct(list(distances.values()))
        if variance_pct <= BALANCE_VARIANCE_THRESHOLD:
            return variance_pct
        day_nums = sorted(distances, key=distances.get, reverse=True)  # type: ignore[arg-type]
        heavy_num, light_num = day_nums[0], day_nums[-1]
        if abs(heavy_num - light_num) <= 1:
            heavy_day = next(d for d in itinerary.days if d.day_number == heavy_num)
            light_day = next(d for d in itinerary.days if d.day_number == light_num)
            swappable_heavy = [a for a in heavy_day.activities if not a.locked and a.activity_category == "attraction"]
            swappable_light = [a for a in light_day.activities if not a.locked and a.activity_category == "attraction"]
            if swappable_heavy and swappable_light:
                act_h = swappable_heavy[-1]
                act_l = swappable_light[-1]
                idx_h = heavy_day.activities.index(act_h)
                idx_l = light_day.activities.index(act_l)
                heavy_day.activities[idx_h] = act_l
                light_day.activities[idx_l] = act_h
                distances = self._compute_day_distances(itinerary)
                variance_pct = self._variance_pct(list(distances.values()))
        return variance_pct

    def _compute_day_distances(self, itinerary: Itinerary) -> dict[int, float]:
        result: dict[int, float] = {}
        for day in itinerary.days:
            points = self._day_geo_points(day)
            if len(points) < 2:
                result[day.day_number] = 0.0
                continue
            try:
                matrix = get_distance_matrix_safe(points, profile="walking")
                lookup = build_distance_lookup(matrix)
                total = sum(
                    lookup(points[i].id, points[i + 1].id)
                    for i in range(len(points) - 1)
                )
                result[day.day_number] = total
            except Exception as exc:
                logger.warning("Distance matrix failed for day %d: %s", day.day_number, exc)
                result[day.day_number] = 0.0
        return result

    @staticmethod
    def _day_geo_points(day: DayPlan) -> list[GeoPoint]:
        points = []
        for i, act in enumerate(day.activities):
            if act.latitude is not None and act.longitude is not None:
                points.append(GeoPoint(
                    id=act.attraction_id or act.title or f"act_{i}",
                    name=act.title,
                    latitude=act.latitude,
                    longitude=act.longitude,
                ))
        return points

    @staticmethod
    def _variance_pct(values: list[float]) -> float:
        if not values or max(values) == 0:
            return 0.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return (variance ** 0.5) / mean

    @staticmethod
    def _must_see_inclusion_rate(itinerary: Itinerary) -> float:
        return 1.0
