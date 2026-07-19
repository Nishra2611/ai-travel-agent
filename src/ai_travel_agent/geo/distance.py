"""Cached distance matrix using haversine formula."""
from __future__ import annotations

import math
from functools import lru_cache


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


@lru_cache(maxsize=4096)
def cached_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km(lat1, lng1, lat2, lng2)


def build_distance_matrix(points: list[tuple[float, float]]) -> list[list[float]]:
    """Build NxN distance matrix for a list of (lat, lng) tuples."""
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = cached_distance_km(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix
