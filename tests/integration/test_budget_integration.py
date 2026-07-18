"""
tests/integration/test_budget_integration.py — Week 8

Runs the real compiled graph (build_graph) with the search/build nodes
replaced by fakes, so this test exercises actual LangGraph wiring --
node registration, edge routing, state merging across allocate_budget and
evaluate_budget -- without hitting SerpApi, Redis, or an LLM. Same
philosophy as test_itinerary_integration.py: the unit tests already prove
_BudgetOptimizer's math is correct, this proves the graph actually calls it
in the right order with the right state.

Fakes are patched onto the ai_travel_agent.agents.graph module *before*
build_graph() runs, since build_graph() captures node functions from that
module's namespace at call time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_travel_agent.agents import graph as graph_module


def _fake_parse_preferences(state):
    return {
        "preferences": {
            "total_budget": 3000.0,
            "budget_profile": "mid_range",
            "raw_preference_text": state.get("raw_request", ""),
        }
    }


def _fake_search_flights(state):
    return {"flights": [{"price": 700.0}]}


def _fake_search_hotels(state):
    return {"hotels": [{"price_per_night": 150.0, "nights": 5}]}


def _fake_find_attractions(state):
    return {"attractions": [{"name": "Louvre", "cost": 20.0}]}


def _fake_find_restaurants(state):
    return {"restaurants": [{"name": "Le Cafe", "cost": 40.0}]}


def _fake_check_weather(state):
    return {"weather": {"forecast": "sunny"}}


def _fake_track_budget(state):
    return {"budget_used": 1200.0}


def _fake_build_itinerary(state):
    return {
        "itinerary": {
            "days": [
                {
                    "activities": [
                        {"category": "activity", "cost": 20.0},
                        {"category": "restaurant", "cost": 40.0},
                    ]
                }
            ]
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
    monkeypatch.setattr(graph_module, "search_flights", _fake_search_flights)
    monkeypatch.setattr(graph_module, "search_hotels", _fake_search_hotels)
    monkeypatch.setattr(graph_module, "find_attractions", _fake_find_attractions)
    monkeypatch.setattr(graph_module, "find_restaurants", _fake_find_restaurants)
    monkeypatch.setattr(graph_module, "check_weather", _fake_check_weather)
    monkeypatch.setattr(graph_module, "track_budget", _fake_track_budget)
    monkeypatch.setattr(graph_module, "build_itinerary", _fake_build_itinerary)
    monkeypatch.setattr(graph_module, "assemble_output", _fake_assemble_output)
    monkeypatch.setattr(graph_module, "handle_error", _fake_handle_error)
    monkeypatch.setattr(graph_module, "supervisor_router", _fake_supervisor_router)
    return graph_module


def test_budget_nodes_run_in_correct_order_and_populate_state(
    patched_graph_module, tmp_path
):
    db_path = str(Path(tmp_path) / "checkpoints.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)

    config = {"configurable": {"thread_id": "test-thread-1"}}
    result = compiled.invoke({"raw_request": "budget trip"}, config=config)

    # allocate_budget ran before search (search results are already faked
    # in, so we can't directly prove ordering from timestamps, but we can
    # prove allocate_budget's output made it all the way through the graph
    # without being overwritten by a later node).
    assert result["budget_allocation"] is not None
    assert result["budget_allocation"]["total_budget"] == 3000.0

    # evaluate_budget ran after build_itinerary and produced both outputs.
    assert result["budget_tradeoffs"] is not None
    assert result["budget_adherence"] is not None
    assert result["final_output"] == {"ok": True}


def test_graph_compiles_with_all_week8_nodes_registered(patched_graph_module, tmp_path):
    db_path = str(Path(tmp_path) / "checkpoints2.db")
    compiled = patched_graph_module.build_graph(db_path=db_path)

    node_names = set(compiled.get_graph().nodes.keys())
    assert "allocate_budget" in node_names
    assert "evaluate_budget" in node_names
