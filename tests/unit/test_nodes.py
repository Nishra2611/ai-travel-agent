"""
Unit tests for agent nodes.
All tool calls are mocked — no network, no Ollama, no Redis required.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_travel_agent.agents.state import TravelState


def base_state(**extra) -> TravelState:
    s: TravelState = {
        "raw_input": "Paris 5 days $3000",
        "status": "parse",
        "messages": [],
        "trip_id": "trip_test01",
    }
    s.update(extra)  # type: ignore[typeddict-item]
    return s


def prefs_state() -> TravelState:
    return base_state(
        status="search",
        preferences={
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
            "confidence_score": 0.95,
        },
    )


# ── parse_preferences ─────────────────────────────────────────────────────────


class TestParsePreferences:
    def test_success_sets_preferences_and_status(self) -> None:
        from ai_travel_agent.agents.nodes import parse_preferences

        mock_result = {
            "destination": "Paris",
            "duration_days": 5,
            "budget_usd": 3000.0,
            "confidence_score": 0.9,
            "raw_input": "Paris 5 days $3000",
        }
        with patch(
            "ai_travel_agent.agents.nodes.parse_preferences",
            wraps=parse_preferences,
        ):
            with patch(
                "ai_travel_agent.parsers.preference_parser.PreferenceParserTool._run",
                return_value=mock_result,
            ):
                result = parse_preferences(base_state())

        assert result["preferences"]["destination"] == "Paris"
        assert result["status"] == "search"
        assert "trip_id" in result

    def test_failure_sets_error_status(self) -> None:
        from ai_travel_agent.agents.nodes import parse_preferences

        with patch(
            "ai_travel_agent.parsers.preference_parser.PreferenceParserTool._run",
            side_effect=Exception("Ollama offline"),
        ):
            result = parse_preferences(base_state())

        assert result["status"] == "error"
        assert result["error_message"] is not None

    def test_message_added_on_success(self) -> None:
        from ai_travel_agent.agents.nodes import parse_preferences

        mock_result = {
            "destination": "Tokyo",
            "duration_days": 7,
            "confidence_score": 0.85,
            "raw_input": "Tokyo 7 days",
        }
        with patch(
            "ai_travel_agent.parsers.preference_parser.PreferenceParserTool._run",
            return_value=mock_result,
        ):
            result = parse_preferences(base_state(raw_input="Tokyo 7 days"))

        assert len(result["messages"]) > 0
        assert result["messages"][0]["role"] == "assistant"


# ── search_flights ────────────────────────────────────────────────────────────


class TestSearchFlights:
    def test_success_sets_flight_results(self) -> None:
        from ai_travel_agent.agents.nodes import search_flights

        mock_flights = [{"id": "f1", "total_price_usd": 742, "num_stops": 0}]
        with patch(
            "ai_travel_agent.agents.nodes._flight_tool._run",
            return_value=mock_flights,
        ):
            result = search_flights(prefs_state())

        assert result["flight_results"] == mock_flights
        assert result["flight_error"] is None

    def test_failure_sets_empty_list_and_error(self) -> None:
        from ai_travel_agent.agents.nodes import search_flights

        with patch(
            "ai_travel_agent.agents.nodes._flight_tool._run",
            side_effect=Exception("API down"),
        ):
            result = search_flights(prefs_state())

        assert result["flight_results"] == []
        assert result["flight_error"] is not None

    def test_empty_results_sets_error(self) -> None:
        from ai_travel_agent.agents.nodes import search_flights

        with patch("ai_travel_agent.agents.nodes._flight_tool._run", return_value=[]):
            result = search_flights(prefs_state())

        assert result["flight_results"] == []
        assert result["flight_error"] is not None


# ── search_hotels ─────────────────────────────────────────────────────────────


class TestSearchHotels:
    def test_success(self) -> None:
        from ai_travel_agent.agents.nodes import search_hotels

        mock = [{"id": "h1", "name": "Grand Hotel", "total_price_usd": 750}]
        with patch("ai_travel_agent.agents.nodes._hotel_tool._run", return_value=mock):
            result = search_hotels(prefs_state())

        assert result["hotel_results"] == mock
        assert result["hotel_error"] is None

    def test_failure(self) -> None:
        from ai_travel_agent.agents.nodes import search_hotels

        with patch(
            "ai_travel_agent.agents.nodes._hotel_tool._run",
            side_effect=Exception("timeout"),
        ):
            result = search_hotels(prefs_state())

        assert result["hotel_results"] == []
        assert result["hotel_error"] is not None


# ── find_attractions ──────────────────────────────────────────────────────────


class TestFindAttractions:
    def test_success(self) -> None:
        from ai_travel_agent.agents.nodes import find_attractions

        mock = [{"name": "Eiffel Tower", "rating": 4.8}]
        with patch(
            "ai_travel_agent.agents.nodes._attraction_tool._run", return_value=mock
        ):
            result = find_attractions(prefs_state())

        assert result["attraction_results"] == mock
        assert result["attraction_error"] is None

    def test_failure(self) -> None:
        from ai_travel_agent.agents.nodes import find_attractions

        with patch(
            "ai_travel_agent.agents.nodes._attraction_tool._run",
            side_effect=Exception("overpass down"),
        ):
            result = find_attractions(prefs_state())

        assert result["attraction_results"] == []
        assert result["attraction_error"] is not None


# ── find_restaurants ──────────────────────────────────────────────────────────


class TestFindRestaurants:
    def test_success(self) -> None:
        from ai_travel_agent.agents.nodes import find_restaurants

        mock = [{"name": "Café de Flore", "rating": 4.5}]
        with patch(
            "ai_travel_agent.agents.nodes._restaurant_tool._run", return_value=mock
        ):
            result = find_restaurants(prefs_state())

        assert result["restaurant_results"] == mock
        assert result["restaurant_error"] is None

    def test_dietary_restriction_passed_as_cuisine(self) -> None:
        from ai_travel_agent.agents.nodes import find_restaurants

        state = prefs_state()
        state["preferences"]["dietary_restrictions"] = ["vegetarian"]  # type: ignore[index]
        with patch(
            "ai_travel_agent.agents.nodes._restaurant_tool._run", return_value=[]
        ) as mock_run:
            find_restaurants(state)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cuisine") == "vegetarian"


# ── check_weather ─────────────────────────────────────────────────────────────


class TestCheckWeather:
    def test_success(self) -> None:
        from ai_travel_agent.agents.nodes import check_weather

        mock = [{"date": "2025-12-10", "temp_max": 12, "description": "Clear"}]
        with patch(
            "ai_travel_agent.agents.nodes._weather_tool._run", return_value=mock
        ):
            result = check_weather(prefs_state())

        assert result["weather_results"] == mock
        assert result["weather_error"] is None

    def test_days_capped_at_8(self) -> None:
        from ai_travel_agent.agents.nodes import check_weather

        state = prefs_state()
        state["preferences"]["duration_days"] = 30  # type: ignore[index]
        with patch(
            "ai_travel_agent.agents.nodes._weather_tool._run", return_value=[]
        ) as mock_run:
            check_weather(state)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["days"] <= 8


# ── assemble_output ───────────────────────────────────────────────────────────


class TestAssembleOutput:
    def test_assembles_all_fields(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = prefs_state()
        state.update(
            {  # type: ignore[typeddict-item]
                "flight_results": [{"id": "f1"}],
                "hotel_results": [{"id": "h1"}],
                "attraction_results": [{"name": "Eiffel"}],
                "restaurant_results": [{"name": "Cafe"}],
                "weather_results": [{"date": "2025-12-10"}],
                "budget_summary": {"total_budget": 3000, "total_spent": 800},
            }
        )
        result = assemble_output(state)

        out = result["final_output"]
        assert out["destination"] == "Paris"
        assert len(out["flights"]) == 1
        assert len(out["hotels"]) == 1
        assert len(out["attractions"]) == 1
        assert len(out["restaurants"]) == 1
        assert len(out["weather"]) == 1
        assert result["status"] == "done"

    def test_collects_errors(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        state = prefs_state()
        state["flight_error"] = "API timeout"  # type: ignore[typeddict-unknown-key]
        state["hotel_error"] = "No results"  # type: ignore[typeddict-unknown-key]
        result = assemble_output(state)

        errors = result["final_output"]["errors"]
        assert "flights" in errors
        assert "hotels" in errors
        assert result["final_output"]["tools_failed"] == 2

    def test_status_set_to_done(self) -> None:
        from ai_travel_agent.agents.nodes import assemble_output

        result = assemble_output(prefs_state())
        assert result["status"] == "done"


# ── handle_error ──────────────────────────────────────────────────────────────


class TestHandleError:
    def test_returns_done_status(self) -> None:
        from ai_travel_agent.agents.nodes import handle_error

        state = base_state(status="error", error_message="Something broke")
        result = handle_error(state)

        assert result["status"] == "done"
        assert result["final_output"]["error"] == "Something broke"
        assert result["final_output"]["success"] is False

    def test_handles_missing_error_message(self) -> None:
        from ai_travel_agent.agents.nodes import handle_error

        state = base_state(status="error")
        result = handle_error(state)

        assert result["status"] == "done"
        assert "error" in result["final_output"]
