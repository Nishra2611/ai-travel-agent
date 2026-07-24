"""
scripts/demo_agent_w13.py — Week 13

Runs the full compiled graph end to end and prints state["map_output"].
Same shape as demo_agent_w10.py / demo_agent_w9.py.

Run: poetry run python scripts/demo_agent_w13.py
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

    print("=== map_output ===")
    print(json.dumps(final_state.get("map_output"), indent=2))

    if final_state.get("error"):
        print(f"\n!! error: {final_state['error']}")


if __name__ == "__main__":
    main()
