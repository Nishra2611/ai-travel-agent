"""Unit tests for FlightSearchTool."""

from datetime import datetime
from unittest.mock import patch

import pytest

from ai_travel_agent.tools.flight_search import FlightSearchTool


@pytest.fixture
def tool() -> FlightSearchTool:
    return FlightSearchTool(use_mock_on_failure=True)


@pytest.fixture
def strict_tool() -> FlightSearchTool:
    return FlightSearchTool(use_mock_on_failure=False)


def _mock_fetch(tool: FlightSearchTool, origin: str = "BOM", dest: str = "CDG"):
    return patch.object(
        tool,
        "_fetch",
        return_value=tool._mock_data(
            origin=origin, destination=dest, departure_date="2025-12-10"
        ),
    )


# --- core output ---


def test_returns_at_most_5_results(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"origin": "BOM", "destination": "CDG", "departure_date": "2025-12-10"}
        )
    assert len(result) <= 5


def test_results_sorted_by_price_ascending(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"origin": "BOM", "destination": "CDG", "departure_date": "2025-12-10"}
        )
    prices = [r["total_price_usd"] for r in result]
    assert prices == sorted(prices)


def test_required_fields_present(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"origin": "BOM", "destination": "CDG", "departure_date": "2025-12-10"}
        )
    required = {
        "id",
        "segments",
        "total_price_usd",
        "num_stops",
        "total_duration_minutes",
    }
    for r in result:
        assert required.issubset(r.keys())


# --- filters ---


def test_max_price_filter(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {
                "origin": "JFK",
                "destination": "LHR",
                "departure_date": "2025-12-10",
                "max_price": 800.0,
            }
        )
    assert all(r["total_price_usd"] <= 800.0 for r in result)


def test_max_stops_nonstop_filter(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {
                "origin": "BOM",
                "destination": "NRT",
                "departure_date": "2025-12-10",
                "max_stops": 0,
            }
        )
    assert all(r["num_stops"] == 0 for r in result)


# --- error handling ---


def test_mock_fallback_on_api_error(tool: FlightSearchTool) -> None:
    with patch.object(tool, "_fetch", side_effect=Exception("connection refused")):
        result = tool.invoke(
            {"origin": "DEL", "destination": "CDG", "departure_date": "2025-12-10"}
        )
    assert len(result) > 0


def test_strict_tool_raises_on_error(strict_tool: FlightSearchTool) -> None:
    with patch.object(strict_tool, "_fetch", side_effect=Exception("API down")):
        with pytest.raises(Exception):
            strict_tool.invoke(
                {"origin": "BOM", "destination": "CDG", "departure_date": "2025-12-10"}
            )


# --- caching ---


def test_second_call_does_not_hit_fetch(tool: FlightSearchTool) -> None:
    data = tool._mock_data(origin="SIN", destination="DXB", departure_date="2025-12-10")
    with patch.object(tool, "_fetch", return_value=data) as mock_fetch:
        tool.invoke(
            {"origin": "SIN", "destination": "DXB", "departure_date": "2025-12-10"}
        )
        tool.invoke(
            {"origin": "SIN", "destination": "DXB", "departure_date": "2025-12-10"}
        )
    assert mock_fetch.call_count == 1


# --- input normalisation ---


def test_origin_destination_uppercased(tool: FlightSearchTool) -> None:
    data = tool._mock_data(origin="BOM", destination="CDG", departure_date="2025-12-10")
    with patch.object(tool, "_fetch", return_value=data) as mock_fetch:
        tool.invoke(
            {"origin": "bom", "destination": "cdg", "departure_date": "2025-12-10"}
        )
    _, call_kwargs = mock_fetch.call_args
    assert call_kwargs.get("origin", "").isupper() or call_kwargs.get("origin") == "BOM"


# --- parse helper ---


def test_parse_dt_valid_string() -> None:
    t = FlightSearchTool._parse_dt("2025-12-10 14:30")
    assert isinstance(t, datetime)
    assert t.hour == 14
    assert t.minute == 30


def test_parse_dt_bad_string_returns_datetime() -> None:
    t = FlightSearchTool._parse_dt("not-a-date")
    assert isinstance(t, datetime)


# --- diverse routes ---


def test_diverse_bom_cdg(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool, "BOM", "CDG"):
        r = tool.invoke(
            {"origin": "BOM", "destination": "CDG", "departure_date": "2025-07-01"}
        )
    assert len(r) > 0


def test_diverse_jfk_nrt(tool: FlightSearchTool) -> None:
    with patch.object(
        tool,
        "_fetch",
        return_value=tool._mock_data("JFK", "NRT", "2025-08-15"),
    ):
        r = tool.invoke(
            {"origin": "JFK", "destination": "NRT", "departure_date": "2025-08-15"}
        )
    assert len(r) > 0


def test_diverse_lhr_dxb(tool: FlightSearchTool) -> None:
    with patch.object(
        tool,
        "_fetch",
        return_value=tool._mock_data("LHR", "DXB", "2025-09-20"),
    ):
        r = tool.invoke(
            {"origin": "LHR", "destination": "DXB", "departure_date": "2025-09-20"}
        )
    assert len(r) > 0


def test_round_trip_accepted(tool: FlightSearchTool) -> None:
    with _mock_fetch(tool):
        r = tool.invoke(
            {
                "origin": "BOM",
                "destination": "SIN",
                "departure_date": "2025-12-01",
                "return_date": "2025-12-10",
            }
        )
    assert isinstance(r, list)
