"""
tests/unit/test_travel_time_client.py

Unit tests for travel_time_client.py.
OSRM and httpx are mocked — no network calls.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_travel_agent.services.travel_time_client import (
    _haversine_minutes,
    get_travel_time_safe,
)


class TestHaversineMinutes:
    def test_same_point_returns_minimum(self) -> None:
        result = _haversine_minutes(48.85, 2.35, 48.85, 2.35, 30.0)
        assert result == 5  # minimum floor

    def test_paris_to_louvre_reasonable(self) -> None:
        # Eiffel Tower → Louvre: ~4 km, ~8 min at 30 km/h
        result = _haversine_minutes(48.8584, 2.2945, 48.8606, 2.3376, 30.0)
        assert 5 <= result <= 20

    def test_intercontinental_reasonable(self) -> None:
        # London → Paris: ~340 km
        result = _haversine_minutes(51.5074, -0.1278, 48.8566, 2.3522, 80.0)
        assert 150 <= result <= 400

    def test_faster_speed_gives_fewer_minutes(self) -> None:
        slow = _haversine_minutes(48.85, 2.35, 48.90, 2.40, 20.0)
        fast = _haversine_minutes(48.85, 2.35, 48.90, 2.40, 60.0)
        assert slow > fast

    def test_returns_int(self) -> None:
        result = _haversine_minutes(48.85, 2.35, 48.90, 2.40, 30.0)
        assert isinstance(result, int)


class TestGetTravelTimeSafe:
    def test_returns_osrm_result_on_success(self) -> None:
        with patch(
            "ai_travel_agent.services.travel_time_client.get_travel_time_minutes",
            return_value=25,
        ):
            result = get_travel_time_safe(48.85, 2.35, 48.86, 2.36)
        assert result == 25

    def test_returns_haversine_on_osrm_failure(self) -> None:
        with patch(
            "ai_travel_agent.services.travel_time_client.get_travel_time_minutes",
            side_effect=Exception("connection refused"),
        ):
            result = get_travel_time_safe(48.85, 2.35, 48.86, 2.36)
        assert isinstance(result, int)
        assert result > 0

    def test_never_raises(self) -> None:
        with patch(
            "ai_travel_agent.services.travel_time_client.get_travel_time_minutes",
            side_effect=RuntimeError("total failure"),
        ):
            # must not raise
            result = get_travel_time_safe(0.0, 0.0, 90.0, 180.0)
        assert isinstance(result, int)

    def test_returns_positive_int(self) -> None:
        with patch(
            "ai_travel_agent.services.travel_time_client.get_travel_time_minutes",
            return_value=12,
        ):
            result = get_travel_time_safe(48.85, 2.35, 48.86, 2.36)
        assert result > 0
        assert isinstance(result, int)
