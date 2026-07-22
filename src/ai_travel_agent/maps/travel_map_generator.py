"""
ai_travel_agent/maps/travel_map_generator.py — Week 13

Builds the interactive Folium map: hotel pin, day-colored attraction pins
with popup cards, per-day route polylines (using Week 10's optimized
activity order when present), marker clustering for the zoomed-out view,
and a JS-powered day-by-day reveal animation.

Architectural note, consistent with geo_visualizer.py (Week 9): this module
is a rendering/file-write helper, not a deterministic-computation engine
like _BudgetOptimizer or _RouteOptimizer. There's very little here that
benefits from the "zero dependencies, unit-test directly" treatment,
because there's no optimization problem to get right or wrong -- it's
translating already-computed data (itinerary, route order) into HTML/JS.
The one piece of real logic (which color belongs to which day) is pulled
out into a standalone pure function, `day_color`, specifically so it can be
unit-tested without needing folium installed.

Drop this file at: ai_travel_agent/maps/travel_map_generator.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_travel_agent.utils.logger import get_logger

logger = get_logger(__name__)

# Folium's built-in named icon colors, in the exact order the roadmap asks
# for (Day 1 = blue, Day 2 = green, ...). Cycles if a trip somehow has more
# days than colors.
DAY_COLORS: list[str] = [
    "blue",
    "green",
    "red",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
    "pink",
    "darkblue",
]

HOTEL_ICON_COLOR = "black"
HOTEL_ICON_SYMBOL = "home"
DEFAULT_ZOOM_START = 13
CLUSTER_RADIUS = 60  # px; how aggressively nearby pins merge when zoomed out


def day_color(day_index: int) -> str:
    """0-indexed day -> Folium color name. Pure function, no folium import
    needed, so this is testable without the dependency installed."""
    return DAY_COLORS[day_index % len(DAY_COLORS)]


@dataclass
class MapActivity:
    id: str
    name: str
    latitude: float
    longitude: float
    time_slot: str | None = None
    cost: float | None = None
    category: str | None = None


@dataclass
class MapHotel:
    id: str
    name: str
    latitude: float
    longitude: float


def _popup_html(activity: MapActivity, day_label: str) -> str:
    """Builds the popup info-card HTML. Pure string building, no folium
    dependency, testable in isolation."""
    lines = [f"<b>{activity.name}</b><br>", f"<i>{day_label}</i><br>"]
    if activity.time_slot:
        lines.append(f"Time: {activity.time_slot}<br>")
    if activity.category:
        lines.append(f"Category: {activity.category}<br>")
    if activity.cost is not None:
        lines.append(f"Cost: ${activity.cost:.0f}<br>")
    return (
        f'<div style="font-family: sans-serif; font-size: 13px;">{"".join(lines)}</div>'
    )


def build_travel_map(
    hotel: MapHotel,
    days: list[list[MapActivity]],
    output_path: str | Path,
    animate: bool = True,
) -> Path:
    """
    Renders the full interactive map and saves it as a self-contained-ish
    HTML file (Folium/Leaflet load their JS/CSS from a CDN by default --
    see the module-level note below on what "self-contained" means here).

    days is a list of per-day activity lists, already in the order
    optimize_routes (Week 10) settled on -- this function draws exactly the
    order it's given, it doesn't re-optimize anything.
    """
    import folium
    from folium.plugins import MarkerCluster

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fmap = folium.Map(
        location=[hotel.latitude, hotel.longitude],
        zoom_start=DEFAULT_ZOOM_START,
        tiles="cartodbpositron",
    )

    folium.Marker(
        location=[hotel.latitude, hotel.longitude],
        icon=folium.Icon(color=HOTEL_ICON_COLOR, icon=HOTEL_ICON_SYMBOL, prefix="fa"),
        popup=folium.Popup(f"<b>{hotel.name}</b><br><i>Your hotel</i>", max_width=250),
        tooltip=hotel.name,
    ).add_to(fmap)

    cluster = MarkerCluster(
        name="All activities (clustered)", radius=CLUSTER_RADIUS
    ).add_to(fmap)
    day_feature_groups: list[Any] = []

    for day_index, activities in enumerate(days):
        color = day_color(day_index)
        day_label = f"Day {day_index + 1}"
        fg = folium.FeatureGroup(name=day_label)

        route_points = [(hotel.latitude, hotel.longitude)]
        for activity in activities:
            marker = folium.CircleMarker(
                location=[activity.latitude, activity.longitude],
                radius=8,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                popup=folium.Popup(_popup_html(activity, day_label), max_width=250),
                tooltip=activity.name,
            )
            marker.add_to(fg)
            marker.add_to(
                cluster
            )  # same marker, added to the cluster layer for zoomed-out decluttering
            route_points.append((activity.latitude, activity.longitude))
        route_points.append(
            (hotel.latitude, hotel.longitude)
        )  # end near hotel, matches Week 10's loop

        if len(activities) >= 1:
            folium.PolyLine(
                locations=route_points,
                color=color,
                weight=3,
                opacity=0.7,
                tooltip=f"{day_label} route",
            ).add_to(fg)

        fg.add_to(fmap)
        day_feature_groups.append((day_label, fg))

    folium.LayerControl(collapsed=False).add_to(fmap)

    if animate and day_feature_groups:
        _add_day_reveal_animation(fmap, day_feature_groups)

    fmap.save(str(output_path))
    logger.info(
        "travel map rendered",
        extra={"output_path": str(output_path), "num_days": len(days)},
    )
    return output_path


def _add_day_reveal_animation(
    fmap: Any, day_feature_groups: list[tuple[str, Any]]
) -> None:
    """
    Injects a small JS control panel (Play / Prev / Next) that reveals one
    day's FeatureGroup at a time. Uses each FeatureGroup's Leaflet JS
    variable name (fg.get_name()) directly in the generated <script>, which
    is why this must run after every fg.add_to(fmap) call -- get_name()
    only returns folium's real generated identifier once the group has
    actually been added to the map.

    All days start hidden except Day 1; Play steps through them on a timer,
    Prev/Next let the viewer step manually. This is plain Leaflet
    addLayer/removeLayer, no external JS animation library.
    """
    import folium

    layer_names = [fg.get_name() for _, fg in day_feature_groups]
    labels = [label for label, _ in day_feature_groups]
    map_name = fmap.get_name()

    js = f"""
    <div id="day-reveal-controls" style="
        position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: white; padding: 10px 16px; border-radius: 8px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.3); font-family: sans-serif; font-size: 13px;
        display: flex; align-items: center; gap: 10px;">
      <button id="day-prev-btn">&larr; Prev</button>
      <span id="day-label-text" style="min-width: 70px; text-align: center; font-weight: bold;">{labels[0]}</span>
      <button id="day-next-btn">Next &rarr;</button>
      <button id="day-play-btn">Play</button>
    </div>
    <script>
      (function() {{
        var layers = [{", ".join(layer_names)}];
        var labels = {labels!r};
        var currentDay = 0;
        var playTimer = null;

        function showOnly(index) {{
          for (var i = 0; i < layers.length; i++) {{
            if ({map_name}.hasLayer(layers[i])) {{ {map_name}.removeLayer(layers[i]); }}
          }}
          {map_name}.addLayer(layers[index]);
          document.getElementById('day-label-text').innerText = labels[index];
          currentDay = index;
        }}

        document.getElementById('day-prev-btn').onclick = function() {{
          showOnly((currentDay - 1 + layers.length) % layers.length);
        }};
        document.getElementById('day-next-btn').onclick = function() {{
          showOnly((currentDay + 1) % layers.length);
        }};
        document.getElementById('day-play-btn').onclick = function() {{
          if (playTimer) {{
            clearInterval(playTimer);
            playTimer = null;
            document.getElementById('day-play-btn').innerText = 'Play';
            return;
          }}
          document.getElementById('day-play-btn').innerText = 'Pause';
          playTimer = setInterval(function() {{
            showOnly((currentDay + 1) % layers.length);
          }}, 1800);
        }};

        showOnly(0);
      }})();
    </script>
    """
    fmap.get_root().html.add_child(folium.Element(js))
