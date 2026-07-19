"""DBSCAN-based POI clustering for grouping attractions by proximity."""
from __future__ import annotations

import math
from typing import Any


def _dbscan(
    points: list[tuple[float, float]],
    eps_km: float = 2.0,
    min_samples: int = 1,
) -> list[int]:
    """Minimal DBSCAN returning cluster label per point (-1 = noise)."""
    n = len(points)
    labels = [-1] * n
    cluster_id = 0

    def neighbors(idx: int) -> list[int]:
        result = []
        lat1, lng1 = points[idx]
        for j, (lat2, lng2) in enumerate(points):
            if j == idx:
                continue
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
            d = 6371.0 * 2 * math.asin(math.sqrt(a))
            if d <= eps_km:
                result.append(j)
        return result

    visited = [False] * n
    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        nbrs = neighbors(i)
        if len(nbrs) < min_samples:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        queue = list(nbrs)
        while queue:
            q = queue.pop()
            if not visited[q]:
                visited[q] = True
                q_nbrs = neighbors(q)
                if len(q_nbrs) >= min_samples:
                    queue.extend(q_nbrs)
            if labels[q] == -1:
                labels[q] = cluster_id
        cluster_id += 1

    return labels


def cluster_attractions(
    attractions: list[dict[str, Any]],
    num_days: int,
    eps_km: float = 3.0,
) -> list[list[dict[str, Any]]]:
    """
    Cluster attractions into num_days groups by geographic proximity.
    Returns a list of num_days buckets (some may be empty if few attractions).
    """
    if not attractions:
        return [[] for _ in range(num_days)]

    points = [(float(a.get("lat", 0)), float(a.get("lng", 0))) for a in attractions]
    labels = _dbscan(points, eps_km=eps_km)

    # Group by cluster label
    clusters: dict[int, list[dict[str, Any]]] = {}
    for i, label in enumerate(labels):
        clusters.setdefault(label, []).append(attractions[i])

    # Sort clusters by size descending, noise (-1) last
    sorted_clusters = sorted(
        clusters.items(),
        key=lambda kv: (kv[0] != -1, len(kv[1])),
        reverse=True,
    )
    cluster_lists = [v for _, v in sorted_clusters]

    # Distribute into num_days buckets
    # If only one cluster (all attractions nearby), split evenly across days
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(num_days)]
    if len(cluster_lists) == 1:
        # Even distribution: round-robin individual attractions
        for i, attraction in enumerate(cluster_lists[0]):
            buckets[i % num_days].append(attraction)
    else:
        for i, cluster in enumerate(cluster_lists):
            buckets[i % num_days].extend(cluster)

    return buckets
