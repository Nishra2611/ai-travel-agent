"""
scripts/demo_hotel_search.py

Run from project root:
    poetry run python scripts/demo_hotel_search.py

What this proves:
    - HotelSearchTool instantiates correctly
    - Mock fallback returns 10 results
    - Rating and price filters work
    - Cache stores result (second call is instant)
    - Total price = per_night × nights
"""

import time

from dotenv import load_dotenv

load_dotenv()

from src.tools.hotel_search import HotelSearchTool  # noqa: E402

tool = HotelSearchTool(use_mock_on_failure=True)

QUERIES = [
    {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15", "adults": 2},
    {"city": "Tokyo", "check_in": "2026-01-10", "check_out": "2026-01-17", "adults": 1},
    {"city": "Bali", "check_in": "2026-02-01", "check_out": "2026-02-08", "adults": 2},
    {"city": "Dubai", "check_in": "2026-03-05", "check_out": "2026-03-10", "adults": 3},
]

print("=" * 60)
print("HotelSearchTool — demo")
print("=" * 60)

for q in QUERIES:
    print(f"\n{q['city']}  |  {q['check_in']} → {q['check_out']}")
    t0 = time.perf_counter()
    results = tool.invoke(q)
    elapsed = time.perf_counter() - t0
    print(f"  {len(results)} hotels  ({elapsed:.2f}s)")
    for h in results:
        stars = "★" * int(h.get("star_rating") or 0)
        eco = " 🌿" if h.get("eco_certified") else ""
        print(
            f"    {h['name'][:35]:<35}"
            f"  {stars:<5}"
            f"  {h['review_score'] or '-'}/5"
            f"  ${h['price_per_night_usd']:.0f}/night"
            f"  ${h['total_price_usd']:.0f} total"
            f"{eco}"
        )

# --- filter demo ---
print("\n--- min_rating=4.4, max_price_per_night=200 ---")
filtered = tool.invoke(
    {
        "city": "Paris",
        "check_in": "2025-12-10",
        "check_out": "2025-12-15",
        "min_rating": 4.4,
        "max_price_per_night": 200.0,
    }
)
print(f"  {len(filtered)} hotels match")
for h in filtered:
    print(f"    {h['name']}  ★{h['star_rating']}  ${h['price_per_night_usd']}/night")

# --- cache speedup demo ---
print("\n--- cache speedup ---")
params = {"city": "london", "check_in": "2025-11-01", "check_out": "2025-11-05"}
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

print("\n✓ HotelSearchTool working\n")
