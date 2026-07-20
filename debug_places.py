import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import httpx
from ai_travel_agent.utils.config import settings

key = settings.google_places_api_key
print("Key present:", bool(key), "len:", len(key) if key else 0)

resp = httpx.post(
    "https://places.googleapis.com/v1/places:searchText",
    headers={
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.formattedAddress",
    },
    json={"textQuery": "Italian restaurants in London"},
    timeout=10,
)
print("Status:", resp.status_code)
import json
data = resp.json()
places = data.get("places", [])
print("Places count:", len(places))
if places:
    print("First:", places[0].get("displayName", {}).get("text"), places[0].get("rating"))
else:
    print("Response:", json.dumps(data, indent=2)[:500])
