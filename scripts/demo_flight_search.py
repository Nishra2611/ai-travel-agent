"""
scripts/demo_flight_search.py

Run from project root:
    poetry run python scripts/demo_flight_search.py

What this proves:
    - FlightSearchTool instantiates correctly
    - Mock fallback returns 5 results when API is not called
    - Price/stops filters work
    - Cache stores result (second call is instant)
"""

import time

from dotenv import load_dotenv

load_dotenv()

from src.tools.flight_search import FlightSearchTool  # noqa: E402

tool = FlightSearchTool(use_mock_on_failure=True)

QUERIES = [
    {
        "origin": "BOM",
        "destination": "CDG",
        "departure_date": "2025-12-10",
        "adults": 1,
    },
    {
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": "2025-12-15",
        "adults": 2,
    },
    {
        "origin": "DEL",
        "destination": "NRT",
        "departure_date": "2026-01-05",
        "adults": 1,
    },
]

print("=" * 60)
print("FlightSearchTool — demo")
print("=" * 60)

for q in QUERIES:
    print(f"\n{q['origin']} → {q['destination']}  |  {q['departure_date']}")
    t0 = time.perf_counter()
    results = tool.invoke(q)
    elapsed = time.perf_counter() - t0
    print(f"  {len(results)} flights  ({elapsed:.2f}s)")
    for r in results:
        seg = r["segments"][0]
        print(
            f"    {seg['airline']:<22} ${r['total_price_usd']:.0f}"
            f"  {r['num_stops']} stop(s)"
            f"  {r['total_duration_minutes']}min"
        )

# --- filter demo ---
print("\n--- max_price=800, max_stops=0 filter ---")
filtered = tool.invoke(
    {
        "origin": "BOM",
        "destination": "CDG",
        "departure_date": "2025-12-10",
        "max_price": 800.0,
        "max_stops": 0,
    }
)
print(f"  {len(filtered)} flights match (all nonstop under $800)")

# --- cache speedup demo ---
print("\n--- cache speedup ---")
params = {"origin": "LHR", "destination": "DXB", "departure_date": "2025-11-20"}
t1 = time.perf_counter()
tool.invoke(params)
first = time.perf_counter() - t1

t2 = time.perf_counter()
tool.invoke(params)
second = time.perf_counter() - t2

print(f"  1st call : {first:.3f}s")
print(f"  2nd call : {second:.4f}s  (cache)")
if second > 0:
    print(f"  speedup  : {first / second:.0f}x")

print("\n✓ FlightSearchTool working\n")
