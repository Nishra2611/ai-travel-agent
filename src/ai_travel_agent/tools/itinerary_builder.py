"""
Converts raw tool results (flights, hotels, attractions, restaurants, weather)
plus parsed TravelPreferences into a validated, day-by-day Itinerary object.

Design decisions:
  - Deterministic slot assignment (no LLM): fast, testable, predictable.
    LLM narration of descriptions is deferred to Week 8.
  - Opening-hours validation: museums not assigned before open time,
    attractions not assigned after close.
  - Travel-time buffers: OSRM between consecutive activities.
    Safe fallback to Haversine when OSRM is offline.
  - Multi-day structure:
      Day 1   = arrival day  (afternoon/evening activities only)
      Days 2…N-1 = full days (morning / afternoon / evening)
      Day N   = departure day (morning only, airport transfer in evening)
  - 3 trip types handled via activity_type weighting:
      city_tour   → culture + landmark heavy
      beach       → relaxation + nature heavy, late morning start
      adventure   → nature + outdoor heavy, early morning start

Slot time windows (24h):
  MORNING   : 08:00 – 12:00
  AFTERNOON : 13:00 – 17:00
  EVENING   : 18:00 – 21:00

Returns: Itinerary.model_dump() as dict (consistent with all other tools).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from pydantic import BaseModel, Field

from ai_travel_agent.models.attraction import AttractionCategory
from ai_travel_agent.models.flight import FlightOption, FlightSegment
from ai_travel_agent.models.hotel import GeoLocation, HotelOption
from ai_travel_agent.models.itinerary import (
    DayPlan,
    Itinerary,
    ItineraryActivity,
    TimeSlot,
)
from ai_travel_agent.services.travel_time_client import get_travel_time_safe
from ai_travel_agent.tools.base import BaseTravelTool
from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# ── slot time windows ─────────────────────────────────────────────────────────

_SLOT_START: dict[TimeSlot, time] = {
    TimeSlot.MORNING: time(8, 0),
    TimeSlot.AFTERNOON: time(13, 0),
    TimeSlot.EVENING: time(18, 0),
}
_SLOT_END: dict[TimeSlot, time] = {
    TimeSlot.MORNING: time(12, 0),
    TimeSlot.AFTERNOON: time(17, 0),
    TimeSlot.EVENING: time(21, 0),
}

# Minutes of buffer between end of activity and next start
_BUFFER_MINUTES = 15

# Categories that map to each slot preference
# (higher priority = tried first for that slot)
_SLOT_AFFINITY: dict[str, list[TimeSlot]] = {
    AttractionCategory.MUSEUM: [TimeSlot.MORNING, TimeSlot.AFTERNOON],
    AttractionCategory.LANDMARK: [
        TimeSlot.MORNING,
        TimeSlot.AFTERNOON,
        TimeSlot.EVENING,
    ],
    AttractionCategory.PARK: [TimeSlot.MORNING, TimeSlot.AFTERNOON],
    AttractionCategory.SHOPPING: [TimeSlot.AFTERNOON, TimeSlot.MORNING],
    AttractionCategory.ENTERTAINMENT: [TimeSlot.EVENING, TimeSlot.AFTERNOON],
    AttractionCategory.RESTAURANT: [TimeSlot.EVENING, TimeSlot.AFTERNOON],
    AttractionCategory.TOUR: [TimeSlot.MORNING, TimeSlot.AFTERNOON],
}


# ── input schema ──────────────────────────────────────────────────────────────


class ItineraryBuilderInput(BaseModel):
    preferences: dict[str, Any] = Field(
        ..., description="TravelPreferences.model_dump()"
    )
    flights: list[dict[str, Any]] = Field(default_factory=list)
    hotels: list[dict[str, Any]] = Field(default_factory=list)
    attractions: list[dict[str, Any]] = Field(default_factory=list)
    restaurants: list[dict[str, Any]] = Field(default_factory=list)
    weather: list[dict[str, Any]] = Field(default_factory=list)
    budget_summary: dict[str, Any] = Field(default_factory=dict)


# ── main tool ─────────────────────────────────────────────────────────────────


class ItineraryBuilderTool(BaseTravelTool):
    name: str = "itinerary_builder"
    description: str = (
        "Builds a validated day-by-day itinerary from all collected travel data. "
        "Assigns activities to time slots, respects opening hours, adds travel "
        "time buffers between consecutive activities. Call after all search tools."
    )
    args_schema: type[BaseModel] = ItineraryBuilderInput
    cache_namespace: str = "itinerary"
    cache_ttl: int = 1800  # 30 min

    def _run(  # type: ignore[override]
        self,
        preferences: dict[str, Any],
        flights: list[dict[str, Any]] | None = None,
        hotels: list[dict[str, Any]] | None = None,
        attractions: list[dict[str, Any]] | None = None,
        restaurants: list[dict[str, Any]] | None = None,
        weather: list[dict[str, Any]] | None = None,
        budget_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        builder = _ItineraryBuilder(
            preferences=preferences,
            flights=flights or [],
            hotels=hotels or [],
            attractions=attractions or [],
            restaurants=restaurants or [],
            weather=weather or [],
            budget_summary=budget_summary or {},
        )
        itinerary = builder.build()

        logger.info(
            "ItineraryBuilder: %d days, %d total activities, destination=%s",
            len(itinerary.days),
            sum(len(d.activities) for d in itinerary.days),
            itinerary.destination,
        )

        result = itinerary.model_dump(mode="json")
        result["is_within_budget"] = itinerary.is_within_budget

        return result

    # these satisfy BaseTravelTool abstract methods but are not used
    def _fetch(self, **kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[override]
        raise NotImplementedError

    def _mock_data(self, **kwargs: Any) -> list[dict[str, Any]]:  # type: ignore[override]
        raise NotImplementedError


# ── internal builder ──────────────────────────────────────────────────────────


class _ItineraryBuilder:
    """
    Internal stateful builder. Separated from the BaseTool wrapper so it
    can be unit-tested directly without LangChain plumbing.
    """

    def __init__(
        self,
        preferences: dict[str, Any],
        flights: list[dict[str, Any]],
        hotels: list[dict[str, Any]],
        attractions: list[dict[str, Any]],
        restaurants: list[dict[str, Any]],
        weather: list[dict[str, Any]],
        budget_summary: dict[str, Any],
    ) -> None:
        self.prefs = preferences
        self.flights = flights
        self.hotels = hotels
        self.attractions = attractions
        self.restaurants = restaurants
        self.weather = weather
        self.budget_summary = budget_summary

        # derived
        self.destination: str = preferences.get("destination", "Unknown")
        self.duration: int = int(preferences.get("duration_days", 3))
        self.num_travelers: int = int(preferences.get("num_travelers", 1))
        self.activity_types: list[str] = preferences.get("activity_types") or []
        self.trip_type: str = self._detect_trip_type()
        self.start_date: date = self._resolve_start_date()

        # weather lookup by date string
        self._weather_by_date: dict[str, str] = {
            w.get("date", ""): self._format_weather(w) for w in weather if w.get("date")
        }

    # ── public ────────────────────────────────────────────────────────────────

    def build(self) -> Itinerary:
        days = self._build_days()
        outbound, ret = self._pick_flights()
        hotel = self._pick_hotel()
        total_cost = self._compute_total_cost(days, outbound, hotel)

        return Itinerary(
            id=f"itin_{uuid.uuid4().hex[:8]}",
            title=f"{self.duration}-Day {self.destination} {self.trip_type.replace('_', ' ').title()} Trip",
            destination=self.destination,
            start_date=self.start_date,
            end_date=self.start_date + timedelta(days=self.duration - 1),
            num_travelers=self.num_travelers,
            days=days,
            outbound_flight=outbound,
            return_flight=ret,
            hotel=hotel,
            total_cost_usd=total_cost,
            budget_usd=self.prefs.get("budget_usd"),
            generated_at=datetime.utcnow().isoformat(),
            version=1,
        )

    # ── trip type detection ───────────────────────────────────────────────────

    def _detect_trip_type(self) -> str:
        """
        Infer trip type from activity_types in preferences.
        beach      → relaxation or nature dominant
        adventure  → adventure dominant
        city_tour  → default (culture, shopping, landmark)
        """
        types = {t.lower() for t in self.activity_types}
        if "adventure" in types:
            return "adventure"
        if "relaxation" in types or ("nature" in types and "culture" not in types):
            return "beach"
        return "city_tour"

    # ── date resolution ───────────────────────────────────────────────────────

    def _resolve_start_date(self) -> date:
        raw = self.prefs.get("start_date")
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            try:
                return date.fromisoformat(raw)
            except ValueError:
                pass
        return date.today() + timedelta(days=30)

    # ── day building ──────────────────────────────────────────────────────────

    def _build_days(self) -> list[DayPlan]:
        days: list[DayPlan] = []
        # Pool of attractions to assign (copy so we can pop)
        pool = list(self.attractions)
        rest_pool = list(self.restaurants)

        for day_num in range(1, self.duration + 1):
            current_date = self.start_date + timedelta(days=day_num - 1)
            date_str = current_date.isoformat()
            weather_str = self._weather_by_date.get(date_str)

            if day_num == 1:
                activities = self._arrival_day(pool, rest_pool, current_date)
                theme = f"Arrival in {self.destination}"
            elif day_num == self.duration:
                activities = self._departure_day(pool, current_date)
                theme = f"Departure from {self.destination}"
            else:
                activities = self._full_day(pool, rest_pool, current_date, day_num)
                theme = self._day_theme(day_num)

            self._inject_travel_times(activities)

            days.append(
                DayPlan(
                    date=current_date,
                    day_number=day_num,
                    theme=theme,
                    activities=activities,
                    daily_budget_usd=self._daily_budget(activities),
                    weather_forecast=weather_str,
                )
            )

        return days

    def _arrival_day(
        self,
        pool: list[dict[str, Any]],
        rest_pool: list[dict[str, Any]],
        day_date: date,
    ) -> list[ItineraryActivity]:
        """
        Arrival day: hotel check-in afternoon, light evening activity.
        No morning activities — flight arrival assumed AM/midday.
        """
        activities: list[ItineraryActivity] = []

        # 1. Airport → hotel transfer
        activities.append(
            ItineraryActivity(
                time_slot=TimeSlot.AFTERNOON,
                start_time=time(14, 0),
                end_time=time(15, 0),
                title=f"Arrive in {self.destination} & Hotel Check-In",
                description=(
                    f"Transfer from airport to your hotel in {self.destination}. "
                    "Check in, freshen up, and get oriented."
                ),
                location_name=self._hotel_name(),
                estimated_cost_usd=0.0,
                notes="Allow extra time if flight is delayed.",
            )
        )

        # 2. One easy landmark or walk in the evening
        eve_pick = self._pick_from_pool(
            pool,
            preferred_slots=[TimeSlot.EVENING],
            preferred_categories=[AttractionCategory.LANDMARK, AttractionCategory.PARK],
        )
        if eve_pick:
            activities.append(self._attraction_to_activity(eve_pick, TimeSlot.EVENING))

        # 3. Welcome dinner
        rest = self._pick_restaurant(rest_pool, TimeSlot.EVENING)
        if rest:
            activities.append(rest)

        return activities

    def _departure_day(
        self,
        pool: list[dict[str, Any]],
        day_date: date,
    ) -> list[ItineraryActivity]:
        """
        Departure day: one morning activity, then airport transfer.
        No afternoon/evening — flight assumed early-mid afternoon.
        """
        activities: list[ItineraryActivity] = []

        # last morning activity
        morning_pick = self._pick_from_pool(
            pool,
            preferred_slots=[TimeSlot.MORNING],
            preferred_categories=[AttractionCategory.SHOPPING, AttractionCategory.PARK],
        )
        if morning_pick:
            activities.append(
                self._attraction_to_activity(morning_pick, TimeSlot.MORNING)
            )

        # airport transfer
        activities.append(
            ItineraryActivity(
                time_slot=TimeSlot.AFTERNOON,
                start_time=time(12, 0),
                end_time=time(13, 30),
                title="Hotel Check-Out & Transfer to Airport",
                description=(
                    "Check out from hotel and transfer to airport. "
                    "Arrive at least 2 hours before departure."
                ),
                location_name="Airport",
                estimated_cost_usd=0.0,
                notes="Keep luggage ready the night before.",
            )
        )

        return activities

    def _full_day(
        self,
        pool: list[dict[str, Any]],
        rest_pool: list[dict[str, Any]],
        day_date: date,
        day_num: int,
    ) -> list[ItineraryActivity]:
        """
        Full day: one activity per slot + dinner.
        Trip-type adjusts which categories and which slots are preferred.
        """
        activities: list[ItineraryActivity] = []

        slot_prefs = self._slot_preferences_for_trip_type()

        for slot in [TimeSlot.MORNING, TimeSlot.AFTERNOON]:
            cats = slot_prefs.get(slot, [])
            pick = self._pick_from_pool(
                pool, preferred_slots=[slot], preferred_categories=cats
            )
            if pick:
                act = self._attraction_to_activity(pick, slot)
                if not self._opening_hours_ok(pick, slot):
                    act = self._shift_slot(act, pick)
                activities.append(act)

        # dinner in evening
        rest = self._pick_restaurant(rest_pool, TimeSlot.EVENING)
        if rest:
            activities.append(rest)

        # one evening activity (landmark or entertainment)
        eve_pick = self._pick_from_pool(
            pool,
            preferred_slots=[TimeSlot.EVENING],
            preferred_categories=[
                AttractionCategory.LANDMARK,
                AttractionCategory.ENTERTAINMENT,
            ],
        )
        if eve_pick:
            activities.append(self._attraction_to_activity(eve_pick, TimeSlot.EVENING))

        return activities

    # ── slot preference by trip type ──────────────────────────────────────────

    def _slot_preferences_for_trip_type(self) -> dict[TimeSlot, list[str]]:
        if self.trip_type == "adventure":
            return {
                TimeSlot.MORNING: [AttractionCategory.PARK, AttractionCategory.TOUR],
                TimeSlot.AFTERNOON: [
                    AttractionCategory.PARK,
                    AttractionCategory.LANDMARK,
                ],
            }
        if self.trip_type == "beach":
            return {
                TimeSlot.MORNING: [
                    AttractionCategory.PARK,
                    AttractionCategory.LANDMARK,
                ],
                TimeSlot.AFTERNOON: [
                    AttractionCategory.SHOPPING,
                    AttractionCategory.ENTERTAINMENT,
                ],
            }
        # city_tour default
        return {
            TimeSlot.MORNING: [AttractionCategory.MUSEUM, AttractionCategory.LANDMARK],
            TimeSlot.AFTERNOON: [AttractionCategory.SHOPPING, AttractionCategory.TOUR],
        }

    # ── pool management ───────────────────────────────────────────────────────

    def _pick_from_pool(
        self,
        pool: list[dict[str, Any]],
        preferred_slots: list[TimeSlot],
        preferred_categories: list[str],
    ) -> dict[str, Any] | None:
        """
        Pick and remove the best-matching attraction from pool.
        Priority: preferred_categories first, then any remaining.
        """
        # try preferred categories in order
        for cat in preferred_categories:
            for i, item in enumerate(pool):
                if item.get("category") == cat:
                    return pool.pop(i)

        # fallback: any item
        return pool.pop(0) if pool else None

    def _pick_restaurant(
        self,
        rest_pool: list[dict[str, Any]],
        slot: TimeSlot,
    ) -> ItineraryActivity | None:
        if not rest_pool:
            return None
        r = rest_pool.pop(0)
        return ItineraryActivity(
            time_slot=slot,
            start_time=_SLOT_START[slot],
            end_time=time(_SLOT_START[slot].hour + 1, 30),
            title=f"Dinner at {r.get('name', 'Local Restaurant')}",
            description=(
                f"{r.get('name', 'A highly rated local restaurant')} — "
                f"rated {r.get('rating', 'N/A')}/5. "
                f"{r.get('description', 'Enjoy authentic local cuisine.')}"
            ),
            location_name=r.get("name", "Restaurant"),
            estimated_cost_usd=self._meal_cost(),
            notes=r.get("address", ""),
        )

    # ── opening hours validation ───────────────────────────────────────────────

    def _opening_hours_ok(self, attraction: dict[str, Any], slot: TimeSlot) -> bool:
        """
        Returns False if we KNOW the attraction is closed during this slot.
        If opening_hours is missing, assume open (return True).
        """
        oh: dict[str, Any] | None = attraction.get("opening_hours")
        if not oh:
            return True  # no data → assume open

        # Use Monday as proxy for a generic weekday check
        # (full day-of-week checking deferred to Week 7 conflict resolution)
        sample = oh.get("monday") or oh.get("tuesday") or oh.get("wednesday")
        if not sample:
            return True

        slot_start = _SLOT_START[slot]
        slot_end = _SLOT_END[slot]

        try:
            # expect format "09:00-18:00" or "9:00 AM - 6:00 PM"
            open_str, close_str = _parse_hours_range(sample)
            open_t = _parse_time_str(open_str)
            close_t = _parse_time_str(close_str)
            # activity must start during open window
            return open_t <= slot_start and close_t >= slot_end
        except Exception:
            return True  # parse failed → assume open

    def _shift_slot(
        self, activity: ItineraryActivity, attraction: dict[str, Any]
    ) -> ItineraryActivity:
        """
        If a slot is invalid due to opening hours, try the next available slot.
        Mutates and returns the activity.
        """
        oh = attraction.get("opening_hours") or {}
        sample = oh.get("monday") or ""
        if not sample:
            return activity
        try:
            open_str, _ = _parse_hours_range(sample)
            open_t = _parse_time_str(open_str)
            if open_t >= time(13, 0):
                activity = activity.model_copy(
                    update={"time_slot": TimeSlot.AFTERNOON, "start_time": open_t}
                )
        except Exception:
            pass
        return activity

    # ── travel time injection ─────────────────────────────────────────────────

    def _inject_travel_times(self, activities: list[ItineraryActivity]) -> None:
        """
        For each consecutive pair of activities that have lat/lng,
        compute travel time and store in travel_time_to_next_minutes.
        """
        for i in range(len(activities) - 1):
            curr = activities[i]
            nxt = activities[i + 1]

            curr_loc = self._resolve_location(curr.location_name)
            nxt_loc = self._resolve_location(nxt.location_name)

            if curr_loc and nxt_loc:
                mins = get_travel_time_safe(
                    curr_loc["lat"],
                    curr_loc["lng"],
                    nxt_loc["lat"],
                    nxt_loc["lng"],
                )
                activities[i] = curr.model_copy(
                    update={"travel_time_to_next_minutes": mins}
                )
            else:
                # no location data — use 20 min default urban buffer
                activities[i] = curr.model_copy(
                    update={"travel_time_to_next_minutes": 20}
                )

    def _resolve_location(self, location_name: str) -> dict[str, float] | None:
        """
        Try to find lat/lng for a location name from the attractions pool.
        Falls back to None if not found (travel time will use 20min default).
        """
        for attr in self.attractions:
            if attr.get("name") == location_name:
                loc = attr.get("location") or {}
                if loc.get("latitude") and loc.get("longitude"):
                    return {"lat": loc["latitude"], "lng": loc["longitude"]}
        return None

    # ── attraction → activity mapping ─────────────────────────────────────────

    def _attraction_to_activity(
        self, attr: dict[str, Any], slot: TimeSlot
    ) -> ItineraryActivity:
        start = _SLOT_START[slot]
        dur_h = float(attr.get("estimated_duration_hours", 2.0))
        end_h = start.hour + int(dur_h)
        end_m = start.minute + int((dur_h % 1) * 60)
        if end_m >= 60:
            end_h += 1
            end_m -= 60
        end_h = min(end_h, _SLOT_END[slot].hour)
        end = time(end_h, end_m)

        return ItineraryActivity(
            time_slot=slot,
            start_time=start,
            end_time=end,
            attraction_id=attr.get("id"),
            title=attr.get("name", "Activity"),
            description=attr.get(
                "description", f"Visit {attr.get('name', 'this attraction')}."
            ),
            location_name=attr.get("name", ""),
            estimated_cost_usd=float(attr.get("entry_price_usd") or 0.0),
            notes=(
                f"Rating: {attr.get('rating', 'N/A')}/5 · "
                f"Est. {dur_h:.0f}h · "
                f"{attr.get('address', '')}"
            ),
        )

    # ── flight / hotel helpers ────────────────────────────────────────────────

    def _pick_flights(
        self,
    ) -> tuple[FlightOption | None, FlightOption | None]:
        if not self.flights:
            return None, None
        try:
            cheapest = min(self.flights, key=lambda f: f.get("total_price_usd", 9999))
            outbound = self._dict_to_flight(cheapest)
            return outbound, None
        except Exception as exc:
            logger.warning("Could not parse flight: %s", exc)
            return None, None

    def _dict_to_flight(self, d: dict[str, Any]) -> FlightOption | None:
        try:
            segs = [
                FlightSegment(
                    departure_airport=s.get("departure_airport", ""),
                    arrival_airport=s.get("arrival_airport", ""),
                    departure_time=datetime.fromisoformat(str(s["departure_time"])),
                    arrival_time=datetime.fromisoformat(str(s["arrival_time"])),
                    airline=s.get("airline", ""),
                    flight_number=s.get("flight_number", ""),
                    duration_minutes=int(s.get("duration_minutes", 0)),
                )
                for s in d.get("segments", [])
            ]
            return FlightOption(
                id=d.get("id", str(uuid.uuid4())),
                segments=segs,
                total_price_usd=float(d["total_price_usd"]),
                currency=d.get("currency", "USD"),
                cabin_class=d.get("cabin_class", "Economy"),
                amadeus_offer_id=d.get("amadeus_offer_id"),
            )
        except Exception as exc:
            logger.warning("FlightOption parse failed: %s", exc)
            return None

    def _pick_hotel(self) -> HotelOption | None:
        if not self.hotels:
            return None
        try:
            top = self.hotels[0]
            loc = top.get("location") or {}
            return HotelOption(
                id=top.get("id", str(uuid.uuid4())),
                name=top.get("name", "Hotel"),
                star_rating=top.get("star_rating"),
                price_per_night_usd=float(top.get("price_per_night_usd", 0)),
                total_price_usd=float(top.get("total_price_usd", 0)),
                check_in=self.start_date,
                check_out=self.start_date + timedelta(days=self.duration - 1),
                location=GeoLocation(
                    latitude=float(loc.get("latitude", 0)),
                    longitude=float(loc.get("longitude", 0)),
                ),
                address=top.get("address", ""),
                amenities=top.get("amenities", []),
                review_score=top.get("review_score"),
                review_count=top.get("review_count"),
                booking_url=top.get("booking_url"),
            )
        except Exception as exc:
            logger.warning("HotelOption parse failed: %s", exc)
            return None

    def _hotel_name(self) -> str:
        if self.hotels:
            return self.hotels[0].get("name", f"Hotel in {self.destination}")
        return f"Hotel in {self.destination}"

    # ── cost computation ──────────────────────────────────────────────────────

    def _compute_total_cost(
        self,
        days: list[DayPlan],
        flight: FlightOption | None,
        hotel: HotelOption | None,
    ) -> float:
        activities_cost = sum(
            act.estimated_cost_usd for day in days for act in day.activities
        )
        flight_cost = flight.total_price_usd if flight else 0.0
        hotel_cost = hotel.total_price_usd if hotel else 0.0
        return round(activities_cost + flight_cost + hotel_cost, 2)

    def _daily_budget(self, activities: list[ItineraryActivity]) -> float:
        return round(sum(a.estimated_cost_usd for a in activities), 2)

    def _meal_cost(self) -> float:
        base = {"budget": 15.0, "moderate": 35.0, "luxury": 80.0}
        return base.get(str(self.prefs.get("travel_style", "moderate")), 35.0)

    # ── misc helpers ──────────────────────────────────────────────────────────

    def _day_theme(self, day_num: int) -> str:
        themes = {
            "city_tour": [
                "Iconic Landmarks",
                "Museums & Culture",
                "Neighbourhoods & Shopping",
                "Hidden Gems",
                "Art & Architecture",
                "Food & Markets",
            ],
            "beach": [
                "Beach & Sea",
                "Water Sports",
                "Coastal Villages",
                "Sunset & Relaxation",
                "Island Hopping",
            ],
            "adventure": [
                "Mountain Trails",
                "Wildlife & Nature",
                "River & Canyons",
                "High Altitude",
                "Forest & Waterfalls",
            ],
        }
        pool = themes.get(self.trip_type, themes["city_tour"])
        return pool[(day_num - 2) % len(pool)]

    def _format_weather(self, w: dict[str, Any]) -> str:
        desc = w.get("description", "")
        tmax = w.get("temp_max", "")
        tmin = w.get("temp_min", "")
        if tmax and tmin:
            return f"{desc} · {tmin}°–{tmax}°C"
        return desc


# ── opening-hours parsing helpers ─────────────────────────────────────────────


def _parse_hours_range(s: str) -> tuple[str, str]:
    """Split '09:00-18:00' or '9 AM - 6 PM' into (open, close) strings."""
    for sep in (" - ", "-", "–", " to "):
        if sep in s:
            parts = s.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    raise ValueError(f"Cannot parse hours range: {s!r}")


def _parse_time_str(s: str) -> time:
    """Parse '09:00', '9:00 AM', '9 AM' etc. → time object."""
    s = s.strip().upper()
    for fmt in ("%H:%M", "%I:%M %p", "%I %p", "%H"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse time: {s!r}")
