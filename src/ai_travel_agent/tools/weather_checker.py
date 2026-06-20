print("WEATHER_CHECKER FILE LOADED")

import os
import logging
from datetime import datetime
from collections import defaultdict

import httpx
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from ai_travel_agent.utils.config import settings
from ai_travel_agent.services.geocode_client import geocode

logger = logging.getLogger(__name__)


class WeatherCheckerInput(BaseModel):
    city: str = Field(..., description="City name, e.g. 'London' or 'Tokyo'")
    days: int = Field(7, ge=1, le=8, description="Days to forecast (1–8)")


class WeatherCheckerTool(BaseTool):
    name: str = "weather_checker"

    description: str = (
        "Returns a per-day weather forecast for a city."
    )

    args_schema: type[BaseModel] = WeatherCheckerInput

    def _run(self, city: str, days: int = 7) -> list[dict]:
        return self._get_forecast(city, days)

    async def _arun(self, city: str, days: int = 7) -> list[dict]:
        return self._get_forecast(city, days)

    def _get_forecast(self, city: str, days: int) -> list[dict]:

        key = settings.openweathermap_api_key

        if not key:
            logger.warning("OPENWEATHERMAP_API_KEY not set")
            return []

        loc = geocode(city)

        if not loc:
            logger.warning("Could not geocode city '%s'", city)
            return []

        mode = os.getenv("WEATHER_API_MODE", "forecast5")

        try:
            if mode == "onecall":
                return self._onecall(loc, key, days)

            return self._forecast5(loc, key, days)

        except Exception as exc:
            logger.exception("Weather API failed")
            print("WEATHER ERROR:", exc)
            return []

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _onecall(self, loc: dict, key: str, days: int) -> list[dict]:

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

        if resp.status_code != 200:
            print("STATUS:", resp.status_code)
            print("BODY:", resp.text)

        resp.raise_for_status()

        result = []

        for day in resp.json().get("daily", [])[:days]:
            result.append(
                {
                    "date": datetime.fromtimestamp(day["dt"]).strftime("%Y-%m-%d"),
                    "condition": day["weather"][0]["description"].capitalize(),
                    "temp_min": round(day["temp"]["min"], 1),
                    "temp_max": round(day["temp"]["max"], 1),
                    "rain_chance_pct": round(day.get("pop", 0) * 100),
                    "humidity_pct": day.get("humidity"),
                }
            )

        return result

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(min=1, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _forecast5(self, loc: dict, key: str, days: int) -> list[dict]:
        
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

        print("STATUS:", resp.status_code)
        print("BODY:", resp.text[:1000])

        resp.raise_for_status()

        if resp.status_code != 200:
                    print("STATUS:", resp.status_code)
                    print("BODY:", resp.text)

        resp.raise_for_status()

        by_day = defaultdict(list)

        for slot in resp.json().get("list", []):
            date = slot["dt_txt"].split(" ")[0]
            by_day[date].append(slot)

        result = []

        for date, slots in list(by_day.items())[:days]:

            temps = [s["main"]["temp"] for s in slots]
            pops = [s.get("pop", 0) for s in slots]

            conditions = [
                s["weather"][0]["description"]
                for s in slots
            ]

            modal_cond = max(
                set(conditions),
                key=conditions.count
            )

            mid = slots[len(slots) // 2]

            result.append(
                {
                    "date": date,
                    "condition": modal_cond.capitalize(),
                    "temp_min": round(min(temps), 1),
                    "temp_max": round(max(temps), 1),
                    "rain_chance_pct": round(max(pops) * 100),
                    "humidity_pct": mid["main"]["humidity"],
                }
            )

        return result