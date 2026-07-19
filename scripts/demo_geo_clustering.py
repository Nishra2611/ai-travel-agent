"""
scripts/demo_geo_clustering.py — Week 9

Exercises get_distance_matrix_safe + _GeoClusterBuilder directly, no
graph/LangChain involved -- same spirit as demo_budget_optimizer.py and
demo_itinerary_builder.py. Uses the mock Paris fixture (no OSRM network
call required, since we go straight to clustering on raw coordinates --
distance matrix is demoed separately below with a real OSRM call, which
falls back to Haversine automatically if OSRM is unreachable).

Run: poetry run python scripts/demo_geo_clustering.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_travel_agent.geo.distance_matrix_client import (
    GeoPoint,
    get_distance_matrix_safe,
)
from ai_travel_agent.geo.geo_clustering import _GeoClusterBuilder
from ai_travel_agent.geo.geo_visualizer import render_clustering_map

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "paris_pois.json"
OUTPUT = Path(__file__).parent.parent / "outputs" / "geo_maps" / "paris_demo.html"


def main() -> None:
    data = json.loads(FIXTURE.read_text())
    points = [
        GeoPoint(
            id=p["id"], name=p["name"], latitude=p["latitude"], longitude=p["longitude"]
        )
        for p in data["points"]
    ]
    print(f"Loaded {len(points)} points for {data['city']}")

    # 1. Distance matrix (real OSRM call, safe-falls-back to haversine if unreachable)
    matrix = get_distance_matrix_safe(points[:5], profile="walking")
    print(
        f"\n1) Distance matrix source: {matrix.source}  ({len(matrix.entries)} pairs)"
    )
    sample = matrix.entries[0]
    print(
        f"   sample: {sample.origin_id} -> {sample.destination_id} = "
        f"{sample.distance_meters:.0f}m, {sample.duration_seconds/60:.1f}min"
    )

    # 2. Clustering
    builder = _GeoClusterBuilder()
    result = builder.cluster(data["city"], points)
    print(
        f"\n2) DBSCAN result: {len(result.clusters)} clusters, {len(result.noise_points)} noise points"
    )
    print(f"   Silhouette score: {result.silhouette_score}")
    for cluster in result.clusters:
        names = ", ".join(p.name for p in cluster.points)
        print(
            f"\n   [{cluster.label}] centroid=({cluster.centroid_lat:.4f}, {cluster.centroid_lng:.4f})"
        )
        print(f"     {names}")
    if result.noise_points:
        print(
            f"\n   Noise (unclustered): {', '.join(p.name for p in result.noise_points)}"
        )

    # 3. Map
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    render_clustering_map(result, OUTPUT)
    print(f"\n3) Map written to {OUTPUT}")


if __name__ == "__main__":
    main()
