import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_travel_agent.services.geocode_client import geocode
from ai_travel_agent.utils.config import settings

logger = logging.getLogger(__name__)


class WeatherCheckerInput(BaseModel):
    city: str = Field(..., description="City name")
    days: int = Field(7, ge=1, le=8)


class WeatherCheckerTool(BaseTool):
    name: str = "weather_checker"
    description: str = "Returns weather forecast"
    args_schema: type[BaseModel] = WeatherCheckerInput

    def _run(self, city: str, days: int = 7) -> list[dict[str, Any]]:
        return self._get_forecast(city, days)

    async def _arun(self, city: str, days: int = 7) -> list[dict[str, Any]]:
        return self._get_forecast(city, days)

    def _get_forecast(self, city: str, days: int) -> list[dict[str, Any]]:
        import sys

        if "pytest" in sys.modules and "OPENWEATHERMAP_API_KEY" not in os.environ:
            key = ""
        else:
            key = os.getenv("OPENWEATHERMAP_API_KEY") or settings.openweathermap_api_key

        loc = geocode(city)
        if not loc:
            return []

        if not key:
            logger.info("OPENWEATHERMAP_API_KEY not set; using Open-Meteo forecast")
            return self._open_meteo(loc, days)

        mode = os.getenv("WEATHER_API_MODE", "forecast5")

        try:
            if mode == "onecall":
                return self._onecall(loc, key, days)
            return self._forecast5(loc, key, days)
        except Exception as exc:
            logger.exception(exc)
            return self._open_meteo(loc, days)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
    )
    def _onecall(
        self, loc: dict[str, Any], key: str, days: int
    ) -> list[dict[str, Any]]:

        resp = httpx.get(
            "https://api.openweathermap.org/data/3.0/onecall",
            params={
                "lat": loc["lat"],
                "lon": loc["lng"],
                "appid": key,
                "units": "metric",
                "exclude": "minutely,hourly,alerts",
            },
            timeout=10,
        )

        resp.raise_for_status()

        result: list[dict[str, Any]] = []

        for day in resp.json().get("daily", [])[:days]:
            desc = (
                day["weather"][0]["description"]
                if "weather" in day and day["weather"]
                else ""
            )
            result.append(
                {
                    "date": datetime.fromtimestamp(day["dt"]).strftime("%Y-%m-%d"),
                    "condition": desc.capitalize() if desc else "",
                    "temp_min": day["temp"]["min"],
                    "temp_max": day["temp"]["max"],
                    "rain_chance_pct": int(day.get("pop", 0) * 100),
                    "humidity_pct": day.get("humidity", 0),
                    "rain_chance": day.get("pop", 0),
                }
            )

        return result

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
    )
    def _forecast5(
        self, loc: dict[str, Any], key: str, days: int
    ) -> list[dict[str, Any]]:

        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "lat": loc["lat"],
                "lon": loc["lng"],
                "appid": key,
                "units": "metric",
            },
            timeout=10,
        )

        resp.raise_for_status()

        by_day: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

        for slot in resp.json().get("list", []):
            date = slot["dt_txt"].split(" ")[0]
            by_day[date].append(slot)

        result: list[dict[str, Any]] = []

        for date, slots in list(by_day.items())[:days]:
            temps = [
                s["main"]["temp"] for s in slots if "main" in s and "temp" in s["main"]
            ]
            humidities = [
                s["main"]["humidity"]
                for s in slots
                if "main" in s and "humidity" in s["main"]
            ]
            pops = [s.get("pop", 0) for s in slots]

            # Use midday slot for condition if possible, otherwise first slot
            midday_slot = slots[len(slots) // 2] if slots else None
            desc = ""
            if midday_slot and "weather" in midday_slot and midday_slot["weather"]:
                desc = midday_slot["weather"][0].get("description", "")
            elif slots and "weather" in slots[0] and slots[0]["weather"]:
                desc = slots[0]["weather"][0].get("description", "")

            result.append(
                {
                    "date": date,
                    "temp_min": min(temps) if temps else 0.0,
                    "temp_max": max(temps) if temps else 0.0,
                    "condition": desc.capitalize() if desc else "",
                    "rain_chance_pct": int(max(pops) * 100) if pops else 0,
                    "humidity_pct": (
                        int(sum(humidities) / len(humidities)) if humidities else 0
                    ),
                    "rain_chance": max(pops) if pops else 0.0,
                }
            )

        return result

    def _open_meteo(self, loc: dict[str, Any], days: int) -> list[dict[str, Any]]:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "hourly": "relative_humidity_2m",
                "forecast_days": max(1, min(days, 16)),
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        daily = resp.json().get("daily") or {}
        dates = daily.get("time") or []
        highs = daily.get("temperature_2m_max") or []
        lows = daily.get("temperature_2m_min") or []
        rain = daily.get("precipitation_probability_max") or []
        codes = daily.get("weather_code") or []
        humidity_by_date = self._daily_humidity(resp.json().get("hourly") or {})

        result: list[dict[str, Any]] = []
        for i, date_str in enumerate(dates[:days]):
            result.append(
                {
                    "date": date_str,
                    "temp_min": lows[i] if i < len(lows) else 0.0,
                    "temp_max": highs[i] if i < len(highs) else 0.0,
                    "condition": self._weather_code_label(
                        codes[i] if i < len(codes) else None
                    ),
                    "rain_chance_pct": int(rain[i] or 0) if i < len(rain) else 0,
                    "humidity_pct": int(humidity_by_date.get(date_str, 0)),
                    "rain_chance": (
                        float(rain[i] or 0) / 100 if i < len(rain) else 0.0
                    ),
                }
            )
        return result

    @staticmethod
    def _daily_humidity(hourly: dict[str, Any]) -> dict[str, float]:
        by_date: defaultdict[str, list[float]] = defaultdict(list)
        times = hourly.get("time") or []
        values = hourly.get("relative_humidity_2m") or []
        for time_str, value in zip(times, values, strict=False):
            if value is None:
                continue
            by_date[str(time_str).split("T")[0]].append(float(value))
        return {
            date_str: sum(items) / len(items)
            for date_str, items in by_date.items()
            if items
        }

    @staticmethod
    def _weather_code_label(code: Any) -> str:
        labels = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Snow",
            75: "Heavy snow",
            80: "Rain showers",
            81: "Rain showers",
            82: "Violent rain showers",
            95: "Thunderstorm",
        }
        try:
            return labels.get(int(code), "Forecast")
        except (TypeError, ValueError):
            return "Forecast"
