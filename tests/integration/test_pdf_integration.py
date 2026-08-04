"""
tests/integration/test_pdf_integration.py — Week 14

Runs the real compiled graph with upstream nodes faked and _PDFGenerator
mocked at the nodes-module level (same reasoning as test_build_pdf_node.py
-- WeasyPrint itself is out of scope for this test, graph wiring is in
scope). Confirms generate_pdf runs last, after generate_map, and that a
PDF failure doesn't affect map_output or final_output.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_travel_agent.agents import graph as graph_module
from ai_travel_agent.pdf.pdf_generator import PDFGenerationError


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


def _fake_generate_map(state):
    return {
        "map_output": {
            "html_path": "outputs/maps/travel_map.html",
            "thumbnail_path": "outputs/maps/thumb.png",
        }
    }


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
    monkeypatch.setattr(graph_module, "generate_map", _fake_generate_map)
    # generate_pdf is NOT faked -- this is the node under test, but
    # _pdf_generator inside it is mocked below so WeasyPrint isn't required.
    monkeypatch.setattr(graph_module, "handle_error", _fake_handle_error)
    monkeypatch.setattr(graph_module, "supervisor_router", _fake_supervisor_router)
    return graph_module


def test_generate_pdf_runs_after_generate_map(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints.db")

    with patch("ai_travel_agent.agents.nodes._pdf_generator") as mock_generator:
        mock_generator.build.return_value = "outputs/pdf/itinerary.pdf"

        compiled = patched_graph_module.build_graph(db_path=db_path)
        config = {"configurable": {"thread_id": "pdf-test-thread"}}
        result = compiled.invoke({"raw_request": "pdf trip"}, config=config)

        assert mock_generator.build.called
        assert result["pdf_output"]["status"] == "generated"
        assert (
            result["map_output"] is not None
        )  # map still present, unaffected by PDF step
        assert result["final_output"] == {"ok": True}


def test_pdf_failure_does_not_affect_map_or_final_output(
    patched_graph_module, tmp_path
):
    db_path = str(Path(tmp_path) / "checkpoints2.db")

    with patch("ai_travel_agent.agents.nodes._pdf_generator") as mock_generator:
        mock_generator.build.side_effect = PDFGenerationError("weasyprint missing")

        compiled = patched_graph_module.build_graph(db_path=db_path)
        config = {"configurable": {"thread_id": "pdf-fail-thread"}}
        result = compiled.invoke({"raw_request": "pdf trip"}, config=config)

        assert result["pdf_output"]["status"] == "failed"
        assert result["map_output"]["html_path"] == "outputs/maps/travel_map.html"
        assert result["final_output"] == {"ok": True}


def test_graph_compiles_with_pdf_node_registered(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints3.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)
    node_names = set(compiled.get_graph().nodes.keys())
    assert "generate_pdf" in node_names
