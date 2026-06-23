"""
scripts/demo_agent.py — end-to-end smoke test, no HTTP.
Run: poetry run python scripts/demo_agent.py
"""

from __future__ import annotations

import time

from dotenv import load_dotenv

from ai_travel_agent.agents.graph import build_graph

load_dotenv()

TEST_INPUTS = [
    "I want to visit Paris for 5 days in July under $3000",
    "Plan a 7-day trip to Tokyo for 2 people, love food and culture",
    "Weekend trip to Goa, budget Rs 50000, adventure activities",
]


def run(message: str, session_id: str) -> None:
    print(f"\n{'='*58}\nInput: {message}\n{'='*58}")
    graph = build_graph(db_path="data/smoke_test.db")
    t0 = time.perf_counter()
    state = graph.invoke(
        {
            "raw_input": message,
            "status": "parse",
            "messages": [{"role": "user", "content": message}],
        },
        config={"configurable": {"thread_id": session_id}},
    )
    elapsed = time.perf_counter() - t0
    out = state.get("final_output") or {}
    print(f"Time        : {elapsed:.1f}s")
    print(f"Status      : {state.get('status')}")
    print(f"Destination : {out.get('destination', '?')}")
    print(f"Flights     : {len(out.get('flights', []))}")
    print(f"Hotels      : {len(out.get('hotels', []))}")
    print(f"Attractions : {len(out.get('attractions', []))}")
    print(f"Restaurants : {len(out.get('restaurants', []))}")
    print(f"Weather days: {len(out.get('weather', []))}")
    print(f"Errors      : {out.get('errors', {})}")
    msgs = [m for m in (state.get("messages") or []) if m.get("role") == "assistant"]
    for m in msgs:
        print(f"Agent       : {m['content']}")


if __name__ == "__main__":
    for i, msg in enumerate(TEST_INPUTS, 1):
        run(msg, f"smoke-{i}")
    print("\n✓ All smoke tests complete\n")
