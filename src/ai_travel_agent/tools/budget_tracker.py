from typing import Any
import json
import logging
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BudgetTrackerInput(BaseModel):
    trip_id: str = Field(..., description="Unique ID for this trip's ledger, e.g. 'paris-dec-2025'")
    action: Literal["set_budget", "add_expense", "get_summary", "reset"]
    total_budget: float | None = Field(None)
    category: str | None = Field(None)
    amount: float | None = Field(None)
    description: str | None = Field(None)


class BudgetTrackerTool(BaseTool):
    name: str = "budget_tracker"
    description: str = "Manages a trip budget ledger stored in Redis"
    args_schema: type[BaseModel] = BudgetTrackerInput

    def _run(
        self,
        trip_id: str,
        action: str,
        total_budget: float | None = None,
        category: str | None = None,
        amount: float | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:

        from ai_travel_agent.utils.cache import get_redis_client

        redis = get_redis_client()

        ledger_key = f"budget:ledger:{trip_id}"
        total_key = f"budget:total:{trip_id}"

        if action == "reset":
            redis.delete(ledger_key)
            redis.delete(total_key)
            return {"status": "reset", "trip_id": trip_id}

        raw = redis.get(ledger_key)
        ledger_data: list[dict[str, Any]] = json.loads(raw) if raw else []

        if action == "set_budget":
            if total_budget is None:
                raise ValueError("total_budget is required for set_budget")

            redis.set(total_key, str(total_budget))
            return {
                "status": "budget_set",
                "trip_id": trip_id,
                "total_budget": total_budget,
            }

        if action == "add_expense":
            if not category:
                raise ValueError("category is required")
            if amount is None:
                raise ValueError("amount is required")

            entry: dict[str, Any] = {
                "category": category.lower().strip(),
                "amount": round(float(amount), 2),
                "description": (description or "").strip(),
            }

            ledger_data.append(entry)
            redis.set(ledger_key, json.dumps(ledger_data))

            return {
                "status": "expense_added",
                "entry": entry,
                "total_entries": len(ledger_data),
            }

        if action == "get_summary":
            by_category: dict[str, float] = {}

            for e in ledger_data:
                cat = e["category"]
                by_category[cat] = round(by_category.get(cat, 0) + e["amount"], 2)

            spent = round(sum(by_category.values()), 2)

            total_raw = redis.get(total_key)
            total = float(total_raw) if total_raw else None

            return {
                "trip_id": trip_id,
                "spent_total": spent,
                "by_category": by_category,
                "total_budget": total,
                "remaining": round(total - spent, 2) if total else None,
                "entry_count": len(ledger_data),
            }

        raise ValueError("Invalid action")

    async def _arun(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(**kwargs)