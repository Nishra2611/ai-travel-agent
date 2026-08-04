"""
ai_travel_agent/geo/geo_visualizer.py — Week 9

Renders a ClusteringResult as an interactive Folium HTML map. This is
deliberately NOT a graph node -- it's a side-effecting file-write helper
called from demo scripts / a future "download map" API route, same reason
geocode_client.py's raw HTTP calls aren't nodes either. build_geo_clusters
(nodes.py) only ever returns state; nothing in the graph should reach out
to the filesystem.

Drop this file at: ai_travel_agent/geo/geo_visualizer.py
"""

from __future__ import annotations

from pathlib import Path

import folium

from ai_travel_agent.geo.geo_clustering import ClusteringResult

NOISE_COLOR = "#808080"
DEFAULT_ZOOM_START = 13


def render_clustering_map(result: ClusteringResult, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_points = [p for c in result.clusters for p in c.points] + result.noise_points
    if not all_points:
        raise ValueError("cannot render a map with zero points")

    center_lat = sum(p.latitude for p in all_points) / len(all_points)
    center_lng = sum(p.longitude for p in all_points) / len(all_points)
    fmap = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=DEFAULT_ZOOM_START,
        tiles="cartodbpositron",
    )

    for cluster in result.clusters:
        group = folium.FeatureGroup(name=cluster.label)
        for point in cluster.points:
            folium.CircleMarker(
                location=[point.latitude, point.longitude],
                radius=6,
                color=cluster.color_hex,
                fill=True,
                fill_color=cluster.color_hex,
                fill_opacity=0.85,
                tooltip=f"{point.name} ({cluster.label})",
            ).add_to(group)
        folium.Marker(
            location=[cluster.centroid_lat, cluster.centroid_lng],
            icon=folium.Icon(color="black", icon="star"),
            tooltip=f"{cluster.label} centroid",
        ).add_to(group)
        group.add_to(fmap)

    if result.noise_points:
        noise_group = folium.FeatureGroup(name="Unclustered")
        for point in result.noise_points:
            folium.CircleMarker(
                location=[point.latitude, point.longitude],
                radius=4,
                color=NOISE_COLOR,
                fill=True,
                fill_color=NOISE_COLOR,
                fill_opacity=0.5,
                tooltip=f"{point.name} (unclustered)",
            ).add_to(noise_group)
        noise_group.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(str(output_path))
    return output_path
