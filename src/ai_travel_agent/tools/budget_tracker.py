# Target: src/ai_travel_agent/tools/budget_tracker.py

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


class BudgetTrackerInput(BaseModel):
    trip_id: str = Field(..., description="Unique ID for this trip's ledger, e.g. 'paris-dec-2025'")
    action: Literal["set_budget", "add_expense", "get_summary", "reset"]
    total_budget: Optional[float] = Field(None, description="Required for set_budget")
    category: Optional[str] = Field(
        None,
        description="Expense category: accommodation, food, attractions, transport, shopping, misc"
    )
    amount: Optional[float] = Field(None, description="Expense amount in the trip's currency")
    description: Optional[str] = Field(None, description="Short label for the expense")


class BudgetTrackerTool(BaseTool):
    name: str = "budget_tracker"
    description: str = (
        "Manages a trip's running budget ledger stored in Redis. "
        "Actions:\n"
        "  set_budget  — set the total trip budget (total_budget required)\n"
        "  add_expense — log a spend (category + amount required, description optional)\n"
        "  get_summary — returns spent_total, by_category breakdown, total_budget, remaining\n"
        "  reset       — clears all expenses and the budget for this trip_id\n"
        "Each trip_id is a separate ledger — use a consistent ID per trip."
    )
    args_schema: type[BaseModel] = BudgetTrackerInput

    def _run(
        self,
        trip_id: str,
        action: str,
        total_budget: Optional[float] = None,
        category: Optional[str] = None,
        amount: Optional[float] = None,
        description: Optional[str] = None,
    ) -> dict:
        # Late import keeps the module importable even when Redis is not yet
        # configured — the tool only connects at call time.
        from ai_travel_agent.utils.cache import get_redis_client
        redis = get_redis_client()

        ledger_key = f"budget:ledger:{trip_id}"
        total_key = f"budget:total:{trip_id}"

        if action == "reset":
            redis.delete(ledger_key)
            redis.delete(total_key)
            logger.info("Budget reset for trip_id=%s", trip_id)
            return {"status": "reset", "trip_id": trip_id}

        if action == "set_budget":
            if total_budget is None:
                raise ValueError("total_budget is required for set_budget")
            redis.set(total_key, str(total_budget))
            return {"status": "budget_set", "trip_id": trip_id, "total_budget": total_budget}

        if action == "add_expense":
            if not category:
                raise ValueError("category is required for add_expense")
            if amount is None:
                raise ValueError("amount is required for add_expense")

            raw = redis.get(ledger_key)
            ledger: list = json.loads(raw) if raw else []
            entry = {
                "category": category.lower().strip(),
                "amount": round(float(amount), 2),
                "description": (description or "").strip(),
            }
            ledger.append(entry)
            redis.set(ledger_key, json.dumps(ledger))
            return {"status": "expense_added", "entry": entry, "total_entries": len(ledger)}

        if action == "get_summary":
            raw = redis.get(ledger_key)
            ledger: list = json.loads(raw) if raw else []

            by_category: dict[str, float] = {}
            for e in ledger:
                cat = e["category"]
                by_category[cat] = round(by_category.get(cat, 0) + e["amount"], 2)

            spent = round(sum(by_category.values()), 2)

            total_raw = redis.get(total_key)
            total = float(total_raw) if total_raw is not None else None

            return {
                "trip_id": trip_id,
                "spent_total": spent,
                "by_category": by_category,
                "total_budget": total,
                "remaining": round(total - spent, 2) if total is not None else None,
                "entry_count": len(ledger),
            }

        raise ValueError(f"Unknown action: {action!r}. Must be one of: set_budget, add_expense, get_summary, reset")

    async def _arun(
        self,
        trip_id: str,
        action: str,
        total_budget: Optional[float] = None,
        category: Optional[str] = None,
        amount: Optional[float] = None,
        description: Optional[str] = None,
    ) -> dict:
        return self._run(
            trip_id=trip_id,
            action=action,
            total_budget=total_budget,
            category=category,
            amount=amount,
            description=description,
        )