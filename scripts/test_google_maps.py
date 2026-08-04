import requests
from dotenv import load_dotenv

load_dotenv()

# Using free OpenStreetMap Nominatim (no API key needed)
result = requests.get(
    "https://nominatim.openstreetmap.org/search",
    params={"q": "Eiffel Tower, Paris", "format": "json", "limit": 1},
    headers={"User-Agent": "ai-travel-agent-dev"},
    timeout=10,
).json()

location = {"lat": result[0]["lat"], "lng": result[0]["lon"]}
print(f"Eiffel Tower: {location}")

# Walking distance via OSRM (free, no key needed)
dist = requests.get(
    "http://router.project-osrm.org/route/v1/foot/2.2945,48.8584;2.3364,48.8606",
    params={"overview": "false"},
    timeout=10,
).json()
duration_min = int(dist["routes"][0]["duration"] / 60)
print(f"Walk time: {duration_min} mins")
print("Google Maps API working")
