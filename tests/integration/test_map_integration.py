"""
tests/integration/test_map_integration.py — Week 13

Runs the real compiled graph with all upstream nodes faked and
build_travel_map/render_thumbnail_safe mocked at the nodes-module level
(same reasoning as test_build_map_node.py -- this test is about graph
wiring, not about folium/Playwright, which are covered elsewhere).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_travel_agent.agents import graph as graph_module


def _fake_parse_preferences(state):
    return {
        "preferences": {
            "destination_city": "Paris",
            "total_budget": 3000.0,
            "budget_profile": "mid_range",
        }
    }


def _fake_allocate_budget(state):
    return {
        "budget_allocation": {
            "total_budget": 3000.0,
            "profile": "mid_range",
            "allocations": {},
            "search_hints": {},
        }
    }


def _fake_search_flights(state):
    return {"flights": [{"price": 700.0}]}


def _fake_search_hotels(state):
    return {
        "hotels": [
            {
                "id": "h1",
                "name": "Hotel A",
                "price_per_night": 150.0,
                "nights": 5,
                "latitude": 48.8629,
                "longitude": 2.3355,
            }
        ]
    }


def _fake_find_attractions(state):
    return {
        "attractions": [
            {
                "id": "a1",
                "name": "Eiffel Tower",
                "latitude": 48.8584,
                "longitude": 2.2945,
                "cost": 20.0,
            }
        ]
    }


def _fake_find_restaurants(state):
    return {"restaurants": []}


def _fake_check_weather(state):
    return {"weather": {"forecast": "sunny"}}


def _fake_track_budget(state):
    return {"budget_used": 1200.0}


def _fake_build_geo_clusters(state):
    return {"geo_clusters": {"city": "Paris", "clusters": [], "noise_point_ids": []}}


def _fake_build_itinerary(state):
    return {
        "itinerary": {
            "days": [
                {
                    "activities": [
                        {
                            "id": "a1",
                            "name": "Eiffel Tower",
                            "latitude": 48.8584,
                            "longitude": 2.2945,
                            "cost": 20.0,
                        },
                    ]
                }
            ]
        }
    }


def _fake_optimize_routes(state):
    return {"route_optimization": {"day_1": {"efficiency_score": 1.0}}}


def _fake_evaluate_budget(state):
    return {
        "budget_tradeoffs": {"status": "on_budget", "suggestions": []},
        "budget_adherence": {"overall_score": 90.0},
    }


def _fake_assemble_output(state):
    return {"final_output": {"ok": True}}


def _fake_handle_error(state):
    return {"error": state.get("error", "unknown error")}


def _fake_supervisor_router(state):
    if state.get("error"):
        return "handle_error"
    return "parse_preferences" if "preferences" not in state else "search_flights"


@pytest.fixture
def patched_graph_module(monkeypatch):
    monkeypatch.setattr(graph_module, "parse_preferences", _fake_parse_preferences)
    monkeypatch.setattr(graph_module, "allocate_budget", _fake_allocate_budget)
    monkeypatch.setattr(graph_module, "search_flights", _fake_search_flights)
    monkeypatch.setattr(graph_module, "search_hotels", _fake_search_hotels)
    monkeypatch.setattr(graph_module, "find_attractions", _fake_find_attractions)
    monkeypatch.setattr(graph_module, "find_restaurants", _fake_find_restaurants)
    monkeypatch.setattr(graph_module, "check_weather", _fake_check_weather)
    monkeypatch.setattr(graph_module, "track_budget", _fake_track_budget)
    monkeypatch.setattr(graph_module, "build_geo_clusters", _fake_build_geo_clusters)
    monkeypatch.setattr(graph_module, "build_itinerary", _fake_build_itinerary)
    monkeypatch.setattr(graph_module, "optimize_routes", _fake_optimize_routes)
    monkeypatch.setattr(graph_module, "evaluate_budget", _fake_evaluate_budget)
    monkeypatch.setattr(graph_module, "assemble_output", _fake_assemble_output)
    # generate_map is NOT faked -- this is the node under test, but its
    # internals (build_travel_map/render_thumbnail_safe) are mocked below
    # so this test doesn't need folium/Playwright installed.
    monkeypatch.setattr(graph_module, "handle_error", _fake_handle_error)
    monkeypatch.setattr(graph_module, "supervisor_router", _fake_supervisor_router)
    return graph_module


def test_generate_map_runs_after_assemble_output(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints.db")

    with (
        patch("ai_travel_agent.agents.nodes.build_travel_map") as mock_build,
        patch("ai_travel_agent.agents.nodes.render_thumbnail_safe") as mock_thumb,
    ):
        mock_build.return_value = "outputs/maps/travel_map.html"
        mock_thumb.return_value = "outputs/maps/travel_map_thumbnail.png"

        compiled = patched_graph_module.build_graph(db_path=db_path)
        config = {"configurable": {"thread_id": "map-test-thread"}}
        result = compiled.invoke({"raw_request": "map trip"}, config=config)

        assert mock_build.called
        assert result["map_output"] is not None
        assert result["map_output"]["html_path"] == "outputs/maps/travel_map.html"
        assert result["final_output"] == {"ok": True}


def test_graph_compiles_with_map_node_registered(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints2.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)
    node_names = set(compiled.get_graph().nodes.keys())
    assert "generate_map" in node_names
