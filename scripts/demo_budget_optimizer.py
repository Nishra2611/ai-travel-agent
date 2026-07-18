"""
scripts/demo_budget_optimizer.py — Week 8

Exercises _BudgetOptimizer directly, no graph/LangChain/FastAPI involved --
same spirit as demo_itinerary_builder.py from Week 5/6. Proves the
allocation/tradeoff/adherence logic works before it ever touches a node.

Run: poetry run python scripts/demo_budget_optimizer.py
"""

from __future__ import annotations

from ai_travel_agent.budget.budget_optimizer import (
    BudgetProfile,
    _BudgetOptimizer,
)


def main() -> None:
    optimizer = _BudgetOptimizer()

    # 1. Baseline mid-range allocation
    baseline = optimizer.allocate(total_budget=3000.0, profile=BudgetProfile.MID_RANGE)
    print("1) Baseline mid-range allocation ($3000)")
    for a in baseline.allocations:
        print(
            f"    {a.category.value:<15} ${a.allocated_amount:>8.2f}  ({a.percentage*100:5.1f}%)"
        )

    # 2. Same budget with a preference signal
    text = "I prioritize accommodation over dining"
    weighted = optimizer.allocate(
        total_budget=3000.0, profile=BudgetProfile.MID_RANGE, preference_text=text
    )
    print(f"\n2) Re-allocated with preference: '{text}'")
    for a in weighted.allocations:
        print(
            f"    {a.category.value:<15} ${a.allocated_amount:>8.2f}  ({a.percentage*100:5.1f}%)"
        )

    # 3. Simulate under-budget actual spend -> expect upgrade suggestions
    under_spend = {a.category: a.allocated_amount * 0.6 for a in baseline.allocations}
    under_report = optimizer.suggest_tradeoffs(baseline, under_spend)
    print(
        f"\n3) Under-budget tradeoff (status={under_report.status}, surplus=${under_report.surplus_or_deficit:.2f})"
    )
    for s in under_report.suggestions:
        print(
            f"    {s.action.upper():<8} {s.category.value:<15} ${s.current_amount:.2f} -> ${s.suggested_amount:.2f}"
        )

    # 4. Simulate over-budget actual spend -> expect cut suggestions
    over_spend = {a.category: a.allocated_amount * 1.4 for a in baseline.allocations}
    over_report = optimizer.suggest_tradeoffs(baseline, over_spend)
    print(
        f"\n4) Over-budget tradeoff (status={over_report.status}, deficit=${-over_report.surplus_or_deficit:.2f})"
    )
    for s in over_report.suggestions:
        print(
            f"    {s.action.upper():<8} {s.category.value:<15} ${s.current_amount:.2f} -> ${s.suggested_amount:.2f}"
        )

    # 5. Adherence score for the over-budget case
    score = optimizer.adherence_score(baseline, over_spend)
    print(
        f"\n5) Adherence score: overall={score.overall_score}  verdict={score.verdict}  variance={score.variance_pct}%"
    )
    for cat, s in score.category_scores.items():
        print(f"    {cat.value:<15} {s}")


if __name__ == "__main__":
    main()
