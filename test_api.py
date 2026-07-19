"""
Full API test — Weeks 1-12 endpoints.
Run: poetry run python test_api.py
"""
import json
import sys
import time
import httpx

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def show(label: str, data: dict | list, ok: bool = True) -> None:
    global PASS, FAIL
    status = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"\n[{status}] {label}")
    text = json.dumps(data, indent=2, default=str)
    # truncate long outputs
    lines = text.splitlines()
    if len(lines) > 40:
        text = "\n".join(lines[:40]) + f"\n  ... ({len(lines)-40} more lines)"
    print(text)


# ── 1. Health ────────────────────────────────────────────────
section("HEALTH & ROOT")

r = httpx.get(f"{BASE}/", timeout=10)
show("GET /  (root)", r.json(), r.status_code == 200)

r = httpx.get(f"{BASE}/health", timeout=10)
show("GET /health", r.json(), r.status_code == 200)

r = httpx.get(f"{BASE}/cache/health", timeout=10)
show("GET /cache/health", r.json(), r.status_code == 200)

# ── 2. Flights ───────────────────────────────────────────────
section("FLIGHTS (Week 2)")

r = httpx.get(f"{BASE}/flights", params={"origin": "AMD", "destination": "DEL"}, timeout=15)
data = r.json()
show(
    "GET /flights  AMD→DEL",
    {"count": len(data.get("results", [])), "first": data.get("results", [{}])[0]},
    r.status_code == 200 and len(data.get("results", [])) > 0,
)

# ── 3. Hotels ────────────────────────────────────────────────
section("HOTELS (Week 2)")

r = httpx.get(
    f"{BASE}/api/hotels",
    params={"city": "Paris", "check_in": "2025-09-01", "check_out": "2025-09-06", "adults": 2},
    timeout=15,
)
data = r.json()
show(
    "GET /api/hotels  Paris 5 nights",
    {"count": data.get("count"), "first": data.get("results", [{}])[0]},
    r.status_code == 200 and data.get("count", 0) > 0,
)

# ── 4. Weather ───────────────────────────────────────────────
section("WEATHER (Week 3)")

r = httpx.get(f"{BASE}/api/trip/weather", params={"city": "London", "days": 5}, timeout=20)
data = r.json()
show(
    "GET /api/trip/weather  London 5 days",
    data[:2] if isinstance(data, list) and data else data,
    r.status_code == 200,
)

# ── 5. Attractions ───────────────────────────────────────────
section("ATTRACTIONS (Week 3)")

r = httpx.get(
    f"{BASE}/api/trip/attractions",
    params={"city": "Paris", "limit": 5},
    timeout=30,
)
data = r.json()
show(
    "GET /api/trip/attractions  Paris limit=5",
    data[:2] if isinstance(data, list) and data else data,
    r.status_code == 200,
)

# ── 6. Restaurants ───────────────────────────────────────────
section("RESTAURANTS (Week 3)")

r = httpx.get(
    f"{BASE}/api/trip/restaurants",
    params={"city": "Tokyo", "cuisine": "sushi", "min_rating": 4.0, "limit": 3},
    timeout=20,
)
data = r.json()
show(
    "GET /api/trip/restaurants  Tokyo sushi",
    data[:2] if isinstance(data, list) and data else data,
    r.status_code == 200,
)

# ── 7. Budget Tracker ────────────────────────────────────────
section("BUDGET TRACKER (Week 3)")

trip_id = "test-paris-2025"

r = httpx.post(
    f"{BASE}/api/trip/budget",
    json={"trip_id": trip_id, "action": "set_budget", "total_budget": 3000.0},
    timeout=10,
)
show("POST /api/trip/budget  set_budget $3000", r.json(), r.status_code == 200)

r = httpx.post(
    f"{BASE}/api/trip/budget",
    json={"trip_id": trip_id, "action": "add_expense", "category": "hotel", "amount": 800.0, "description": "4 nights"},
    timeout=10,
)
show("POST /api/trip/budget  add hotel $800", r.json(), r.status_code == 200)

r = httpx.post(
    f"{BASE}/api/trip/budget",
    json={"trip_id": trip_id, "action": "add_expense", "category": "activities", "amount": 150.0, "description": "museums"},
    timeout=10,
)
show("POST /api/trip/budget  add activities $150", r.json(), r.status_code == 200)

r = httpx.get(f"{BASE}/api/trip/budget/{trip_id}", timeout=10)
data = r.json()
show(
    "GET /api/trip/budget/{trip_id}  summary",
    data,
    r.status_code == 200 and data.get("spent_total") == 950.0,
)

# ── 8. Full Trip Planner (Week 11) ───────────────────────────
section("FULL TRIP PLANNER — Week 11 Optimizer")

print("\n  Planning 'Paris 5 days $3000 for 2 people'  (may take 5-30s)...")
t0 = time.perf_counter()
r = httpx.post(
    f"{BASE}/api/trip/plan",
    json={"request": "Paris 5 days $3000 for 2 people"},
    timeout=60,
)
elapsed = time.perf_counter() - t0
data = r.json()
itinerary = data.get("itinerary", {})
days = itinerary.get("days", [])
total_acts = sum(len(d.get("activities", [])) for d in days)

show(
    f"POST /api/trip/plan  ({elapsed:.1f}s)",
    {
        "destination": itinerary.get("destination"),
        "title": itinerary.get("title"),
        "start_date": itinerary.get("start_date"),
        "end_date": itinerary.get("end_date"),
        "num_days": len(days),
        "total_activities": total_acts,
        "total_cost_usd": itinerary.get("total_cost_usd"),
        "budget_usd": itinerary.get("budget_usd"),
        "within_budget": itinerary.get("total_cost_usd", 0) <= (itinerary.get("budget_usd") or 9999),
        "day_1_activities": [
            {"slot": a.get("time_slot"), "title": a.get("title"), "priority": a.get("priority")}
            for a in days[0].get("activities", [])
        ] if days else [],
    },
    r.status_code == 200 and len(days) > 0,
)

# ── 9. Evaluate Itinerary (Week 12) ─────────────────────────
section("ITINERARY EVALUATOR — Week 12 Judge")

if itinerary:
    print("\n  Evaluating the itinerary just planned...")
    r2 = httpx.post(
        f"{BASE}/api/trip/evaluate",
        json={"itinerary": itinerary, "request": "Paris 5 days $3000 for 2 people"},
        timeout=30,
    )
    eval_data = r2.json()
    scores = eval_data.get("scores", {})
    show(
        f"POST /api/trip/evaluate  ({eval_data.get('planning_time_ms', 0):.0f}ms)",
        {dim: entry.get("score") for dim, entry in scores.items()},
        r2.status_code == 200 and len(scores) == 10,
    )
    if scores:
        print("\n  Dimension scores:")
        for dim, entry in scores.items():
            bar = "█" * entry.get("score", 0)
            print(f"    {dim:<22} {entry.get('score')}/5  {bar}  — {entry.get('justification', '')[:60]}")
else:
    print("  Skipping evaluate — no itinerary from planner")

# ── 10. Week 12 Baseline (summary) ──────────────────────────
section("WEEK 12 BASELINE RESULTS SUMMARY")

from pathlib import Path
import csv

csv_path = Path("tests/evaluation/baseline_results.csv")
if csv_path.exists():
    rows = list(csv.DictReader(csv_path.open()))
    dims = ["feasibility","budget_accuracy","geo_efficiency","weather_match","completeness",
            "priority_adherence","walking_balance","time_realism","activity_diversity","preference_match"]
    avgs = {}
    for d in dims:
        vals = [float(r[d]) for r in rows if r.get(d)]
        avgs[d] = round(sum(vals)/len(vals), 2) if vals else 0.0

    print(f"\n  {len(rows)} scenarios evaluated. Average scores per dimension:")
    for dim, avg in sorted(avgs.items(), key=lambda x: x[1]):
        bar = "█" * int(avg)
        print(f"    {dim:<22} {avg:.2f}/5  {bar}")

    PASS += 1
    print(f"\n[PASS] Baseline CSV loaded — {len(rows)} rows")
else:
    print("  baseline_results.csv not found — run: poetry run python tests/evaluation/run_baseline.py")

# ── Summary ──────────────────────────────────────────────────
section("RESULTS SUMMARY")
total = PASS + FAIL
print(f"\n  {PASS}/{total} checks passed")
if FAIL == 0:
    print("  ALL SYSTEMS OPERATIONAL — Weeks 1-12 complete\n")
else:
    print(f"  {FAIL} check(s) failed — see above\n")

sys.exit(0 if FAIL == 0 else 1)
