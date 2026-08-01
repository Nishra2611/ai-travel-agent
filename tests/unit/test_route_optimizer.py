"""
tests/unit/test_route_optimizer.py — Week 10

Unit tests _RouteOptimizer directly (no graph, no network) -- same pattern
as test_budget_optimizer.py / test_geo_clustering.py. Covers:
  - NN+2opt matches the true optimum on a small symmetric case (exact
    brute-force comparison)
  - multi-start 2opt stays within a documented gap of the true optimum on
    asymmetric (one-way-aware) cases, where plain single-start 2opt was
    verified during development to land 47% off optimum
  - the 20-scenario benchmark from scripts/benchmark_route_optimizer.py,
    re-run here as assertions: every scenario should show positive
    improvement over the naive random baseline, and the mean improvement
    should clear a documented floor
  - trivial cases (0-1 activities) don't crash and report no improvement
  - efficiency_score / improvement_pct arithmetic is internally consistent
"""

from __future__ import annotations

import itertools
import random

import pytest

from ai_travel_agent.geo.distance_matrix_client import GeoPoint
from ai_travel_agent.route.route_optimizer import _RouteOptimizer


@pytest.fixture
def optimizer() -> _RouteOptimizer:
    return _RouteOptimizer()


def _brute_force_optimum(hotel, activities, lookup) -> float:
    best = None
    for perm in itertools.permutations(activities):
        order = [hotel, *perm]
        cost = sum(lookup(order[i].id, order[i + 1].id) for i in range(len(order) - 1))
        cost += lookup(order[-1].id, order[0].id)
        if best is None or cost < best:
            best = cost
    return best


def test_finds_true_optimum_on_symmetric_line_case(optimizer):
    positions = {"hotel": 0, "a1": 3, "a2": 1, "a3": 5, "a4": 2, "a5": 4}

    def lookup(o, d):
        return abs(positions[o] - positions[d])

    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
    activities = [
        GeoPoint(id=k, name=k, latitude=0, longitude=0)
        for k in ["a1", "a2", "a3", "a4", "a5"]
    ]

    result = optimizer.optimize_day(hotel, activities, lookup, seed=1)
    true_optimum = _brute_force_optimum(hotel, activities, lookup)
    assert result.optimized_seconds == pytest.approx(true_optimum, abs=1e-6)


@pytest.mark.parametrize("seed", range(10))
def test_stays_within_documented_gap_on_asymmetric_cases(optimizer, seed):
    rng = random.Random(seed)
    n = rng.randint(4, 7)
    ids = ["hotel"] + [f"a{i}" for i in range(n)]
    costs = {(o, d): rng.uniform(1, 20) for o in ids for d in ids if o != d}

    def lookup(o, d):
        return 0.0 if o == d else costs[(o, d)]

    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
    activities = [GeoPoint(id=k, name=k, latitude=0, longitude=0) for k in ids[1:]]

    result = optimizer.optimize_day(hotel, activities, lookup, seed=seed)
    true_optimum = _brute_force_optimum(hotel, activities, lookup)

    gap_pct = (result.optimized_seconds - true_optimum) / true_optimum * 100
    # Documented ceiling from development verification (multi-start 2opt
    # sweep across 15 random asymmetric cases: mean gap 1.9%, max 12.1%).
    # 20% gives headroom for RNG variance across seeds not in that sweep.
    assert gap_pct < 20.0, f"seed {seed}: gap {gap_pct:.1f}% exceeds documented ceiling"


def test_20_scenario_benchmark_all_positive_improvement(optimizer):
    """Re-runs the same scenario generator as
    scripts/benchmark_route_optimizer.py as an assertion suite. Verified
    result at time of writing: mean improvement 42.1%, worst case 15.6%,
    0/20 scenarios with zero-or-negative improvement."""
    improvements = []
    for seed in range(1, 21):
        rng = random.Random(seed)
        n = rng.randint(3, 8)
        ids = ["hotel"] + [f"a{i}" for i in range(n)]
        costs = {(o, d): rng.uniform(2.0, 25.0) for o in ids for d in ids if o != d}

        def lookup(o, d, costs=costs):
            return 0.0 if o == d else costs[(o, d)]

        hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
        activities = [GeoPoint(id=k, name=k, latitude=0, longitude=0) for k in ids[1:]]
        result = optimizer.optimize_day(hotel, activities, lookup, seed=seed)
        improvements.append(result.improvement_pct)

    assert all(
        imp > 0 for imp in improvements
    ), "every scenario should beat naive random ordering"
    mean_improvement = sum(improvements) / len(improvements)
    assert (
        mean_improvement > 25.0
    ), f"mean improvement {mean_improvement:.1f}% below documented floor"


def test_zero_activities_returns_trivial_result(optimizer):
    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
    result = optimizer.optimize_day(hotel, [], lambda o, d: 0.0)
    assert result.ordered_activities == []
    assert result.efficiency_score == 1.0
    assert result.improvement_pct == 0.0


def test_single_activity_returns_trivial_result(optimizer):
    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
    activity = GeoPoint(id="a1", name="Only stop", latitude=1, longitude=1)

    def lookup(o, d):
        return 10.0 if o != d else 0.0

    result = optimizer.optimize_day(hotel, [activity], lookup)
    assert [p.id for p in result.ordered_activities] == ["a1"]
    assert result.baseline_method == "trivial"


def test_efficiency_score_and_improvement_pct_are_consistent(optimizer):
    rng = random.Random(99)
    ids = ["hotel", "a0", "a1", "a2", "a3"]
    costs = {(o, d): rng.uniform(1, 20) for o in ids for d in ids if o != d}

    def lookup(o, d):
        return 0.0 if o == d else costs[(o, d)]

    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)
    activities = [GeoPoint(id=k, name=k, latitude=0, longitude=0) for k in ids[1:]]
    result = optimizer.optimize_day(hotel, activities, lookup, seed=99)

    expected_efficiency = result.naive_baseline_seconds / result.optimized_seconds
    expected_improvement = (
        (result.naive_baseline_seconds - result.optimized_seconds)
        / result.naive_baseline_seconds
        * 100
    )
    assert result.efficiency_score == pytest.approx(expected_efficiency, rel=1e-6)
    assert result.improvement_pct == pytest.approx(expected_improvement, rel=1e-6)


def test_exact_baseline_used_below_threshold_sampled_above(optimizer):
    hotel = GeoPoint(id="hotel", name="Hotel", latitude=0, longitude=0)

    small = [
        GeoPoint(id=f"a{i}", name=f"a{i}", latitude=0, longitude=0) for i in range(5)
    ]
    large = [
        GeoPoint(id=f"a{i}", name=f"a{i}", latitude=0, longitude=0) for i in range(9)
    ]

    def lookup(o, d):
        return 1.0 if o != d else 0.0

    small_result = optimizer.optimize_day(hotel, small, lookup, seed=1)
    large_result = optimizer.optimize_day(hotel, large, lookup, seed=1)

    assert small_result.baseline_method == "exact"
    assert large_result.baseline_method == "sampled"
