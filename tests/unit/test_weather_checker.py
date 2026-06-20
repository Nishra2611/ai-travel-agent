# Target: tests/tools/test_weather_checker.py

from unittest.mock import MagicMock, patch

import pytest

from ai_travel_agent.tools.weather_checker import WeatherCheckerTool

MOCK_GEOCODE = {"lat": 51.5074, "lng": -0.1278, "display_name": "London, UK"}

# Simulates 3 days × 4 slots each (3-hour intervals)
def _make_forecast5_response():
    slots = []
    days = ["2025-06-18", "2025-06-19", "2025-06-20"]
    for day in days:
        for hour in ["06:00:00", "09:00:00", "12:00:00", "15:00:00"]:
            slots.append({
                "dt_txt": f"{day} {hour}",
                "main": {"temp": 15.0 if "06" in hour else 20.0, "humidity": 70},
                "weather": [{"description": "partly cloudy" if "06" in hour else "sunny intervals"}],
                "pop": 0.1 if "06" in hour else 0.3,
            })
    return {"list": slots}


@pytest.fixture
def tool():
    return WeatherCheckerTool()


def test_returns_empty_when_api_key_missing(tool, monkeypatch):
    monkeypatch.delenv("OPENWEATHERMAP_API_KEY", raising=False)
    assert tool._run(city="London", days=5) == []


def test_returns_empty_when_geocode_fails(tool, monkeypatch):
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "test-key")
    with patch("ai_travel_agent.tools.weather_checker.geocode", return_value=None):
        assert tool._run(city="NonexistentCity999", days=5) == []


def test_forecast5_daily_aggregation(tool, monkeypatch):
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "test-key")
    monkeypatch.setenv("WEATHER_API_MODE", "forecast5")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = _make_forecast5_response()

    with patch("ai_travel_agent.tools.weather_checker.geocode", return_value=MOCK_GEOCODE), \
         patch("httpx.get", return_value=mock_resp):
        result = tool._run(city="London", days=5)

    assert isinstance(result, list)
    assert len(result) <= 5
    for day in result:
        assert "date" in day
        assert "condition" in day
        assert "temp_min" in day and "temp_max" in day
        assert day["temp_max"] >= day["temp_min"], "temp_max must be >= temp_min"
        assert 0 <= day["rain_chance_pct"] <= 100
        assert day["humidity_pct"] is not None


def test_condition_is_capitalised(tool, monkeypatch):
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "test-key")
    monkeypatch.setenv("WEATHER_API_MODE", "forecast5")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = _make_forecast5_response()

    with patch("ai_travel_agent.tools.weather_checker.geocode", return_value=MOCK_GEOCODE), \
         patch("httpx.get", return_value=mock_resp):
        result = tool._run(city="London", days=3)

    for day in result:
        assert day["condition"][0].isupper(), f"condition not capitalised: {day['condition']}"


def test_days_param_caps_result_length(tool, monkeypatch):
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "test-key")
    monkeypatch.setenv("WEATHER_API_MODE", "forecast5")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = _make_forecast5_response()  # 3 days of data

    with patch("ai_travel_agent.tools.weather_checker.geocode", return_value=MOCK_GEOCODE), \
         patch("httpx.get", return_value=mock_resp):
        result_2 = tool._run(city="London", days=2)
        result_3 = tool._run(city="London", days=3)

    assert len(result_2) <= 2
    assert len(result_3) <= 3


def test_graceful_failure_on_http_error(tool, monkeypatch):
    monkeypatch.setenv("OPENWEATHERMAP_API_KEY", "bad-key")
    monkeypatch.setenv("WEATHER_API_MODE", "forecast5")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("401 Unauthorized")

    with patch("ai_travel_agent.tools.weather_checker.geocode", return_value=MOCK_GEOCODE), \
         patch("httpx.get", return_value=mock_resp):
        result = tool._run(city="London", days=5)

    # Must return [] not raise
    assert result == []
