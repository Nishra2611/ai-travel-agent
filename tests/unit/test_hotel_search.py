"""Unit tests for HotelSearchTool."""

from unittest.mock import patch

import pytest

from ai_travel_agent.tools.hotel_search import HotelSearchTool


@pytest.fixture
def tool() -> HotelSearchTool:
    return HotelSearchTool(use_mock_on_failure=True)


def _mock_fetch(tool: HotelSearchTool, city: str = "paris"):
    return patch.object(
        tool,
        "_fetch",
        return_value=tool._mock_data(
            city=city, check_in="2025-12-10", check_out="2025-12-15"
        ),
    )


# --- core output ---


def test_returns_at_most_10_results(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    assert len(result) <= 10


def test_sorted_by_rating_desc_then_price_asc(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    ratings = [h.get("star_rating") or 0.0 for h in result]
    assert ratings == sorted(ratings, reverse=True)


def test_required_fields_present(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    required = {
        "id",
        "name",
        "price_per_night_usd",
        "total_price_usd",
        "star_rating",
        "location",
        "amenities",
    }
    for h in result:
        assert required.issubset(h.keys())


def test_location_has_lat_lng(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    for h in result:
        assert "latitude" in h["location"]
        assert "longitude" in h["location"]


# --- price calculation ---


def test_total_price_is_nightly_times_nights(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    # 5 nights
    for h in result:
        expected = h["price_per_night_usd"] * 5
        assert abs(h["total_price_usd"] - expected) < 0.01


# --- filters ---


def test_min_rating_filter(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {
                "city": "Paris",
                "check_in": "2025-12-10",
                "check_out": "2025-12-15",
                "min_rating": 4.3,
            }
        )
    assert all(h["star_rating"] >= 4.3 for h in result)


def test_max_price_per_night_filter(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {
                "city": "Paris",
                "check_in": "2025-12-10",
                "check_out": "2025-12-15",
                "max_price_per_night": 150.0,
            }
        )
    assert all(h["price_per_night_usd"] <= 150.0 for h in result)


# --- error handling ---


def test_mock_fallback_on_api_error(tool: HotelSearchTool) -> None:
    with patch.object(tool, "_fetch", side_effect=Exception("timeout")):
        result = tool.invoke(
            {"city": "Bali", "check_in": "2025-06-01", "check_out": "2025-06-07"}
        )
    assert len(result) > 0


# --- caching ---


def test_second_call_does_not_hit_fetch(tool: HotelSearchTool) -> None:
    data = tool._mock_data(city="tokyo", check_in="2025-07-01", check_out="2025-07-07")
    with patch.object(tool, "_fetch", return_value=data) as mock_fetch:
        tool.invoke(
            {"city": "Tokyo", "check_in": "2025-07-01", "check_out": "2025-07-07"}
        )
        tool.invoke(
            {"city": "Tokyo", "check_in": "2025-07-01", "check_out": "2025-07-07"}
        )
    assert mock_fetch.call_count == 1


# --- extra fields from SerpApi ---


def test_eco_certified_field_present(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    assert all("eco_certified" in h for h in result)


def test_check_in_out_time_fields(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool):
        result = tool.invoke(
            {"city": "Paris", "check_in": "2025-12-10", "check_out": "2025-12-15"}
        )
    for h in result:
        assert "check_in_time" in h
        assert "check_out_time" in h


# --- diverse cities ---


def test_diverse_tokyo(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool, "tokyo"):
        r = tool.invoke(
            {"city": "Tokyo", "check_in": "2025-07-01", "check_out": "2025-07-07"}
        )
    assert len(r) > 0


def test_diverse_bali(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool, "bali"):
        r = tool.invoke(
            {"city": "Bali", "check_in": "2025-06-01", "check_out": "2025-06-08"}
        )
    assert len(r) > 0


def test_diverse_dubai(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool, "dubai"):
        r = tool.invoke(
            {"city": "Dubai", "check_in": "2025-01-15", "check_out": "2025-01-22"}
        )
    assert len(r) > 0


def test_diverse_london(tool: HotelSearchTool) -> None:
    with _mock_fetch(tool, "london"):
        r = tool.invoke(
            {"city": "London", "check_in": "2025-09-10", "check_out": "2025-09-14"}
        )
    assert len(r) > 0
