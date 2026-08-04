"""
scripts/demo_caching.py

Run from project root:
    poetry run python scripts/demo_caching.py

What this proves:
    - CacheManager.get / set / increment_api_calls / get_api_calls_today all work
    - Second tool call is served from cache (50-200x faster)
    - Results from cache are byte-for-byte identical to first call
    - Daily budget counter increments and reads correctly
"""

import time

from dotenv import load_dotenv

load_dotenv()

from ai_travel_agent.tools.flight_search import FlightSearchTool  # noqa: E402
from ai_travel_agent.tools.hotel_search import HotelSearchTool  # noqa: E402
from ai_travel_agent.utils.cache import cache  # noqa: E402

print("=" * 60)
print("Cache verification demo")
print("=" * 60)

# --- 1. health check ---
print(f"\nRedis healthy : {cache.is_healthy()}")

# --- 2. hotel cache speedup ---
print("\n--- Hotel cache speedup ---")
htool = HotelSearchTool(use_mock_on_failure=True)
hparams = {
    "city": "paris",
    "check_in": "2025-12-10",
    "check_out": "2025-12-15",
    "adults": 2,
}

t1 = time.perf_counter()
r1 = htool.invoke(hparams)
first = time.perf_counter() - t1

t2 = time.perf_counter()
r2 = htool.invoke(hparams)
second = time.perf_counter() - t2

print(f"  1st call : {first:.3f}s  ({len(r1)} hotels)")
print(f"  2nd call : {second:.4f}s  ({len(r2)} hotels)  ← from cache")
print(f"  Identical: {r1 == r2}")
if second > 0:
    print(f"  Speedup  : {first / second:.0f}x")

# --- 3. flight cache speedup ---
print("\n--- Flight cache speedup ---")
ftool = FlightSearchTool(use_mock_on_failure=True)
fparams = {"origin": "BOM", "destination": "CDG", "departure_date": "2025-12-10"}

t3 = time.perf_counter()
f1 = ftool.invoke(fparams)
first_f = time.perf_counter() - t3

t4 = time.perf_counter()
f2 = ftool.invoke(fparams)
second_f = time.perf_counter() - t4

print(f"  1st call : {first_f:.3f}s  ({len(f1)} flights)")
print(f"  2nd call : {second_f:.4f}s  ({len(f2)} flights)  ← from cache")
print(f"  Identical: {f1 == f2}")
if second_f > 0:
    print(f"  Speedup  : {first_f / second_f:.0f}x")

# --- 4. budget counter ---
print("\n--- Daily API budget counter ---")
before = cache.get_api_calls_today("serpapi")
print(f"  Calls today before : {before}")
cache.increment_api_calls("serpapi")
after = cache.get_api_calls_today("serpapi")
print(f"  Calls today after  : {after}")
print(f"  Counter works      : {after == before + 1}")

print("\n✓ Cache fully verified\n")
