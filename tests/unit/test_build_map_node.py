"""
tests/unit/test_build_map_node.py — Week 13

Tests generate_map with hand-built TravelState dicts, mocking
build_travel_map and render_thumbnail_safe at the module level so this
suite doesn't require folium or a Chromium binary to be installed -- those
are already covered directly in test_travel_map_generator.py and
test_thumbnail_renderer.py. This file is purely about the node's state
plumbing and its graceful-degradation guarantees.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_travel_agent.agents.nodes import _to_map_activities, generate_map


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
                    ]
                },
            ]
        },
    }


def test_to_map_activities_skips_missing_coordinates():
    day = {
        "activities": [
            {"id": "a1", "name": "Has coords", "latitude": 1.0, "longitude": 2.0},
            {"id": "a2", "name": "No coords"},
        ]
    }
    result = _to_map_activities(day)
    assert len(result) == 1
    assert result[0].id == "a1"


def test_generate_map_calls_builder_and_renderer_with_expected_paths():
    state = _make_state()
    with (
        patch("ai_travel_agent.agents.nodes.build_travel_map") as mock_build,
        patch("ai_travel_agent.agents.nodes.render_thumbnail_safe") as mock_thumb,
    ):
        mock_build.return_value = "outputs/maps/travel_map.html"
        mock_thumb.return_value = "outputs/maps/travel_map_thumbnail.png"

        result = generate_map(state)

        assert mock_build.called
        assert mock_thumb.called
        assert result["map_output"]["html_path"] == "outputs/maps/travel_map.html"
        assert (
            result["map_output"]["thumbnail_path"]
            == "outputs/maps/travel_map_thumbnail.png"
        )


def test_generate_map_reports_no_thumbnail_when_renderer_returns_none():
    state = _make_state()
    with (
        patch("ai_travel_agent.agents.nodes.build_travel_map") as mock_build,
        patch("ai_travel_agent.agents.nodes.render_thumbnail_safe") as mock_thumb,
    ):
        mock_build.return_value = "outputs/maps/travel_map.html"
        mock_thumb.return_value = None  # simulates Playwright unavailable

        result = generate_map(state)
        assert result["map_output"]["html_path"] == "outputs/maps/travel_map.html"
        assert result["map_output"]["thumbnail_path"] is None


def test_generate_map_returns_none_without_hotel_coordinates():
    state = _make_state()
    state["hotels"] = [{"id": "h1", "name": "No coords"}]
    result = generate_map(state)
    assert result["map_output"] is None


def test_generate_map_returns_none_without_itinerary():
    result = generate_map({"hotels": [{"id": "h1", "latitude": 1, "longitude": 1}]})
    assert result["map_output"] is None


def test_generate_map_degrades_gracefully_when_builder_raises():
    state = _make_state()
    with patch(
        "ai_travel_agent.agents.nodes.build_travel_map",
        side_effect=ImportError("no folium"),
    ):
        result = generate_map(state)
        assert result["map_output"] is None


def test_generate_map_never_raises_on_empty_state():
    result = generate_map({})
    assert result["map_output"] is None
