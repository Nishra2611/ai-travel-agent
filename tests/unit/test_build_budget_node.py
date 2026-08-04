"""
tests/unit/test_budget_optimizer.py — Week 8

Unit tests _BudgetOptimizer directly (no graph, no mocking) -- same pattern
as test_itinerary_builder.py. 20 scenarios covering:
  - allocation sum/floor invariants across 3 profiles x 3 budget sizes (9)
  - preference weighting shifts share in the expected direction (5)
  - adherence score correctness across perfect/over/under spend (3)
  - tradeoff engine end to end: upgrade/cut/on-budget (3)

These numbers were verified by actually running the water-filling floor
logic standalone before committing to it -- see the module docstring in
budget_optimizer.py for the "why deterministic, not LLM" reasoning.
"""

from __future__ import annotations

import pytest

from ai_travel_agent.budget.budget_optimizer import (
    MIN_CATEGORY_FLOOR_PCT,
    BudgetCategory,
    BudgetProfile,
    _BudgetOptimizer,
)


@pytest.fixture
def optimizer() -> _BudgetOptimizer:
    return _BudgetOptimizer()


# ---------------------------------------------------------------------------
# 1-9: allocation sum + floor invariants, 3 profiles x 3 budget sizes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "profile", [BudgetProfile.BACKPACKER, BudgetProfile.MID_RANGE, BudgetProfile.LUXURY]
)
@pytest.mark.parametrize("total_budget", [800.0, 2500.0, 8000.0])
def test_allocation_respects_total_and_floors(optimizer, profile, total_budget):
    result = optimizer.allocate(total_budget=total_budget, profile=profile)

    allocated_sum = sum(a.allocated_amount for a in result.allocations)
    assert allocated_sum <= total_budget + 0.01

    for alloc in result.allocations:
        floor = MIN_CATEGORY_FLOOR_PCT.get(alloc.category, 0.0) * total_budget
        assert alloc.allocated_amount >= floor - 0.01


# ---------------------------------------------------------------------------
# 10-14: preference weighting shifts allocation in the expected direction
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,boosted,reduced",
    [
        (
            "I prioritize accommodation over dining",
            BudgetCategory.ACCOMMODATION,
            BudgetCategory.FOOD,
        ),
        (
            "I prioritize activities over flights",
            BudgetCategory.ACTIVITIES,
            BudgetCategory.FLIGHTS,
        ),
        (
            "food matters more than transport",
            BudgetCategory.FOOD,
            BudgetCategory.TRANSPORT,
        ),
        (
            "flights matter more than shopping",
            BudgetCategory.FLIGHTS,
            BudgetCategory.MISC,
        ),
        (
            "I prioritize accommodation over activities",
            BudgetCategory.ACCOMMODATION,
            BudgetCategory.ACTIVITIES,
        ),
    ],
)
def test_preference_weighting_shifts_allocation(optimizer, text, boosted, reduced):
    baseline = optimizer.allocate(total_budget=3000.0, profile=BudgetProfile.MID_RANGE)
    weighted = optimizer.allocate(
        total_budget=3000.0, profile=BudgetProfile.MID_RANGE, preference_text=text
    )

    assert weighted.get(boosted).percentage > baseline.get(boosted).percentage
    assert weighted.get(reduced).percentage <= baseline.get(reduced).percentage + 1e-6


# ---------------------------------------------------------------------------
# 15-17: adherence score correctness
# ---------------------------------------------------------------------------
def test_adherence_score_perfect_match(optimizer):
    allocation = optimizer.allocate(
        total_budget=2000.0, profile=BudgetProfile.MID_RANGE
    )
    actual_spend = {a.category: a.allocated_amount for a in allocation.allocations}

    score = optimizer.adherence_score(allocation, actual_spend)
    assert score.overall_score >= 99.0
    assert score.verdict == "excellent_adherence"


def test_adherence_score_penalizes_overspend_more_than_underspend(optimizer):
    allocation = optimizer.allocate(
        total_budget=2000.0, profile=BudgetProfile.MID_RANGE
    )
    over_spend = {a.category: a.allocated_amount * 1.3 for a in allocation.allocations}
    under_spend = {a.category: a.allocated_amount * 0.7 for a in allocation.allocations}

    over_score = optimizer.adherence_score(allocation, over_spend)
    under_score = optimizer.adherence_score(allocation, under_spend)
    assert over_score.overall_score < under_score.overall_score


def test_adherence_score_flags_severe_overspend(optimizer):
    allocation = optimizer.allocate(
        total_budget=1000.0, profile=BudgetProfile.BACKPACKER
    )
    blown_spend = {a.category: a.allocated_amount * 2.5 for a in allocation.allocations}

    score = optimizer.adherence_score(allocation, blown_spend)
    assert score.overall_score < 50
    assert score.variance_pct > 0


# ---------------------------------------------------------------------------
# 18-20: tradeoff engine end to end
# ---------------------------------------------------------------------------
def test_tradeoff_suggests_upgrades_when_under_budget(optimizer):
    allocation = optimizer.allocate(
        total_budget=4000.0, profile=BudgetProfile.MID_RANGE
    )
    under_spend = {a.category: a.allocated_amount * 0.6 for a in allocation.allocations}

    report = optimizer.suggest_tradeoffs(allocation, under_spend)
    assert report.status == "under_budget"
    assert len(report.suggestions) > 0
    assert all(s.action == "upgrade" for s in report.suggestions)


def test_tradeoff_suggests_cuts_when_over_budget(optimizer):
    allocation = optimizer.allocate(total_budget=1500.0, profile=BudgetProfile.LUXURY)
    over_spend = {a.category: a.allocated_amount * 1.5 for a in allocation.allocations}

    report = optimizer.suggest_tradeoffs(allocation, over_spend)
    assert report.status == "over_budget"
    assert len(report.suggestions) > 0
    assert all(s.action == "cut" for s in report.suggestions)
    for s in report.suggestions:
        floor = allocation.get(s.category).min_required
        assert s.suggested_amount >= floor - 0.01


def test_tradeoff_no_suggestions_when_on_budget(optimizer):
    allocation = optimizer.allocate(
        total_budget=2200.0, profile=BudgetProfile.MID_RANGE
    )
    on_budget_spend = {a.category: a.allocated_amount for a in allocation.allocations}

    report = optimizer.suggest_tradeoffs(allocation, on_budget_spend)
    assert report.status == "on_budget"
    assert report.suggestions == []
