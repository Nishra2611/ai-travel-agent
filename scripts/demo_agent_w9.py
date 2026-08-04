"""
scripts/demo_agent_w9.py — Week 9

Runs the full compiled graph end to end and prints state["geo_clusters"],
alongside the Week 8 budget keys to show the whole pipeline together.
Same shape as demo_agent_w8.py / demo_agent_w5.py.

Run: poetry run python scripts/demo_agent_w9.py
"""

from __future__ import annotations

import json
import uuid

from ai_travel_agent.agents.graph import agent


def main() -> None:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "raw_request": "I want to visit Paris for 5 days in July, budget $3000, mid-range",
    }

    print(f"Running agent (thread_id={thread_id}) ...\n")
    final_state = agent.invoke(initial_state, config=config)

    print("=== geo_clusters ===")
    print(json.dumps(final_state.get("geo_clusters"), indent=2))

    print("\n=== budget_allocation (Week 8, for context) ===")
    print(json.dumps(final_state.get("budget_allocation"), indent=2))

    if final_state.get("error"):
        print(f"\n!! error: {final_state['error']}")


if __name__ == "__main__":
    main()
