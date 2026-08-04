"""
scripts/demo_route_optimizer.py — Week 10

Exercises _RouteOptimizer directly against the mock Paris fixture, no
graph/LangChain involved -- same spirit as demo_geo_clustering.py and
demo_budget_optimizer.py. Picks one hotel and the 5 nearest attractions
from the fixture, runs NN + multi-start 2-opt, and prints the optimized
order alongside the efficiency metrics.

Run: poetry run python scripts/demo_route_optimizer.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_travel_agent.geo.distance_matrix_client import (
    GeoPoint,
    get_distance_matrix_safe,
)
from ai_travel_agent.route.route_optimizer import _RouteOptimizer, build_distance_lookup

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "paris_pois.json"


def main() -> None:
    data = json.loads(FIXTURE.read_text())
    points_by_category = {"hotel": [], "attraction": []}
    for p in data["points"]:
        points_by_category.setdefault(p.get("category", "attraction"), []).append(
            GeoPoint(
                id=p["id"],
                name=p["name"],
                latitude=p["latitude"],
                longitude=p["longitude"],
            )
        )

    hotel = points_by_category["hotel"][0]
    activities = points_by_category["attraction"][:6]
    print(f"Hotel: {hotel.name}")
    print(f"Activities ({len(activities)}): {', '.join(p.name for p in activities)}")

    matrix = get_distance_matrix_safe([hotel, *activities], profile="walking")
    print(f"\nDistance matrix source: {matrix.source}")
    distance_lookup = build_distance_lookup(matrix)

    optimizer = _RouteOptimizer()
    result = optimizer.optimize_day(hotel, activities, distance_lookup, seed=42)

    print("\nOptimized order (start and end near hotel):")
    print(f"  {hotel.name} (start)")
    for p in result.ordered_activities:
        print(f"  -> {p.name}")
    print(f"  -> {hotel.name} (end)")

    print(f"\nOptimized total travel time: {result.optimized_seconds/60:.1f} min")
    print(
        f"Naive random baseline ({result.baseline_method}): {result.naive_baseline_seconds/60:.1f} min"
    )
    print(f"Efficiency score: {result.efficiency_score:.2f}x")
    print(f"Improvement over naive: {result.improvement_pct:.1f}%")


if __name__ == "__main__":
    main()
