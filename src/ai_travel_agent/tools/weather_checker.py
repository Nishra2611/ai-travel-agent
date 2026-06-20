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

        key = settings.openweathermap_api_key

        if not key:
            logger.warning("Missing API key")
            return []

        loc = geocode(city)
        if not loc:
            return []

        mode = os.getenv("WEATHER_API_MODE", "forecast5")

        try:
            if mode == "onecall":
                return self._onecall(loc, key, days)
            return self._forecast5(loc, key, days)
        except Exception as exc:
            logger.exception(exc)
            return []

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
    )
    def _onecall(self, loc: dict[str, Any], key: str, days: int) -> list[dict[str, Any]]:

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
            result.append({
                "date": datetime.fromtimestamp(day["dt"]).strftime("%Y-%m-%d"),
                "condition": day["weather"][0]["description"],
                "temp_min": day["temp"]["min"],
                "temp_max": day["temp"]["max"],
                "rain_chance": day.get("pop", 0),
            })

        return result

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
    )
    def _forecast5(self, loc: dict[str, Any], key: str, days: int) -> list[dict[str, Any]]:

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
            temps = [s["main"]["temp"] for s in slots]

            result.append({
                "date": date,
                "temp_min": min(temps),
                "temp_max": max(temps),
            })

        return result