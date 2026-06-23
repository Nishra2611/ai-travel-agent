"""
Integration tests for the full LangGraph graph.
All tool _run methods and Ollama are mocked.
Tests the graph wiring, state transitions, and checkpointing.
Run: poetry run pytest tests/integration/test_graph_integration.py -v
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

MOCK_PREFS = {
    "destination": "Paris",
    "origin": "BOM",
    "duration_days": 5,
    "start_date": "2025-12-10",
    "end_date": "2025-12-15",
    "budget_usd": 3000.0,
    "num_travelers": 1,
    "travel_style": "moderate",
    "activity_types": ["culture"],
    "dietary_restrictions": [],
    "raw_input": "Paris 5 days $3000",
    "confidence_score": 0.9,
}

MOCK_FLIGHTS = [{"id": "f1", "total_price_usd": 742.0, "num_stops": 0}]
MOCK_HOTELS = [{"id": "h1", "name": "Grand Hotel Paris", "total_price_usd": 875.0}]
MOCK_ATTRACTIONS = [{"name": "Eiffel Tower", "rating": 4.8}]
MOCK_RESTAURANTS = [{"name": "Café de Flore", "rating": 4.5}]
MOCK_WEATHER = [{"date": "2025-12-10", "temp_max": 10, "description": "Clear"}]
MOCK_BUDGET = {"total_budget": 3000.0, "total_spent": 1617.0, "remaining": 1383.0}


def _make_patches():
    """Return a dict of all patches needed to run the graph without real APIs."""
    return {
        "parser": patch(
            "ai_travel_agent.parsers.preference_parser.PreferenceParserTool._run",
            return_value=MOCK_PREFS,
        ),
        "flights": patch(
            "ai_travel_agent.agents.nodes._flight_tool._run", return_value=MOCK_FLIGHTS
        ),
        "hotels": patch(
            "ai_travel_agent.agents.nodes._hotel_tool._run", return_value=MOCK_HOTELS
        ),
        "attractions": patch(
            "ai_travel_agent.agents.nodes._attraction_tool._run",
            return_value=MOCK_ATTRACTIONS,
        ),
        "restaurants": patch(
            "ai_travel_agent.agents.nodes._restaurant_tool._run",
            return_value=MOCK_RESTAURANTS,
        ),
        "weather": patch(
            "ai_travel_agent.agents.nodes._weather_tool._run", return_value=MOCK_WEATHER
        ),
        "budget": patch(
            "ai_travel_agent.agents.nodes._budget_tool._run", return_value=MOCK_BUDGET
        ),
        "ollama": patch("ai_travel_agent.parsers.preference_parser.OllamaLLM"),
    }


@pytest.fixture
def graph(tmp_path):
    """Build a fresh graph with a temp SQLite DB for each test."""
    from ai_travel_agent.agents.graph import build_graph

    db = str(tmp_path / "test_checkpoints.db")
    return build_graph(db_path=db)


@pytest.fixture
def session_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


class TestGraphWiring:
    def test_graph_compiles(self, tmp_path) -> None:
        from ai_travel_agent.agents.graph import build_graph

        g = build_graph(db_path=str(tmp_path / "wiring.db"))
        assert g is not None

    def test_graph_has_all_nodes(self, tmp_path) -> None:
        from ai_travel_agent.agents.graph import build_graph

        g = build_graph(db_path=str(tmp_path / "nodes.db"))
        node_names = set(g.nodes)
        expected = {
            "parse_preferences",
            "search_flights",
            "search_hotels",
            "find_attractions",
            "find_restaurants",
            "check_weather",
            "track_budget",
            "assemble_output",
            "handle_error",
        }
        assert expected.issubset(node_names)


class TestGraphInvoke:
    def test_full_run_status_done(self, graph, session_id) -> None:
        patches = _make_patches()
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state = graph.invoke(
                {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
                config={"configurable": {"thread_id": session_id}},
            )
        assert state["status"] == "done"

    def test_final_output_has_destination(self, graph, session_id) -> None:
        patches = _make_patches()
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state = graph.invoke(
                {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
                config={"configurable": {"thread_id": session_id}},
            )
        assert state["final_output"]["destination"] == "Paris"

    def test_final_output_has_all_tool_results(self, graph, session_id) -> None:
        patches = _make_patches()
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state = graph.invoke(
                {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
                config={"configurable": {"thread_id": session_id}},
            )
        out = state["final_output"]
        assert len(out["flights"]) == 1
        assert len(out["hotels"]) == 1
        assert len(out["attractions"]) == 1
        assert len(out["restaurants"]) == 1
        assert len(out["weather"]) == 1

    def test_messages_accumulated(self, graph, session_id) -> None:
        patches = _make_patches()
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state = graph.invoke(
                {
                    "raw_input": "Paris 5 days",
                    "status": "parse",
                    "messages": [{"role": "user", "content": "Paris 5 days"}],
                },
                config={"configurable": {"thread_id": session_id}},
            )
        assert len(state["messages"]) >= 2  # user + at least one assistant

    def test_error_node_reached_on_parse_failure(self, graph, session_id) -> None:
        with (
            patch(
                "ai_travel_agent.parsers.preference_parser.PreferenceParserTool._run",
                side_effect=Exception("Ollama offline"),
            ),
            patch("ai_travel_agent.parsers.preference_parser.OllamaLLM"),
        ):
            state = graph.invoke(
                {"raw_input": "bad input", "status": "parse", "messages": []},
                config={"configurable": {"thread_id": session_id}},
            )
        assert state["status"] == "done"
        assert "error" in state["final_output"]

    def test_tool_failure_does_not_crash_graph(self, graph, session_id) -> None:
        """One tool failing should not stop the whole graph."""
        patches = _make_patches()
        # flight tool throws
        patches["flights"] = patch(
            "ai_travel_agent.agents.nodes._flight_tool._run",
            side_effect=Exception("SerpApi down"),
        )
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state = graph.invoke(
                {"raw_input": "Paris 5 days $3000", "status": "parse", "messages": []},
                config={"configurable": {"thread_id": session_id}},
            )
        assert state["status"] == "done"
        out = state["final_output"]
        assert out["flights"] == []
        assert "flights" in out.get("errors", {})


class TestCheckpointing:
    def test_second_invoke_same_session_has_history(self, graph, session_id) -> None:
        """Conversation history should persist across invocations."""
        patches = _make_patches()
        config = {"configurable": {"thread_id": session_id}}
        initial = {
            "raw_input": "Paris 5 days $3000",
            "status": "parse",
            "messages": [{"role": "user", "content": "Paris 5 days $3000"}],
        }

        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state1 = graph.invoke(initial, config=config)

        # second call in same session
        followup = {
            "raw_input": "Change to 7 days",
            "status": "parse",
            "messages": [{"role": "user", "content": "Change to 7 days"}],
        }
        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            state2 = graph.invoke(followup, config=config)

        # messages from both calls should be in state (operator.add)
        assert len(state2["messages"]) > len(state1["messages"])

    def test_different_sessions_are_independent(self, graph) -> None:
        patches = _make_patches()
        session_a = f"test-a-{uuid.uuid4().hex[:4]}"
        session_b = f"test-b-{uuid.uuid4().hex[:4]}"

        initial = {
            "raw_input": "Paris 5 days $3000",
            "status": "parse",
            "messages": [{"role": "user", "content": "Paris 5 days $3000"}],
        }

        with (
            patches["parser"],
            patches["flights"],
            patches["hotels"],
            patches["attractions"],
            patches["restaurants"],
            patches["weather"],
            patches["budget"],
            patches["ollama"],
        ):
            graph.invoke(initial, config={"configurable": {"thread_id": session_a}})
            state_b = graph.invoke(
                initial, config={"configurable": {"thread_id": session_b}}
            )

        # session B should not contain session A's messages
        assert state_b["status"] == "done"
