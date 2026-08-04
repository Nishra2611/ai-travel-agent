"""
tests/unit/test_geo_clustering.py — Week 9

Unit tests _GeoClusterBuilder directly against the 3 mock city fixtures
(tests/fixtures/{paris,tokyo,newyork}_pois.json) -- no OSRM, no graph.
Verifies cluster count sanity, every point clustered-or-noise, known
outliers correctly flagged as noise, centroid correctness, silhouette
range, and the k-means fallback path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_travel_agent.geo.distance_matrix_client import GeoPoint
from ai_travel_agent.geo.geo_clustering import (
    DEFAULT_EPS_METERS,
    DEFAULT_MIN_SAMPLES,
    _GeoClusterBuilder,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

KNOWN_OUTLIERS = {
    "paris_pois.json": "p13",  # Chateau de Vincennes
    "tokyo_pois.json": "p12",  # Ghibli Museum
    "newyork_pois.json": "p12",  # Coney Island
}


def _load_fixture(filename: str) -> tuple[str, list[GeoPoint]]:
    data = json.loads((FIXTURES_DIR / filename).read_text())
    points = [
        GeoPoint(
            id=p["id"], name=p["name"], latitude=p["latitude"], longitude=p["longitude"]
        )
        for p in data["points"]
    ]
    return data["city"], points


@pytest.fixture
def builder() -> _GeoClusterBuilder:
    return _GeoClusterBuilder()


@pytest.mark.parametrize(
    "fixture_file", ["paris_pois.json", "tokyo_pois.json", "newyork_pois.json"]
)
def test_dbscan_produces_reasonable_clusters(builder, fixture_file):
    city, points = _load_fixture(fixture_file)
    result = builder.cluster(
        city, points, eps_meters=DEFAULT_EPS_METERS, min_samples=DEFAULT_MIN_SAMPLES
    )

    assert 1 <= len(result.clusters) <= len(points) - 1
    clustered_ids = {p.id for c in result.clusters for p in c.points}
    noise_ids = {p.id for p in result.noise_points}
    assert clustered_ids | noise_ids == {p.id for p in points}
    assert clustered_ids.isdisjoint(noise_ids)


@pytest.mark.parametrize(
    "fixture_file", ["paris_pois.json", "tokyo_pois.json", "newyork_pois.json"]
)
def test_dbscan_flags_known_outlier_as_noise(builder, fixture_file):
    city, points = _load_fixture(fixture_file)
    result = builder.cluster(
        city, points, eps_meters=DEFAULT_EPS_METERS, min_samples=DEFAULT_MIN_SAMPLES
    )

    noise_ids = {p.id for p in result.noise_points}
    assert KNOWN_OUTLIERS[fixture_file] in noise_ids


@pytest.mark.parametrize(
    "fixture_file", ["paris_pois.json", "tokyo_pois.json", "newyork_pois.json"]
)
def test_centroid_is_mean_of_members(builder, fixture_file):
    city, points = _load_fixture(fixture_file)
    result = builder.cluster(city, points)

    for cluster in result.clusters:
        expected_lat = sum(p.latitude for p in cluster.points) / len(cluster.points)
        expected_lng = sum(p.longitude for p in cluster.points) / len(cluster.points)
        assert cluster.centroid_lat == pytest.approx(expected_lat, abs=1e-9)
        assert cluster.centroid_lng == pytest.approx(expected_lng, abs=1e-9)


@pytest.mark.parametrize(
    "fixture_file", ["paris_pois.json", "tokyo_pois.json", "newyork_pois.json"]
)
def test_silhouette_in_valid_range(builder, fixture_file):
    city, points = _load_fixture(fixture_file)
    result = builder.cluster(city, points)
    if len(result.clusters) >= 2:
        assert result.silhouette_score is not None
        assert -1.0 <= result.silhouette_score <= 1.0


def test_kmeans_fallback_assigns_every_point():
    city, points = _load_fixture("paris_pois.json")
    result = _GeoClusterBuilder().cluster(city, points, algorithm="kmeans", kmeans_k=3)

    assert len(result.clusters) == 3
    assert result.noise_points == []
    assert sum(len(c.points) for c in result.clusters) == len(points)


def test_fewer_than_three_points_returns_single_cluster_not_error():
    points = [
        GeoPoint(id="a", name="A", latitude=48.85, longitude=2.35),
        GeoPoint(id="b", name="B", latitude=48.86, longitude=2.34),
    ]
    result = _GeoClusterBuilder().cluster("Nowhere", points)
    assert len(result.clusters) == 1
    assert len(result.clusters[0].points) == 2
