"""
tests/unit/test_build_geo_node.py — Week 9

Tests build_geo_clusters with hand-built TravelState dicts -- no compiled
graph. Focuses on the state plumbing (missing coordinates, empty results,
partial data) since the clustering math itself is already covered in
test_geo_clustering.py.
"""

from __future__ import annotations

from ai_travel_agent.agents.nodes import _collect_points, build_geo_clusters


def test_collects_points_from_attractions_restaurants_and_hotel():
    state = {
        "attractions": [
            {"id": "a1", "name": "Louvre", "latitude": 48.86, "longitude": 2.33}
        ],
        "restaurants": [
            {"id": "r1", "name": "Cafe", "latitude": 48.85, "longitude": 2.34}
        ],
        "hotels": [
            {"id": "h1", "name": "Hotel A", "latitude": 48.85, "longitude": 2.35}
        ],
    }
    points = _collect_points(state)
    ids = {p.id for p in points}
    assert ids == {"a1", "r1", "h1"}


def test_skips_items_missing_coordinates():
    state = {
        "attractions": [
            {"id": "a1", "name": "Has coords", "latitude": 48.86, "longitude": 2.33},
            {"id": "a2", "name": "Missing coords"},
        ],
    }
    points = _collect_points(state)
    assert len(points) == 1
    assert points[0].id == "a1"


def test_build_geo_clusters_returns_none_when_no_geocoded_points():
    state = {"attractions": [{"id": "a1", "name": "No coords"}]}
    result = build_geo_clusters(state)
    assert result["geo_clusters"] is None


def test_build_geo_clusters_produces_result_with_enough_points():
    state = {
        "preferences": {"destination_city": "Paris"},
        "attractions": [
            {
                "id": "a1",
                "name": "Eiffel Tower",
                "latitude": 48.8584,
                "longitude": 2.2945,
            },
            {"id": "a2", "name": "Louvre", "latitude": 48.8606, "longitude": 2.3376},
            {
                "id": "a3",
                "name": "Notre-Dame",
                "latitude": 48.8530,
                "longitude": 2.3499,
            },
        ],
        "restaurants": [],
        "hotels": [
            {"id": "h1", "name": "Hotel A", "latitude": 48.8629, "longitude": 2.3355}
        ],
    }
    result = build_geo_clusters(state)
    assert result["geo_clusters"] is not None
    assert result["geo_clusters"]["city"] == "Paris"
    assert len(result["geo_clusters"]["clusters"]) >= 1


def test_build_geo_clusters_never_raises_on_malformed_state():
    """A missing 'preferences' key entirely, or non-dict attractions, must
    degrade to geo_clusters=None rather than crashing the graph."""
    result = build_geo_clusters({})
    assert result["geo_clusters"] is None
