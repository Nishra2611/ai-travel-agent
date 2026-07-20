"""
Week 11 — Unified Multi-Constraint Itinerary Optimizer.

Pipeline: cluster POIs → optimize route → weather check → budget validation
Features: priority-based scheduling, backtracking, cross-day walking balance.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from ai_travel_agent.geo.clustering import cluster_attractions
from ai_travel_agent.models.itinerary import (
    DayPlan,
    Itinerary,
    ItineraryActivity,
    TimeSlot,
)
from ai_travel_agent.route.optimizer import optimize_route, total_route_distance_km

logger = logging.getLogger(__name__)

# Hours available per time slot
SLOT_HOURS: dict[str, float] = {
    TimeSlot.MORNING: 3.5,
    TimeSlot.AFTERNOON: 3.5,
    TimeSlot.EVENING: 2.0,
}
SLOTS_ORDER = [TimeSlot.MORNING, TimeSlot.AFTERNOON, TimeSlot.EVENING]

# Cross-day balance: rebalance if distance variance ratio exceeds this
BALANCE_VARIANCE_THRESHOLD = 0.30

# Backtracking cap
MAX_BACKTRACK_ATTEMPTS = 20


def _is_outdoor(activity: dict[str, Any]) -> bool:
    outdoor_cats = {"park", "viewpoint", "garden", "beach", "nature", "hiking"}
    cat = str(activity.get("category", "")).lower()
    return any(o in cat for o in outdoor_cats)


def _weather_ok(activity: dict[str, Any], forecast: dict[str, Any] | None) -> bool:
    if forecast is None:
        return True
    if not _is_outdoor(activity):
        return True
    rain = forecast.get("rain_chance", forecast.get("rain_chance_pct", 0))
    if isinstance(rain, float) and rain <= 1.0:
        rain = rain * 100
    return float(rain) < 60


def _activity_cost(attraction: dict[str, Any]) -> float:
    return float(attraction.get("entry_price_usd") or attraction.get("price", 0) or 0)


def _activity_duration(attraction: dict[str, Any]) -> float:
    return float(attraction.get("estimated_duration_hours") or 2.0)


def _make_activity(
    attraction: dict[str, Any], slot: TimeSlot, priority: int
) -> ItineraryActivity:
    return ItineraryActivity(
        time_slot=slot,
        attraction_id=str(attraction.get("id") or attraction.get("name", "")),
        title=str(attraction.get("name", "Activity")),
        description=str(
            attraction.get("description") or attraction.get("category") or ""
        ),
        location_name=str(attraction.get("address") or attraction.get("name", "")),
        estimated_cost_usd=_activity_cost(attraction),
        estimated_duration_hours=_activity_duration(attraction),
        priority=priority,
        lat=attraction.get("lat"),
        lng=attraction.get("lng"),
    )


def _schedule_day(
    day_attractions: list[dict[str, Any]],
    day_budget: float,
    forecast: dict[str, Any] | None,
    priority_weight: float,
    backtrack_log: list[str],
    day_label: str,
) -> tuple[list[ItineraryActivity], float]:
    """
    Schedule attractions into morning/afternoon/evening slots.
    Must-sees (priority 1-2) are placed first; nice-to-haves fill gaps.
    Returns (activities, cost_used).
    Implements backtracking when a must-see can't fit in its preferred slot.
    """
    must_sees = [a for a in day_attractions if a.get("_priority", 3) <= 2]
    nice_to_haves = sorted(
        [a for a in day_attractions if a.get("_priority", 3) > 2],
        key=lambda a: a.get("_priority", 3),
    )

    slot_remaining: dict[str, float] = dict(SLOT_HOURS)
    budget_remaining = day_budget
    activities: list[ItineraryActivity] = []
    backtrack_attempts = 0

    def try_place(attraction: dict[str, Any], is_must_see: bool) -> bool:
        nonlocal budget_remaining, backtrack_attempts
        cost = _activity_cost(attraction)
        duration = _activity_duration(attraction)
        priority = attraction.get("_priority", 3)

        if cost > budget_remaining:
            if is_must_see and backtrack_attempts < MAX_BACKTRACK_ATTEMPTS:
                # Backtrack: drop the last nice-to-have to free budget
                for i in range(len(activities) - 1, -1, -1):
                    if activities[i].priority > 2:
                        freed_cost = activities[i].estimated_cost_usd
                        freed_dur = activities[i].estimated_duration_hours
                        freed_slot = activities[i].time_slot
                        activities.pop(i)
                        budget_remaining += freed_cost
                        slot_remaining[freed_slot] += freed_dur
                        backtrack_attempts += 1
                        backtrack_log.append(
                            f"{day_label}: backtrack — dropped '{activities[i].title if i < len(activities) else 'activity'}' "
                            f"to fit must-see '{attraction['name']}' (budget freed ${freed_cost:.0f})"
                        )
                        break
                else:
                    return False
            else:
                return False

        if not _weather_ok(attraction, forecast):
            if is_must_see:
                backtrack_log.append(
                    f"{day_label}: weather blocked outdoor must-see '{attraction['name']}', skipping"
                )
            return False

        # Find a slot with enough time
        for slot in SLOTS_ORDER:
            if slot_remaining[slot] >= duration:
                activities.append(_make_activity(attraction, slot, priority))
                slot_remaining[slot] -= duration
                budget_remaining -= cost
                return True

        # No slot fits — try backtracking for must-sees
        if is_must_see and backtrack_attempts < MAX_BACKTRACK_ATTEMPTS:
            for i in range(len(activities) - 1, -1, -1):
                if activities[i].priority > 2:
                    freed_slot = activities[i].time_slot
                    freed_dur = activities[i].estimated_duration_hours
                    freed_cost = activities[i].estimated_cost_usd
                    dropped_title = activities[i].title
                    activities.pop(i)
                    slot_remaining[freed_slot] += freed_dur
                    budget_remaining += freed_cost
                    backtrack_attempts += 1
                    backtrack_log.append(
                        f"{day_label}: backtrack — dropped '{dropped_title}' "
                        f"to fit must-see '{attraction['name']}' (freed {freed_dur:.1f}h in {freed_slot})"
                    )
                    if slot_remaining[freed_slot] >= duration:
                        activities.append(
                            _make_activity(attraction, freed_slot, priority)
                        )
                        slot_remaining[freed_slot] -= duration
                        budget_remaining -= cost
                        return True

        return False

    for a in must_sees:
        try_place(a, is_must_see=True)

    for a in nice_to_haves:
        if backtrack_attempts >= MAX_BACKTRACK_ATTEMPTS:
            break
        try_place(a, is_must_see=False)

    cost_used = day_budget - budget_remaining
    return activities, cost_used


def _rebalance_days(
    day_buckets: list[list[dict[str, Any]]],
) -> list[list[dict[str, Any]]]:
    """Swap attractions between adjacent days to even out walking distance."""
    if len(day_buckets) < 2:
        return day_buckets

    distances = [
        total_route_distance_km(optimize_route(b)) if b else 0.0 for b in day_buckets
    ]
    avg_dist = sum(distances) / len(distances) if distances else 0.0
    if avg_dist == 0:
        return day_buckets

    variance_ratio = max(
        abs(d - avg_dist) / avg_dist for d in distances if avg_dist > 0
    )
    if variance_ratio <= BALANCE_VARIANCE_THRESHOLD:
        return day_buckets

    # Simple swap: move one attraction from the heaviest day to the lightest
    max_day = max(range(len(distances)), key=lambda i: distances[i])
    min_day = min(range(len(distances)), key=lambda i: distances[i])

    if day_buckets[max_day] and max_day != min_day:
        # Move the last nice-to-have from heavy day to light day
        for i in range(len(day_buckets[max_day]) - 1, -1, -1):
            a = day_buckets[max_day][i]
            if a.get("_priority", 3) > 2:
                day_buckets[min_day].append(day_buckets[max_day].pop(i))
                logger.debug(
                    "Rebalanced: moved '%s' from day %d to day %d",
                    a.get("name"),
                    max_day + 1,
                    min_day + 1,
                )
                break

    return day_buckets


def build_itinerary(
    preferences: dict[str, Any],
    attractions: list[dict[str, Any]],
    weather_forecast: list[dict[str, Any]],
    priority_weight: float = 0.8,
) -> Itinerary:
    """
    Unified optimizer pipeline:
      1. Cluster POIs by geography
      2. Optimize route per day
      3. Check weather feasibility
      4. Schedule with priority + backtracking
      5. Validate budget
      6. Cross-day walking balance

    priority_weight: 0.0 = treat all as nice-to-have, 1.0 = strictly enforce must-sees
    """
    t0 = time.perf_counter()

    destination = str(preferences.get("destination", "Unknown"))
    duration_days = int(preferences.get("duration_days", 3))
    budget_usd = float(preferences.get("budget_usd") or 1000.0)
    num_travelers = int(preferences.get("num_travelers", 1))
    start_date_raw = preferences.get("start_date")

    if isinstance(start_date_raw, date):
        start_date = start_date_raw
    elif isinstance(start_date_raw, str):
        try:
            start_date = date.fromisoformat(start_date_raw)
        except ValueError:
            start_date = date.today() + timedelta(days=7)
    else:
        start_date = date.today() + timedelta(days=7)

    # Tag each attraction with priority based on rating/popularity
    for a in attractions:
        if "_priority" not in a:
            rating = float(a.get("rating") or 0)
            popular = bool(a.get("popularity_hint"))
            if rating >= 4.5 or popular:
                a["_priority"] = 1  # must-see
            elif rating >= 4.0:
                a["_priority"] = 2  # must-see
            else:
                a["_priority"] = 3  # nice-to-have

    # If priority_weight is low, demote all must-sees to nice-to-haves
    if priority_weight < 0.5:
        for a in attractions:
            if a["_priority"] <= 2:
                a["_priority"] = 3

    # 1. Cluster
    day_buckets = cluster_attractions(attractions, duration_days)

    # 2. Optimize route per day
    day_buckets = [optimize_route(bucket) for bucket in day_buckets]

    # 3. Cross-day balance
    day_buckets = _rebalance_days(day_buckets)

    # Build forecast lookup by date string
    forecast_by_date: dict[str, dict[str, Any]] = {}
    for f in weather_forecast:
        forecast_by_date[str(f.get("date", ""))] = f

    daily_budget = budget_usd / duration_days
    backtrack_log: list[str] = []
    days: list[DayPlan] = []
    total_cost = 0.0

    for day_num in range(1, duration_days + 1):
        day_date = start_date + timedelta(days=day_num - 1)
        forecast = forecast_by_date.get(day_date.isoformat())
        bucket = day_buckets[day_num - 1] if day_num - 1 < len(day_buckets) else []

        activities, cost_used = _schedule_day(
            bucket,
            daily_budget,
            forecast,
            priority_weight,
            backtrack_log,
            f"Day {day_num}",
        )

        total_cost += cost_used

        day_plan = DayPlan(
            date=day_date,
            day_number=day_num,
            activities=activities,
            daily_budget_usd=cost_used,
            weather_forecast=forecast.get("condition") if forecast else None,
        )
        days.append(day_plan)

    if backtrack_log:
        logger.info("Backtrack events:\n%s", "\n".join(backtrack_log))

    elapsed = time.perf_counter() - t0
    logger.info(
        "build_itinerary completed in %.3fs for %d-day trip to %s",
        elapsed,
        duration_days,
        destination,
    )

    return Itinerary(
        id=str(uuid.uuid4()),
        title=f"{duration_days}-Day Trip to {destination}",
        destination=destination,
        start_date=start_date,
        end_date=start_date + timedelta(days=duration_days - 1),
        num_travelers=num_travelers,
        days=days,
        total_cost_usd=round(total_cost, 2),
        budget_usd=budget_usd,
        generated_at=datetime.utcnow().isoformat(),
    )
