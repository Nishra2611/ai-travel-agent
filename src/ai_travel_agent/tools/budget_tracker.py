import json
import logging
from typing import Any, Literal

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

        raw = redis.get(ledger_key)
        ledger_data: list[dict[str, Any]] = json.loads(raw) if raw else []

        if action == "reset":
            redis.delete(ledger_key)
            redis.delete(total_key)
            return {"status": "reset", "trip_id": trip_id}

        if action == "set_budget":
            if total_budget is None:
                raise ValueError("total_budget is required")

            redis.set(total_key, str(total_budget))
            return {"status": "budget_set", "trip_id": trip_id}

        if action == "add_expense":
            if not category or amount is None:
                raise ValueError("category and amount required")

            entry = {
                "category": category,
                "amount": float(amount),
                "description": description or "",
            }

            ledger_data.append(entry)
            redis.set(ledger_key, json.dumps(ledger_data))

            return {"status": "expense_added", "entry": entry}

        if action == "get_summary":
            by_category: dict[str, float] = {}

            for e in ledger_data:
                by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount"]

            spent = sum(by_category.values())
            total = redis.get(total_key)

            total_val = float(total) if total else None

            return {
                "spent_total": spent,
                "by_category": by_category,
                "remaining": (total_val - spent) if total_val else None,
            }

        raise ValueError("Invalid action")

    async def _arun(self, **kwargs: Any) -> dict[str, Any]:
        return self._run(**kwargs)