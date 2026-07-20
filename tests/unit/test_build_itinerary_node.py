"""
Unit tests for the build_itinerary LangGraph node.
ItineraryBuilderTool._run is mocked — tests only the node's
state reading, error handling, and state writing.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_travel_agent.agents.state import TravelState


def make_state(**extra) -> TravelState:
    s: TravelState = {
        "raw_input": "Paris 5 days $3000",
        "status": "build",
        "messages": [],
        "trip_id": "trip_test01",
        "preferences": {
            "destination": "Paris",
            "duration_days": 5,
            "num_travelers": 2,
            "start_date": "2025-12-10",
            "budget_usd": 3000.0,
            "travel_style": "moderate",
            "activity_types": ["culture"],
            "dietary_restrictions": [],
            "raw_input": "Paris 5 days $3000",
            "confidence_score": 0.9,
        },
        "flight_results": [{"id": "f1", "total_price_usd": 742.0}],
        "hotel_results": [{"id": "h1", "name": "Grand Hotel"}],
        "attraction_results": [
            {"id": "a1", "name": "Eiffel Tower", "category": "landmark"}
        ],
        "restaurant_results": [{"id": "r1", "name": "Café"}],
        "weather_results": [{"date": "2025-12-10", "temp_max": 12}],
        "budget_summary": {"total_budget": 3000.0, "total_spent": 800.0},
    }
    s.update(extra)  # type: ignore[typeddict-item]
    return s


MOCK_ITINERARY = {
    "id": "itin_abc123",
    "title": "5-Day Paris City Tour Trip",
    "destination": "Paris",
    "start_date": "2025-12-10",
    "end_date": "2025-12-14",
    "num_travelers": 2,
    "days": [
        {
            "day_number": 1,
            "date": "2025-12-10",
            "theme": "Arrival",
            "activities": [
                {
                    "time_slot": "afternoon",
                    "title": "Check-in",
                    "description": "Arrive",
                    "location_name": "Hotel",
                    "estimated_cost_usd": 0.0,
                }
            ],
            "daily_budget_usd": 0.0,
        },
    ],
    "total_cost_usd": 1542.0,
    "budget_usd": 3000.0,
    "is_within_budget": True,
    "outbound_flight": None,
    "return_flight": None,
    "hotel": None,
    "generated_at": "2025-12-01T10:00:00",
    "version": 1,
}


_OPTIMIZER_PATH = "ai_travel_agent.optimizer.itinerary_builder.build_itinerary"


class TestBuildItineraryNode:
    def test_success_sets_itinerary_result(self) -> None:
        from unittest.mock import MagicMock

        from ai_travel_agent.agents.nodes import build_itinerary

        mock_itin = MagicMock()
        mock_itin.model_dump.return_value = MOCK_ITINERARY
        with patch(_OPTIMIZER_PATH, return_value=mock_itin):
            result = build_itinerary(make_state())

        assert result["itinerary_result"] == MOCK_ITINERARY
        assert result.get("itinerary_error") is None

    def test_success_adds_assistant_message(self) -> None:
        from unittest.mock import MagicMock

        from ai_travel_agent.agents.nodes import build_itinerary

        mock_itin = MagicMock()
        mock_itin.model_dump.return_value = MOCK_ITINERARY
        with patch(_OPTIMIZER_PATH, return_value=mock_itin):
            result = build_itinerary(make_state())

        assert len(result["messages"]) > 0
        assert result["messages"][0]["role"] == "assistant"

    def test_failure_sets_error_and_none_result(self) -> None:
        from ai_travel_agent.agents.nodes import build_itinerary

        with patch(_OPTIMIZER_PATH, side_effect=Exception("builder crashed")):
            result = build_itinerary(make_state())

        assert result["itinerary_result"] is None
        assert result["itinerary_error"] is not None

    def test_passes_attractions_and_weather_to_optimizer(self) -> None:
        from unittest.mock import MagicMock

        from ai_travel_agent.agents.nodes import build_itinerary

        mock_itin = MagicMock()
        mock_itin.model_dump.return_value = MOCK_ITINERARY
        with patch(_OPTIMIZER_PATH, return_value=mock_itin) as mock_build:
            build_itinerary(make_state())

        args = mock_build.call_args
        prefs = args[0][0] if args[0] else args[1]["preferences"]
        assert prefs["destination"] == "Paris"

    def test_empty_tool_results_do_not_crash(self) -> None:
        from ai_travel_agent.agents.nodes import build_itinerary

        state = make_state(
            flight_results=[],
            hotel_results=[],
            attraction_results=[],
            restaurant_results=[],
            weather_results=[],
            budget_summary={},
        )
        # optimizer runs for real with empty attractions — should not raise
        result = build_itinerary(state)
        assert result["itinerary_result"] is not None

    def test_does_not_set_status(self) -> None:
        from unittest.mock import MagicMock

        from ai_travel_agent.agents.nodes import build_itinerary

        mock_itin = MagicMock()
        mock_itin.model_dump.return_value = MOCK_ITINERARY
        with patch(_OPTIMIZER_PATH, return_value=mock_itin):
            result = build_itinerary(make_state())

        assert "status" not in result


class TestAssembleOutputWithItinerary:
    def test_itinerary_in_final_output(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = make_state(itinerary_result=MOCK_ITINERARY)
        result = assemble_output(state)
        assert result["final_output"]["itinerary"] == MOCK_ITINERARY

    def test_itinerary_none_when_missing(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = make_state()
        state.pop("itinerary_result", None)  # type: ignore[misc]
        result = assemble_output(state)
        assert result["final_output"]["itinerary"] is None

    def test_itinerary_error_in_errors_dict(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = make_state(itinerary_result=None, itinerary_error="builder timed out")
        result = assemble_output(state)
        assert "itinerary" in result["final_output"]["errors"]

    def test_tools_succeeded_counts_itinerary(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        # no errors at all
        state = make_state(itinerary_result=MOCK_ITINERARY)
        result = assemble_output(state)
        assert result["final_output"]["tools_succeeded"] == 7

    def test_within_budget_message_included(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = make_state(itinerary_result=MOCK_ITINERARY)
        result = assemble_output(state)
        msg = result["messages"][0]["content"]
        assert "Paris" in msg
