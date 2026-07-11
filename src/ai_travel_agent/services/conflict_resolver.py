"""
Week 6 — ConflictResolver + LangGraph human-in-the-loop node.

Strategy per conflict type:
  TIME_OVERLAP / IMPOSSIBLE_TRAVEL -> shift the later activity forward
  OPENING_HOURS                    -> clamp start/end to open/close window
  MEAL_GAP                         -> insert a placeholder meal slot
  BUDGET_OVERRUN (day-level)       -> drop lowest-priority, highest-cost act
  TOO_MANY_ACTIVITIES / trip-level BUDGET_OVERRUN -> NEEDS_USER (ask via LLM)
"""
import logging
from datetime import datetime, time, timedelta
from typing import Any

from ai_travel_agent.models.itinerary import (
    DayPlan,
    Environment,
    Itinerary,
    ItineraryActivity,
    TimeSlot,
)
from ai_travel_agent.services.conflict_detector import Conflict, ConflictType, Severity
from ai_travel_agent.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ConflictResolver:
    def __init__(self, llm: OllamaClient | None = None) -> None:
        self.llm = llm or OllamaClient()
        self.resolution_log: list[dict[str, Any]] = []

    def resolve_all(
        self, itinerary: Itinerary, conflicts: list[Conflict],
    ) -> tuple[Itinerary, list[dict[str, Any]]]:
        """Returns (modified itinerary, list of NEEDS_USER items)."""
        needs_user: list[dict[str, Any]] = []
        for c in conflicts:
            if c.severity == Severity.NEEDS_USER:
                needs_user.append(self._build_user_question(itinerary, c))
                continue
            day = next((d for d in itinerary.days if d.day_number == c.day_number), None)
            handler = self._HANDLERS.get(c.conflict_type)
            if day and handler:
                handler(self, day, c, itinerary)
        return itinerary, needs_user

    # ── auto-fix handlers ──

    def _fix_time_overlap(self, day: DayPlan, c: Conflict, itin: Itinerary) -> None:
        by_id = {a.attraction_id: a for a in day.activities}
        a, b = by_id.get(c.activity_ids[0]), by_id.get(c.activity_ids[1])
        if not (a and b) or b.locked:
            return
        dur = self._duration(b)
        b.start_time = a.end_time
        b.end_time = self._add(a.end_time or time(0), dur)
        self._log(day.day_number, c.conflict_type, f"Shifted '{b.title}' to {b.start_time}")

    def _fix_impossible_travel(self, day: DayPlan, c: Conflict, itin: Itinerary) -> None:
        by_id = {a.attraction_id: a for a in day.activities}
        a, b = by_id.get(c.activity_ids[0]), by_id.get(c.activity_ids[1])
        if not (a and b) or b.locked:
            return
        needed = int(c.detail["needed_min"])
        dur = self._duration(b)
        new_start = self._add(a.end_time or time(0), needed)
        b.start_time = new_start
        b.end_time = self._add(new_start, dur)
        self._log(day.day_number, c.conflict_type, f"Pushed '{b.title}' to {b.start_time}")

    def _fix_opening_hours(self, day: DayPlan, c: Conflict, itin: Itinerary) -> None:
        act = next((a for a in day.activities if a.attraction_id in c.activity_ids), None)
        if not act:
            return
        dur = self._duration(act)
        if act.open_time and act.start_time and act.start_time < act.open_time:
            act.start_time = act.open_time
            act.end_time = self._add(act.open_time, dur)
        if act.close_time and act.end_time and act.end_time > act.close_time:
            act.end_time = act.close_time
            act.start_time = self._sub(act.close_time, dur)
        self._log(day.day_number, c.conflict_type, f"Clamped '{act.title}' to opening hours")

    def _fix_meal_gap(self, day: DayPlan, c: Conflict, itin: Itinerary) -> None:
        is_lunch = "lunch" in c.message
        slot = time(12, 30) if is_lunch else time(19, 0)
        placeholder = ItineraryActivity(
            time_slot=TimeSlot.AFTERNOON if is_lunch else TimeSlot.EVENING,
            start_time=slot, end_time=self._add(slot, 60),
            attraction_id=f"auto-meal-{day.day_number}-{'lunch' if is_lunch else 'dinner'}",
            title="Lunch (TBD)" if is_lunch else "Dinner (TBD)",
            description="Auto-inserted meal placeholder",
            location_name="Near hotel",
            activity_category="restaurant",
            environment=Environment.INDOOR,
            latitude=day.hotel_latitude, longitude=day.hotel_longitude,
        )
        day.activities.append(placeholder)
        self._log(day.day_number, c.conflict_type, f"Inserted {placeholder.title} at {slot}")

    def _fix_budget_overrun_day(self, day: DayPlan, c: Conflict, itin: Itinerary) -> None:
        candidates = [a for a in day.activities
                      if not a.locked and a.activity_category == "attraction"]
        if not candidates:
            return
        drop = sorted(candidates, key=lambda a: (-a.priority, -a.estimated_cost_usd))[0]
        day.activities.remove(drop)
        self._log(day.day_number, c.conflict_type,
                  f"Dropped '{drop.title}' (${drop.estimated_cost_usd:.0f})")

    _HANDLERS = {
        ConflictType.TIME_OVERLAP: _fix_time_overlap,
        ConflictType.IMPOSSIBLE_TRAVEL: _fix_impossible_travel,
        ConflictType.OPENING_HOURS: _fix_opening_hours,
        ConflictType.MEAL_GAP: _fix_meal_gap,
        ConflictType.BUDGET_OVERRUN: _fix_budget_overrun_day,
    }

    # ── human-in-the-loop ──

    def _build_user_question(self, itin: Itinerary, c: Conflict) -> dict[str, Any]:
        prompt = (
            f"A travel itinerary has an unresolved conflict.\n"
            f"Type: {c.conflict_type.value}\nDetails: {c.message}\n"
            f"Write ONE short question (max 2 sentences) asking the traveler "
            f"how to resolve it, with 2 concrete options."
        )
        question = self.llm.generate(prompt, system="You are a helpful travel planner.")
        return {"conflict": c, "question": question}

    # ── helpers ──

    def _duration(self, a: ItineraryActivity) -> int:
        if not (a.start_time and a.end_time):
            return 60
        return int((datetime.combine(datetime.today(), a.end_time)
                     - datetime.combine(datetime.today(), a.start_time)).total_seconds() / 60)

    @staticmethod
    def _add(t: time, minutes: int) -> time:
        return (datetime.combine(datetime.today(), t) + timedelta(minutes=minutes)).time()

    @staticmethod
    def _sub(t: time, minutes: int) -> time:
        return (datetime.combine(datetime.today(), t) - timedelta(minutes=minutes)).time()

    def _log(self, day: int, ctype: ConflictType, msg: str) -> None:
        self.resolution_log.append({"day": day, "type": ctype.value, "resolution": msg})
        logger.info("[day %d] %s: %s", day, ctype.value, msg)


# ── LangGraph nodes ──

def human_in_the_loop_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node: sets awaiting_user_input flag for interrupt."""
    if state.get("needs_user"):
        state["awaiting_user_input"] = True
        state["pending_questions"] = [q["question"] for q in state["needs_user"]]
    else:
        state["awaiting_user_input"] = False
    return state


def route_after_conflict_check(state: dict[str, Any]) -> str:
    """Conditional edge for the StateGraph."""
    return "ask_user" if state.get("awaiting_user_input") else "continue_planning"
