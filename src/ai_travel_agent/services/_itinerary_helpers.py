"""
ai_travel_agent/services/_itinerary_helpers.py

Small shared utilities so conflict_detector.py and weather_scheduler.py
don't duplicate the same "what kind of activity is this" logic.

ItineraryActivity (from models/itinerary.py) does NOT carry an
activity-kind or indoor/outdoor flag — only attraction_id, title,
description, location_name. So we reconstruct that context by keeping
a lookup back to the original attraction dicts (same pattern
ItineraryBuilder already uses in `_resolve_location`).
"""
from __future__ import annotations

from typing import Any

from ai_travel_agent.models.attraction import AttractionCategory
from ai_travel_agent.models.itinerary import ItineraryActivity

# Tune this if your attraction categories don't map cleanly.
# LANDMARK is treated as OUTDOOR since most (plazas, monuments, viewpoints)
# are exterior visits — flip individual ones via the attraction dict if needed.
CATEGORY_ENVIRONMENT: dict[str, str] = {
    AttractionCategory.PARK: "outdoor",
    AttractionCategory.TOUR: "outdoor",
    AttractionCategory.LANDMARK: "outdoor",
    AttractionCategory.MUSEUM: "indoor",
    AttractionCategory.SHOPPING: "indoor",
    AttractionCategory.ENTERTAINMENT: "indoor",
    AttractionCategory.RESTAURANT: "indoor",
}


def build_attraction_index(attractions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """attraction_id -> original attraction dict, for opening-hours/category lookups."""
    return {a["id"]: a for a in attractions if a.get("id")}


def infer_kind(activity: ItineraryActivity) -> str:
    """
    'attraction' | 'meal' | 'transfer'
    ItineraryActivity has no explicit type field, so we infer it from
    attraction_id + title, matching how ItineraryBuilder itself builds them.
    """
    if activity.attraction_id:
        return "attraction"
    title = (activity.title or "").lower()
    if "dinner" in title or "lunch" in title or "breakfast" in title:
        return "meal"
    return "transfer"  # check-in, check-out, airport transfer, etc.


def environment_for(
    activity: ItineraryActivity,
    attraction_index: dict[str, dict[str, Any]],
) -> str:
    """'indoor' | 'outdoor' | 'mixed'"""
    if activity.attraction_id and activity.attraction_id in attraction_index:
        category = attraction_index[activity.attraction_id].get("category")
        return CATEGORY_ENVIRONMENT.get(category, "mixed")
    return "mixed"


def activity_uid(day_number: int, index: int, activity: ItineraryActivity) -> str:
    """
    Stable synthetic id for conflict reporting — ItineraryActivity has no
    'id' field of its own (attraction_id is only set for attraction-derived
    entries).
    """
    return f"d{day_number}-a{index}"
