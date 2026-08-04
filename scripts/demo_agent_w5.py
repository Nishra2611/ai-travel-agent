"""
scripts/demo_agent_w5.py

Week 5 end-to-end smoke test — runs the full graph including
ItineraryBuilder, prints the day-by-day itinerary to terminal.

Run: poetry run python scripts/demo_agent_w5.py
"""

from __future__ import annotations

import time

from dotenv import load_dotenv

from ai_travel_agent.agents.graph import build_graph

load_dotenv()


TRIPS = [
    ("Paris 5 days under $3000, love culture and food", "smoke-w5-1"),
    ("Bali 7 days beach holiday relaxation, 2 people", "smoke-w5-2"),
    ("Nepal 10 days adventure trekking, budget $1500", "smoke-w5-3"),
]


def print_itinerary(itin: dict) -> None:
    if not itin:
        print("  (no itinerary generated)")
        return
    print(f"  Title   : {itin['title']}")
    print(
        f"  Budget  : ${itin.get('budget_usd', 'N/A')} | "
        f"Cost: ${itin.get('total_cost_usd', 0):.2f} | "
        f"Within: {itin.get('is_within_budget', 'N/A')}"
    )
    print(f"  Hotel   : {itin['hotel']['name'] if itin.get('hotel') else 'none'}")
    print(
        f"  Flight  : " f"${itin['outbound_flight']['total_price_usd']:.0f}"
        if itin.get("outbound_flight")
        else "  Flight  : none"
    )
    print()
    for day in itin.get("days", []):
        print(f"  Day {day['day_number']:2d} — {day['theme']}")
        if day.get("weather_forecast"):
            print(f"    Weather: {day['weather_forecast']}")
        for act in day.get("activities", []):
            slot = act["time_slot"]
            title = act["title"]
            cost = act.get("estimated_cost_usd", 0)
            tt = act.get("travel_time_to_next_minutes")
            tt_str = f" → +{tt}min travel" if tt else ""
            print(f"    [{slot:9s}] {title:<40} ${cost:.0f}{tt_str}")
        print()


graph = build_graph(db_path="data/demo_w5.db")

for msg, sid in TRIPS:
    print(f"\n{'='*62}")
    print(f"Input   : {msg}")
    print(f"Session : {sid}")
    print("=" * 62)

    t0 = time.perf_counter()
    state = graph.invoke(
        {
            "raw_input": msg,
            "status": "parse",
            "messages": [{"role": "user", "content": msg}],
        },
        config={"configurable": {"thread_id": sid}},
    )
    elapsed = time.perf_counter() - t0

    out = state.get("final_output") or {}
    print(f"Status  : {state.get('status')} ({elapsed:.1f}s)")
    print(
        f"Tools   : {out.get('tools_succeeded', 0)}/7 succeeded | "
        f"Errors: {list(out.get('errors', {}).keys())}"
    )
    print()
    print_itinerary(out.get("itinerary") or {})

    for m in state.get("messages", []):
        if m.get("role") == "assistant":
            print(f"Agent   : {m['content']}")

print("\n✓ Week 5 smoke test complete\n")
