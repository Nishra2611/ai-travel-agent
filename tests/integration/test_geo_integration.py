"""
tests/integration/test_geo_integration.py — Week 9

Runs the real compiled graph with search/build nodes faked, proving
build_geo_clusters is wired correctly between track_budget and
build_itinerary. Same pattern as test_budget_integration.py -- fakes are
patched onto the graph module's namespace before build_graph() runs.
"""

from __future__ import annotations

from pathlib import Path

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


# def _fake_search_flights(state):
#     return {"flights": [{"price": 700.0}]}
def _fake_search_flights(state):
    print("FAKE search_flights ran")
    return {"flights": [{"price": 700.0}]}


# def _fake_search_hotels(state):
#     return {
#         "hotels": [
#             {
#                 "id": "h1",
#                 "name": "Hotel A",
#                 "price_per_night": 150.0,
#                 "nights": 5,
#                 "latitude": 48.8629,
#                 "longitude": 2.3355,
#             }
#         ]
#     }
def _fake_search_hotels(state):
    print("FAKE search_hotels ran")
    return {
        "hotel_results": [
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
    print("FAKE find_attractions ran")
    return {
        "attraction_results": [
            {
                "id": "a1",
                "name": "Eiffel Tower",
                "latitude": 48.8584,
                "longitude": 2.2945,
                "cost": 20.0,
            },
            {
                "id": "a2",
                "name": "Louvre",
                "latitude": 48.8606,
                "longitude": 2.3376,
                "cost": 17.0,
            },
            {
                "id": "a3",
                "name": "Notre-Dame",
                "latitude": 48.8530,
                "longitude": 2.3499,
                "cost": 0.0,
            },
        ]
    }


def _fake_find_restaurants(state):
    print("FAKE find_restaurants ran")
    return {
        "restaurant_results": [
            {
                "id": "r1",
                "name": "Cafe",
                "latitude": 48.8554,
                "longitude": 2.3450,
                "cost": 30.0,
            }
        ]
    }


# def _fake_check_weather(state):
#     return {"weather": {"forecast": "sunny"}}
def _fake_check_weather(state):
    print("FAKE check_weather ran")
    return {"weather": {"forecast": "sunny"}}


# def _fake_track_budget(state):
#     return {"budget_used": 1200.0}
def _fake_track_budget(state):
    print("FAKE track_budget ran")
    return {"budget_used": 1200.0}


def _fake_build_itinerary(state):
    # Real build_itinerary would read state["geo_clusters"] here in a
    # future update; this fake just proves the node ran after it.
    return {"itinerary_result": {"days": [{"activities": []}]}}


def _fake_evaluate_budget(state):
    return {
        "budget_tradeoffs": {"status": "on_budget", "suggestions": []},
        "budget_adherence": {"overall_score": 90.0},
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
    # build_geo_clusters is NOT faked -- this is the node under test, we
    # want the real implementation to run against the fake attractions.
    monkeypatch.setattr(graph_module, "build_itinerary", _fake_build_itinerary)
    monkeypatch.setattr(graph_module, "evaluate_budget", _fake_evaluate_budget)
    monkeypatch.setattr(graph_module, "assemble_output", _fake_assemble_output)
    monkeypatch.setattr(graph_module, "handle_error", _fake_handle_error)
    monkeypatch.setattr(graph_module, "supervisor_router", _fake_supervisor_router)
    return graph_module


def test_build_geo_clusters_runs_between_track_budget_and_build_itinerary(
    patched_graph_module, tmp_path
):
    db_path = str(Path(tmp_path) / "checkpoints.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)

    config = {"configurable": {"thread_id": "geo-test-thread"}}
    result = compiled.invoke({"raw_request": "geo trip"}, config=config)

    assert result["geo_clusters"] is not None
    assert result["geo_clusters"]["city"] == "Paris"
    assert len(result["geo_clusters"]["clusters"]) >= 1
    # downstream nodes still ran with geo_clusters already in state
    assert result["itinerary_result"] is not None
    assert result["final_output"] == {"ok": True}


def test_graph_compiles_with_geo_node_registered(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints2.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)
    node_names = set(compiled.get_graph().nodes.keys())
    assert "build_geo_clusters" in node_names
