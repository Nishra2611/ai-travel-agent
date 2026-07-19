"""
scripts/demo_agent_w10.py — Week 10

Runs the full compiled graph end to end and prints state["route_optimization"]
alongside the reordered itinerary, showing the whole Week 8-10 pipeline
together. Same shape as demo_agent_w9.py / demo_agent_w8.py.

Run: poetry run python scripts/demo_agent_w10.py
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

    print("=== route_optimization ===")
    print(json.dumps(final_state.get("route_optimization"), indent=2))

    print("\n=== itinerary (post-optimization activity order) ===")
    print(json.dumps(final_state.get("itinerary"), indent=2))

    if final_state.get("error"):
        print(f"\n!! error: {final_state['error']}")


if __name__ == "__main__":
    main()
