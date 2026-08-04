"""
scripts/demo_agent_w8.py — Week 8

Runs the full compiled graph (agent from ai_travel_agent.agents.graph)
end to end for a budget-stated request, and prints the two new state keys:
budget_allocation (set before search) and budget_tradeoffs/budget_adherence
(set after build_itinerary). Same shape as demo_agent_w5.py.

Run: poetry run python scripts/demo_agent_w8.py
"""

from __future__ import annotations

import json
import uuid

from ai_travel_agent.agents.graph import agent


def main() -> None:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "raw_input": (
            "I want to visit Paris for 5 days in July, budget $3000, "
            "mid-range, I prioritize accommodation over dining"
        ),
        "status": "parse",
        "messages": [],
    }

    print(f"Running agent (thread_id={thread_id}) ...\n")
    final_state = agent.invoke(initial_state, config=config)

    print("=== budget_allocation ===")
    print(json.dumps(final_state.get("budget_allocation"), indent=2))

    print("\n=== budget_tradeoffs ===")
    print(json.dumps(final_state.get("budget_tradeoffs"), indent=2))

    print("\n=== budget_adherence ===")
    print(json.dumps(final_state.get("budget_adherence"), indent=2))

    if final_state.get("error"):
        print(f"\n!! error: {final_state['error']}")


if __name__ == "__main__":
    main()
