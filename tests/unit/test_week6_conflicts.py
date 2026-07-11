"""
tests/unit/test_week6_conflicts.py

15 edge-case tests for ConflictDetector + ConflictResolver.
Uses real project models (ItineraryActivity, DayPlan, Itinerary).
No network calls — travel_time_fn is a simple 15-min stub.
"""
import unittest
from datetime import date, time

from ai_travel_agent.models.itinerary import (
    Environment, Itinerary, ItineraryActivity, DayPlan, TimeSlot,
)
from ai_travel_agent.services.conflict_detector import (
    ConflictDetector, ConflictType, Severity,
)
from ai_travel_agent.services.conflict_resolver import ConflictResolver


# ── helpers ──────────────────────────────────────────────────────────────────

def flat_travel(_from, _to) -> int:
    """Fake travel-time: always 15 min."""
    return 15


def make_act(
    id_: str, title: str,
    start: time, end: time,
    category: str = "attraction",
    cost: float = 0.0,
    priority: int = 3,
    env: Environment = Environment.MIXED,
    open_t: time | None = None,
    close_t: time | None = None,
    locked: bool = False,
) -> ItineraryActivity:
    return ItineraryActivity(
        time_slot=TimeSlot.MORNING,
        attraction_id=id_,
        title=title,
        description="",
        location_name="Test",
        start_time=start, end_time=end,
        activity_category=category,
        estimated_cost_usd=cost,
        priority=priority,
        environment=env,
        open_time=open_t, close_time=close_t,
        locked=locked,
        latitude=1.0, longitude=1.0,
    )


def make_day(number: int, acts: list, budget: float = 500.0) -> DayPlan:
    return DayPlan(
        date=date(2026, 8, number),
        day_number=number,
        activities=acts,
        daily_budget_usd=budget,
        hotel_latitude=1.0, hotel_longitude=1.0,
    )


def make_itin(days: list[DayPlan], total_budget: float = 5000.0) -> Itinerary:
    return Itinerary(
        id="t1", title="Test Trip", destination="Paris",
        start_date=date(2026, 8, 1), end_date=date(2026, 8, 7),
        num_travelers=2, days=days, budget_usd=total_budget,
    )


# ── test cases ────────────────────────────────────────────────────────────────

class TestConflictDetection(unittest.TestCase):

    def setUp(self):
        self.detector = ConflictDetector(travel_time_fn=flat_travel)

    # 1 — time overlap detected
    def test_overlapping_activities_detected(self):
        acts = [make_act("a1", "Museum", time(9), time(11)),
                make_act("a2", "Park",   time(10), time(12))]
        conflicts = self.detector._time_overlaps(make_day(1, acts))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.TIME_OVERLAP)

    # 2 — no overlap → no conflict
    def test_no_overlap_no_conflict(self):
        acts = [make_act("a1", "Museum", time(9),  time(11)),
                make_act("a2", "Park",   time(11, 30), time(12, 30))]
        self.assertEqual(self.detector._time_overlaps(make_day(1, acts)), [])

    # 3 — impossible travel (5 min gap, need 15+10=25)
    def test_impossible_travel_detected(self):
        acts = [make_act("a1", "Museum", time(9),  time(10)),
                make_act("a2", "Park",   time(10, 5), time(11))]
        conflicts = self.detector._impossible_travel(make_day(1, acts))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.IMPOSSIBLE_TRAVEL)

    # 4 — sufficient gap → OK
    def test_sufficient_travel_gap_ok(self):
        acts = [make_act("a1", "Museum", time(9),  time(10)),
                make_act("a2", "Park",   time(10, 30), time(11))]
        self.assertEqual(self.detector._impossible_travel(make_day(1, acts)), [])

    # 5 — activity starts before venue opens
    def test_opening_hours_too_early(self):
        acts = [make_act("a1", "Museum", time(7), time(9),
                         open_t=time(9), close_t=time(18))]
        self.assertEqual(len(self.detector._opening_hours(make_day(1, acts))), 1)

    # 6 — activity ends after venue closes
    def test_opening_hours_too_late(self):
        acts = [make_act("a1", "Museum", time(17), time(19),
                         open_t=time(9), close_t=time(18))]
        self.assertEqual(len(self.detector._opening_hours(make_day(1, acts))), 1)

    # 7 — within opening hours → OK
    def test_opening_hours_within_bounds_ok(self):
        acts = [make_act("a1", "Museum", time(10), time(12),
                         open_t=time(9), close_t=time(18))]
        self.assertEqual(self.detector._opening_hours(make_day(1, acts)), [])

    # 8 — 6 activities exceeds max 5 → NEEDS_USER
    def test_too_many_activities_detected(self):
        acts = [make_act(f"a{i}", f"Stop{i}", time(9 + i), time(9 + i, 45))
                for i in range(6)]
        conflicts = self.detector._too_many_activities(make_day(1, acts))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, Severity.NEEDS_USER)

    # 9 — 3 activities within limit → OK
    def test_within_activity_limit_ok(self):
        acts = [make_act(f"a{i}", f"Stop{i}", time(9 + i), time(9 + i, 45))
                for i in range(3)]
        self.assertEqual(self.detector._too_many_activities(make_day(1, acts)), [])

    # 10 — no lunch in window
    def test_missing_lunch_detected(self):
        acts = [make_act("a1", "Museum", time(9), time(11))]
        conflicts = self.detector._meal_gaps(make_day(1, acts))
        self.assertTrue(any("lunch" in c.message for c in conflicts))

    # 11 — no dinner in window
    def test_missing_dinner_detected(self):
        acts = [make_act("l1", "Cafe", time(12, 30), time(13, 30), category="restaurant")]
        conflicts = self.detector._meal_gaps(make_day(1, acts))
        self.assertTrue(any("dinner" in c.message for c in conflicts))

    # 12 — both meals present → no gap
    def test_both_meals_present_no_gap(self):
        acts = [
            make_act("l1", "Cafe",   time(12, 30), time(13, 30), category="restaurant"),
            make_act("d1", "Bistro", time(19),     time(20, 30), category="restaurant"),
        ]
        self.assertEqual(self.detector._meal_gaps(make_day(1, acts)), [])

    # 13 — day budget overrun → AUTO_FIXABLE
    def test_day_budget_overrun(self):
        acts = [make_act("a1", "Tour", time(9), time(12), cost=600.0)]
        itin = make_itin([make_day(1, acts, budget=500.0)])
        conflicts = self.detector._budget_overrun(itin)
        self.assertTrue(any(c.day_number == 1 for c in conflicts))

    # 14 — trip-level budget overrun → NEEDS_USER
    def test_trip_budget_overrun_needs_user(self):
        acts = [make_act("a1", "Tour", time(9), time(12), cost=100.0)]
        itin = make_itin([make_day(1, acts, budget=500.0)], total_budget=50.0)
        conflicts = self.detector._budget_overrun(itin)
        self.assertTrue(any(c.severity == Severity.NEEDS_USER for c in conflicts))

    # 15 — end-to-end: resolver shifts Park to start at Museum end
    def test_resolver_fixes_overlap_end_to_end(self):
        acts = [make_act("a1", "Museum", time(9),  time(11)),
                make_act("a2", "Park",   time(10), time(12))]
        itin = make_itin([make_day(1, acts)])
        conflicts = self.detector.detect_all(itin)

        class _NoLLM:
            def generate(self, *a, **kw): return "Fix it."
            def generate_json(self, *a, **kw): return {}

        resolver = ConflictResolver(llm=_NoLLM())  # type: ignore[arg-type]
        fixed_itin, _ = resolver.resolve_all(itin, conflicts)
        park = next(a for d in fixed_itin.days for a in d.activities if a.attraction_id == "a2")
        self.assertGreaterEqual(park.start_time, time(11))


if __name__ == "__main__":
    unittest.main(verbosity=2)
