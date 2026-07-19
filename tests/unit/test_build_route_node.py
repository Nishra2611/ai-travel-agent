"""
tests/unit/test_build_route_node.py — Week 10

Tests optimize_routes with hand-built TravelState dicts -- no compiled
graph. Focuses on state plumbing (missing hotel coords, days with too few
geocoded activities, itinerary mutation) since the routing math itself is
covered in test_route_optimizer.py. No real OSRM call: get_distance_matrix_safe
falls back to Haversine automatically when the sandbox has no network
access, which is itself part of what's being verified here (this node must
degrade gracefully, not fail, when OSRM is unreachable).
"""

from __future__ import annotations

from ai_travel_agent.agents.nodes import (
    _extract_activity_points,
    _extract_hotel_point,
    optimize_routes,
)


def _make_state():
    return {
        "hotels": [
            {"id": "h1", "name": "Hotel A", "latitude": 48.8629, "longitude": 2.3355}
        ],
        "itinerary": {
            "days": [
                {
                    "activities": [
                        {
                            "id": "a1",
                            "name": "Eiffel Tower",
                            "latitude": 48.8584,
                            "longitude": 2.2945,
                            "cost": 20,
                        },
                        {
                            "id": "a2",
                            "name": "Louvre",
                            "latitude": 48.8606,
                            "longitude": 2.3376,
                            "cost": 17,
                        },
                        {
                            "id": "a3",
                            "name": "Notre-Dame",
                            "latitude": 48.8530,
                            "longitude": 2.3499,
                            "cost": 0,
                        },
                    ]
                },
                {
                    "activities": [
                        {
                            "id": "a4",
                            "name": "Only stop",
                            "latitude": 48.85,
                            "longitude": 2.30,
                            "cost": 10,
                        },
                    ]
                },
            ]
        },
    }


def test_extract_hotel_point_returns_none_without_coordinates():
    assert _extract_hotel_point({"hotels": [{"id": "h1", "name": "No coords"}]}) is None
    assert _extract_hotel_point({"hotels": []}) is None


def test_extract_activity_points_skips_missing_coordinates_and_preserves_fields():
    day = {
        "activities": [
            {
                "id": "a1",
                "name": "Has coords",
                "latitude": 1.0,
                "longitude": 2.0,
                "cost": 15,
            },
            {"id": "a2", "name": "Missing coords", "cost": 5},
        ]
    }
    points, by_id = _extract_activity_points(day)
    assert len(points) == 1
    assert points[0].id == "a1"
    assert by_id["a1"]["cost"] == 15  # original dict fields preserved for mapping back


def test_optimize_routes_reorders_multi_activity_day_and_skips_single_activity_day():
    state = _make_state()
    result = optimize_routes(state)

    assert result["route_optimization"]["day_1"]["efficiency_score"] >= 1.0
    reordered_ids = {a["id"] for a in result["itinerary"]["days"][0]["activities"]}
    assert reordered_ids == {"a1", "a2", "a3"}  # same set, order may differ

    assert result["route_optimization"]["day_2"]["skipped"] is True
    assert [a["id"] for a in result["itinerary"]["days"][1]["activities"]] == ["a4"]


def test_optimize_routes_preserves_activity_fields_after_reordering():
    state = _make_state()
    result = optimize_routes(state)
    day1_activities = result["itinerary"]["days"][0]["activities"]
    costs = {a["id"]: a["cost"] for a in day1_activities}
    assert costs == {"a1": 20, "a2": 17, "a3": 0}


def test_optimize_routes_returns_none_when_hotel_has_no_coordinates():
    state = _make_state()
    state["hotels"] = [{"id": "h1", "name": "No coords hotel"}]
    result = optimize_routes(state)
    assert result["route_optimization"] is None


def test_optimize_routes_returns_none_when_no_itinerary():
    result = optimize_routes({"hotels": [{"id": "h1", "latitude": 1, "longitude": 1}]})
    assert result["route_optimization"] is None


def test_optimize_routes_never_raises_on_empty_state():
    result = optimize_routes({})
    assert result["route_optimization"] is None
