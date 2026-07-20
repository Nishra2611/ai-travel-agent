"""Nearest-neighbor + 2-opt route optimizer for a list of attractions."""
from __future__ import annotations

from typing import Any

from ai_travel_agent.geo.distance import build_distance_matrix, cached_distance_km


def _nn_route(matrix: list[list[float]]) -> list[int]:
    """Nearest-neighbor greedy tour starting from index 0."""
    n = len(matrix)
    unvisited = set(range(1, n))
    route = [0]
    while unvisited:
        last = route[-1]
        nearest = min(unvisited, key=lambda j: matrix[last][j])
        route.append(nearest)
        unvisited.remove(nearest)
    return route


def _two_opt(route: list[int], matrix: list[list[float]], max_iter: int = 100) -> list[int]:
    """2-opt improvement on a route."""
    best = route[:]
    improved = True
    iterations = 0
    while improved and iterations < max_iter:
        improved = False
        iterations += 1
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                d_before = matrix[best[i - 1]][best[i]] + matrix[best[j - 1]][best[j]]
                d_after = matrix[best[i - 1]][best[j - 1]] + matrix[best[i]][best[j]]
                if d_after < d_before - 1e-9:
                    best[i:j] = best[i:j][::-1]
                    improved = True
    return best


def optimize_route(attractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return attractions reordered for minimum travel distance."""
    if len(attractions) <= 2:
        return attractions

    points = [(float(a.get("lat", 0)), float(a.get("lng", 0))) for a in attractions]
    matrix = build_distance_matrix(points)
    route = _nn_route(matrix)
    route = _two_opt(route, matrix)
    return [attractions[i] for i in route]


def total_route_distance_km(attractions: list[dict[str, Any]]) -> float:
    """Compute total walking/travel distance for an ordered list of attractions."""
    total = 0.0
    for i in range(len(attractions) - 1):
        a, b = attractions[i], attractions[i + 1]
        total += cached_distance_km(
            float(a.get("lat", 0)), float(a.get("lng", 0)),
            float(b.get("lat", 0)), float(b.get("lng", 0)),
        )
    return total
