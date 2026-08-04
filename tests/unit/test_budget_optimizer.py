from ai_travel_agent.budget.budget_optimizer import (
    BudgetCategory,
    BudgetProfile,
    _BudgetOptimizer,
)


def test_allocate_budget():
    optimizer = _BudgetOptimizer()

    allocation = optimizer.allocate(
        total_budget=3000,
        profile=BudgetProfile.MID_RANGE,
    )

    assert allocation.total_budget == 3000
    assert len(allocation.allocations) > 0


def test_preference_weighting():
    optimizer = _BudgetOptimizer()

    allocation = optimizer.allocate(
        total_budget=3000,
        profile=BudgetProfile.MID_RANGE,
        preference_text="I prioritize accommodation over dining",
    )

    accommodation = allocation.get(BudgetCategory.ACCOMMODATION)
    food = allocation.get(BudgetCategory.FOOD)

    assert accommodation.percentage > food.percentage


def test_tradeoff_detection():
    optimizer = _BudgetOptimizer()

    allocation = optimizer.allocate(
        total_budget=3000,
        profile=BudgetProfile.MID_RANGE,
    )

    actual_spend = {
        BudgetCategory.FLIGHTS: 1500,
        BudgetCategory.ACCOMMODATION: 1500,
        BudgetCategory.FOOD: 800,
        BudgetCategory.ACTIVITIES: 400,
        BudgetCategory.TRANSPORT: 200,
        BudgetCategory.MISC: 100,
    }

    report = optimizer.suggest_tradeoffs(
        allocation,
        actual_spend,
    )

    assert report.status == "over_budget"


def test_adherence_score():
    optimizer = _BudgetOptimizer()

    allocation = optimizer.allocate(
        total_budget=3000,
        profile=BudgetProfile.MID_RANGE,
    )

    actual_spend = {
        BudgetCategory.FLIGHTS: 840,
        BudgetCategory.ACCOMMODATION: 960,
        BudgetCategory.FOOD: 600,
        BudgetCategory.ACTIVITIES: 360,
        BudgetCategory.TRANSPORT: 150,
        BudgetCategory.MISC: 90,
    }

    score = optimizer.adherence_score(
        allocation,
        actual_spend,
    )

    assert score.overall_score > 80
