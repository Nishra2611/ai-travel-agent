# Target: tests/unit/test_budget_tracker.py

from unittest.mock import patch

import fakeredis
import pytest

from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool

TRIP_ID = "test-trip-london"


@pytest.fixture
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


@pytest.fixture
def tool():
    return BudgetTrackerTool()


def _patched(fake_redis):
    """Patch the get_redis_client used inside budget_tracker._run."""
    return patch(
        "ai_travel_agent.utils.cache.get_redis_client", return_value=fake_redis
    )


def test_set_budget(tool, fake_redis):
    with _patched(fake_redis):
        result = tool._run(trip_id=TRIP_ID, action="set_budget", total_budget=1500.0)
    assert result["status"] == "budget_set"
    assert result["total_budget"] == 1500.0


def test_set_budget_requires_total_budget(tool, fake_redis):
    with _patched(fake_redis):
        with pytest.raises(ValueError):
            tool._run(trip_id=TRIP_ID, action="set_budget")


def test_add_expense(tool, fake_redis):
    with _patched(fake_redis):
        result = tool._run(
            trip_id=TRIP_ID,
            action="add_expense",
            category="food",
            amount=35.0,
            description="Dinner at Padella",
        )
    assert result["status"] == "expense_added"
    assert result["entry"]["category"] == "food"
    assert result["entry"]["amount"] == 35.0


def test_add_expense_requires_category_and_amount(tool, fake_redis):
    with _patched(fake_redis):
        with pytest.raises(ValueError):
            tool._run(trip_id=TRIP_ID, action="add_expense", amount=10.0)
        with pytest.raises(ValueError):
            tool._run(trip_id=TRIP_ID, action="add_expense", category="food")


def test_get_summary_totals_and_breakdown(tool, fake_redis):
    with _patched(fake_redis):
        tool._run(trip_id=TRIP_ID, action="set_budget", total_budget=1500.0)
        tool._run(
            trip_id=TRIP_ID,
            action="add_expense",
            category="accommodation",
            amount=600.0,
        )
        tool._run(trip_id=TRIP_ID, action="add_expense", category="food", amount=35.0)
        tool._run(trip_id=TRIP_ID, action="add_expense", category="food", amount=38.0)
        tool._run(
            trip_id=TRIP_ID, action="add_expense", category="attractions", amount=29.0
        )

        summary = tool._run(trip_id=TRIP_ID, action="get_summary")

    assert summary["spent_total"] == 702.0
    assert summary["by_category"] == {
        "accommodation": 600.0,
        "food": 73.0,
        "attractions": 29.0,
    }
    assert summary["total_budget"] == 1500.0
    assert summary["remaining"] == 798.0
    assert summary["entry_count"] == 4


def test_get_summary_with_no_expenses(tool, fake_redis):
    with _patched(fake_redis):
        summary = tool._run(trip_id="empty-trip", action="get_summary")
    assert summary["spent_total"] == 0
    assert summary["by_category"] == {}
    assert summary["total_budget"] is None
    assert summary["remaining"] is None


def test_reset_clears_ledger_and_budget(tool, fake_redis):
    with _patched(fake_redis):
        tool._run(trip_id=TRIP_ID, action="set_budget", total_budget=1000.0)
        tool._run(trip_id=TRIP_ID, action="add_expense", category="food", amount=20.0)
        tool._run(trip_id=TRIP_ID, action="reset")
        summary = tool._run(trip_id=TRIP_ID, action="get_summary")

    assert summary["spent_total"] == 0
    assert summary["total_budget"] is None


def test_unknown_action_raises(tool, fake_redis):
    with _patched(fake_redis):
        with pytest.raises(ValueError):
            tool._run(trip_id=TRIP_ID, action="not_a_real_action")


def test_trip_ids_are_isolated(tool, fake_redis):
    with _patched(fake_redis):
        tool._run(trip_id="trip-a", action="set_budget", total_budget=500.0)
        tool._run(trip_id="trip-a", action="add_expense", category="food", amount=20.0)
        tool._run(trip_id="trip-b", action="set_budget", total_budget=2000.0)

        summary_a = tool._run(trip_id="trip-a", action="get_summary")
        summary_b = tool._run(trip_id="trip-b", action="get_summary")

    assert summary_a["total_budget"] == 500.0
    assert summary_a["spent_total"] == 20.0
    assert summary_b["total_budget"] == 2000.0
    assert summary_b["spent_total"] == 0
