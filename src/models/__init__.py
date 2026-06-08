from .attraction import (
    Attraction,
    AttractionCategory,
)
from .flight import (
    FlightOption,
    FlightSegment,
)
from .hotel import (
    GeoLocation,
    HotelOption,
)
from .itinerary import (
    DayPlan,
    Itinerary,
    ItineraryActivity,
)
from .travel_preferences import (
    ActivityType,
    TravelPreferences,
    TravelStyle,
)

__all__ = [
    "TravelPreferences",
    "TravelStyle",
    "ActivityType",
    "FlightOption",
    "FlightSegment",
    "HotelOption",
    "GeoLocation",
    "Attraction",
    "AttractionCategory",
    "Itinerary",
    "DayPlan",
    "ItineraryActivity",
]
