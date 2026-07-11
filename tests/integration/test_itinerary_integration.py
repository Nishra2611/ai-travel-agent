"""
tests/integration/test_itinerary_integration.py

Integration tests: full graph runs with build_itinerary node included.
All tool _run methods mocked — no network, no Ollama.
Verifies that the itinerary flows correctly through the graph
and lands in final_output.
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
    "end_date": "2025-12-14",
    "budget_usd": 3000.0,
    "num_travelers": 2,
    "travel_style": "moderate",
    "activity_types": ["culture"],
    "dietary_restrictions": [],
    "raw_input": "Paris 5 days $3000",
    "confidence_score": 0.9,
}
MOCK_FLIGHTS = [
    {
        "id": "f1",
        "total_price_usd": 742.0,
        "num_stops": 0,
        "cabin_class": "Economy",
        "currency": "USD",
        "segments": [
            {
                "departure_airport": "BOM",
                "arrival_airport": "CDG",
                "departure_time": "2025-12-10T10:00:00",
                "arrival_time": "2025-12-10T16:00:00",
                "airline": "Air India",
                "flight_number": "AI131",
                "duration_minutes": 480,
            }
        ],
    }
]
MOCK_HOTELS = [
    {
        "id": "h1",
        "name": "Grand Hotel Paris",
        "star_rating": 4.0,
        "price_per_night_usd": 150.0,
        "total_price_usd": 750.0,
        "check_in": "2025-12-10",
        "check_out": "2025-12-15",
        "location": {"latitude": 48.86, "longitude": 2.34},
        "address": "1 Ave, Paris",
        "amenities": [],
    }
]
MOCK_ATTRACTIONS = [
    {
        "id": f"a{i}",
        "name": f"Paris Attraction {i}",
        "category": "landmark",
        "description": "Nice place.",
        "rating": 4.5,
        "estimated_duration_hours": 2.0,
        "entry_price_usd": 15.0,
        "address": f"{i} St",
        "location": {"latitude": 48.85 + i * 0.01, "longitude": 2.35 + i * 0.01},
        "opening_hours": {"monday": "09:00-18:00"},
        "tags": [],
    }
    for i in range(12)
]
MOCK_RESTAURANTS = [
    {
        "id": "r1",
        "name": "Café de Paris",
        "rating": 4.5,
        "description": "Good food.",
        "address": "2 Food St",
    }
]
MOCK_WEATHER = [
    {
        "date": f"2025-12-{10+i:02d}",
        "temp_max": 12,
        "temp_min": 6,
        "description": "Clear",
    }
    for i in range(5)
]
MOCK_BUDGET = {"total_budget": 3000.0, "total_spent": 1492.0, "remaining": 1508.0}


def _all_patches(osrm_return: int = 20):
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
        "osrm": patch(
            "ai_travel_agent.tools.itinerary_builder.get_travel_time_safe",
            return_value=osrm_return,
        ),
    }


@pytest.fixture
def graph(tmp_path):
    from ai_travel_agent.agents.graph import build_graph

    return build_graph(db_path=str(tmp_path / "itin_test.db"))


@pytest.fixture
def session_id() -> str:
    return f"itin-{uuid.uuid4().hex[:8]}"


def run_graph(graph, session_id: str, message: str = "Paris 5 days $3000"):
    p = _all_patches()
    with (
        p["parser"],
        p["flights"],
        p["hotels"],
        p["attractions"],
        p["restaurants"],
        p["weather"],
        p["budget"],
        p["ollama"],
        p["osrm"],
    ):
        return graph.invoke(
            {
                "raw_input": message,
                "status": "parse",
                "messages": [{"role": "user", "content": message}],
            },
            config={"configurable": {"thread_id": session_id}},
        )


class TestGraphHasBuildItineraryNode:
    def test_build_itinerary_node_registered(self, tmp_path) -> None:
        from ai_travel_agent.agents.graph import build_graph

        g = build_graph(db_path=str(tmp_path / "node_check.db"))
        assert "build_itinerary" in set(g.nodes)

    def test_nine_nodes_total(self, tmp_path) -> None:
        from ai_travel_agent.agents.graph import build_graph

        g = build_graph(db_path=str(tmp_path / "count.db"))
        # parse, search×5, budget, build, assemble, error = 10
        assert len(g.nodes) >= 9


class TestItineraryInFinalOutput:
    def test_itinerary_present_in_output(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        assert state["final_output"]["itinerary"] is not None

    def test_itinerary_has_correct_destination(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        itin = state["final_output"]["itinerary"]
        assert itin["destination"] == "Paris"

    def test_itinerary_has_5_days(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        itin = state["final_output"]["itinerary"]
        assert len(itin["days"]) == 5

    def test_itinerary_activities_have_travel_times(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        itin = state["final_output"]["itinerary"]
        times = [
            a.get("travel_time_to_next_minutes")
            for day in itin["days"]
            for a in day["activities"][:-1]
        ]
        # with our mock, all should be 20
        assert all(t == 20 for t in times if t is not None)

    def test_graph_status_done(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        assert state["status"] == "done"

    def test_tools_succeeded_7(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        assert state["final_output"]["tools_succeeded"] == 7

    def test_itinerary_error_absent_on_success(self, graph, session_id) -> None:
        state = run_graph(graph, session_id)
        assert "itinerary" not in state["final_output"]["errors"]


class TestItineraryBuilderFailureDoesNotCrashGraph:
    def test_graph_still_finishes_when_builder_fails(self, graph, session_id) -> None:
        p = _all_patches()
        p["osrm"] = patch(
            "ai_travel_agent.tools.itinerary_builder.get_travel_time_safe",
            return_value=20,
        )
        # make the builder itself fail
        builder_fail = patch(
            "ai_travel_agent.agents.nodes._itinerary_tool._run",
            side_effect=Exception("builder crashed"),
        )
        with (
            p["parser"],
            p["flights"],
            p["hotels"],
            p["attractions"],
            p["restaurants"],
            p["weather"],
            p["budget"],
            p["ollama"],
            p["osrm"],
            builder_fail,
        ):
            state = graph.invoke(
                {
                    "raw_input": "Paris 5 days",
                    "status": "parse",
                    "messages": [{"role": "user", "content": "Paris 5 days"}],
                },
                config={"configurable": {"thread_id": session_id}},
            )

        assert state["status"] == "done"
        assert state["final_output"]["itinerary"] is None
        assert "itinerary" in state["final_output"]["errors"]
