"""
scripts/demo_map_generator.py — Week 13

Exercises build_travel_map + render_thumbnail_safe directly against the
mock Paris fixture, no graph/LangChain involved. Requires `poetry add
folium` and `playwright install chromium` to actually render (this script
degrades gracefully and tells you which piece is missing if not).

Run: poetry run python scripts/demo_map_generator.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_travel_agent.maps.thumbnail_renderer import render_thumbnail_safe
from ai_travel_agent.maps.travel_map_generator import (
    MapActivity,
    MapHotel,
    build_travel_map,
)

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "paris_pois.json"
OUTPUT_HTML = Path(__file__).parent.parent / "outputs" / "maps" / "demo_travel_map.html"
OUTPUT_PNG = (
    Path(__file__).parent.parent / "outputs" / "maps" / "demo_travel_map_thumb.png"
)


def main() -> None:
    data = json.loads(FIXTURE.read_text())
    hotels = [p for p in data["points"] if p.get("category") == "hotel"]
    attractions = [p for p in data["points"] if p.get("category") == "attraction"]

    hotel = MapHotel(
        id=hotels[0]["id"],
        name=hotels[0]["name"],
        latitude=hotels[0]["latitude"],
        longitude=hotels[0]["longitude"],
    )

    # Split attractions into 3 fake "days" just for the demo.
    days = [
        [
            MapActivity(
                id=p["id"],
                name=p["name"],
                latitude=p["latitude"],
                longitude=p["longitude"],
                time_slot="10:00 AM",
                cost=15.0,
                category="attraction",
            )
            for p in attractions[i::3]
        ]
        for i in range(3)
    ]

    try:
        html_path = build_travel_map(hotel, days, OUTPUT_HTML, animate=True)
        print(f"Map written to {html_path}")
    except ImportError:
        print("folium isn't installed -- run `poetry add folium` to render the map.")
        return

    thumb_path = render_thumbnail_safe(html_path, OUTPUT_PNG)
    if thumb_path:
        print(f"Thumbnail written to {thumb_path}")
    else:
        print(
            "Thumbnail rendering skipped/failed -- check playwright install chromium was run."
        )


if __name__ == "__main__":
    main()
