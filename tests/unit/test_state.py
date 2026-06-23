"""Unit tests for TravelState structure."""

from ai_travel_agent.agents.state import TravelState


def test_state_is_typeddict() -> None:
    from typing import get_type_hints

    hints = get_type_hints(TravelState)
    assert "raw_input" in hints
    assert "preferences" in hints
    assert "status" in hints
    assert "final_output" in hints


def test_state_accepts_partial_dict() -> None:
    # total=False means no key is required
    s: TravelState = {"raw_input": "Paris 5 days", "status": "parse"}
    assert s["raw_input"] == "Paris 5 days"
    assert s["status"] == "parse"


def test_state_all_tool_result_keys() -> None:
    from typing import get_type_hints

    hints = get_type_hints(TravelState)
    for key in (
        "flight_results",
        "hotel_results",
        "attraction_results",
        "restaurant_results",
        "weather_results",
        "budget_summary",
    ):
        assert key in hints, f"Missing key: {key}"


def test_state_all_error_keys() -> None:
    from typing import get_type_hints

    hints = get_type_hints(TravelState)
    for key in (
        "flight_error",
        "hotel_error",
        "attraction_error",
        "restaurant_error",
        "weather_error",
        "budget_error",
    ):
        assert key in hints, f"Missing error key: {key}"


def test_state_messages_annotated() -> None:
    import typing

    hints = typing.get_type_hints(TravelState, include_extras=True)
    # messages should be Annotated (has operator.add reducer)
    msg_hint = hints.get("messages")
    assert msg_hint is not None
    # Annotated types have __metadata__
    assert hasattr(msg_hint, "__metadata__"), "messages must be Annotated with reducer"
