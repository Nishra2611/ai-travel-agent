"""
scripts/benchmark_route_optimizer.py — Week 10

The roadmap's explicit Day 7-equivalent deliverable: "Benchmark: compare NN
heuristic vs random ordering on 20 scenarios, document improvement %."

Generates 20 synthetic scenarios (varying activity counts 3-8, varying
point layouts, seeded for reproducibility) rather than depending on live
OSRM/geocoding, so this runs offline and produces the same numbers every
time. Each scenario's distance matrix is asymmetric (random directional
costs, modeling one-way streets) so the benchmark reflects the same
conditions _RouteOptimizer is designed for, not an easier symmetric case.

Run: poetry run python scripts/benchmark_route_optimizer.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_travel_agent.geo.distance_matrix_client import GeoPoint  # noqa: E402
from ai_travel_agent.route.route_optimizer import _RouteOptimizer  # noqa: E402

NUM_SCENARIOS = 20
MIN_ACTIVITIES, MAX_ACTIVITIES = 3, 8


def _make_scenario(
    seed: int,
) -> tuple[GeoPoint, list[GeoPoint], dict[tuple[str, str], float]]:
    rng = random.Random(seed)
    n = rng.randint(MIN_ACTIVITIES, MAX_ACTIVITIES)
    ids = ["hotel"] + [f"a{i}" for i in range(n)]

    costs: dict[tuple[str, str], float] = {}
    for o in ids:
        for d in ids:
            if o != d:
                # Asymmetric on purpose -- models one-way streets/transit
                # direction, same reasoning as distance_matrix_client.
                costs[(o, d)] = rng.uniform(2.0, 25.0)

    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0.0, longitude=0.0)
    activities = [GeoPoint(id=k, name=k, latitude=0.0, longitude=0.0) for k in ids[1:]]
    return hotel, activities, costs


def main() -> None:
    optimizer = _RouteOptimizer()
    improvements: list[float] = []

    print(
        f"{'#':<4}{'n':<4}{'optimized (s)':<16}{'naive (s)':<14}{'efficiency':<12}{'improvement %'}"
    )
    print("-" * 66)

    for i in range(1, NUM_SCENARIOS + 1):
        hotel, activities, costs = _make_scenario(seed=i)

        def lookup(o: str, d: str, costs=costs) -> float:
            return 0.0 if o == d else costs[(o, d)]

        result = optimizer.optimize_day(hotel, activities, lookup, seed=i)
        improvements.append(result.improvement_pct)

        print(
            f"{i:<4}{len(activities):<4}{result.optimized_seconds:<16.1f}"
            f"{result.naive_baseline_seconds:<14.1f}{result.efficiency_score:<12.2f}"
            f"{result.improvement_pct:.1f}%"
        )

    print("-" * 66)
    mean_improvement = sum(improvements) / len(improvements)
    print(f"Mean improvement over naive random ordering: {mean_improvement:.1f}%")
    print(f"Best case: {max(improvements):.1f}%   Worst case: {min(improvements):.1f}%")
    print(
        f"Scenarios with zero/negative improvement: {sum(1 for x in improvements if x <= 0)}/{NUM_SCENARIOS}"
    )


if __name__ == "__main__":
    main()
