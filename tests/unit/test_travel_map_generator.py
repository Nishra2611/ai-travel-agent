"""
tests/unit/test_travel_map_generator.py — Week 13

day_color and _popup_html are pure functions and always run. The
full build_travel_map render tests use pytest.importorskip("folium") so
this file stays runnable (and honest about what it did/didn't verify) in
environments where folium hasn't been installed yet -- same principle as
the safe-fallback pattern elsewhere: missing an optional dependency should
degrade what gets tested, not error the whole suite.
"""

from __future__ import annotations

import pytest

from ai_travel_agent.maps.travel_map_generator import (
    DAY_COLORS,
    MapActivity,
    MapHotel,
    _popup_html,
    day_color,
)


def test_day_color_matches_roadmap_order():
    assert day_color(0) == "blue"
    assert day_color(1) == "green"


def test_day_color_cycles_past_palette_length():
    assert day_color(len(DAY_COLORS)) == day_color(0)
    assert day_color(len(DAY_COLORS) + 1) == day_color(1)


def test_popup_html_includes_all_provided_fields():
    activity = MapActivity(
        id="a1",
        name="Eiffel Tower",
        latitude=48.85,
        longitude=2.29,
        time_slot="9:00 AM",
        cost=20.0,
        category="attraction",
    )
    html = _popup_html(activity, "Day 1")
    assert "Eiffel Tower" in html
    assert "Day 1" in html
    assert "9:00 AM" in html
    assert "attraction" in html
    assert "$20" in html


def test_popup_html_omits_missing_optional_fields():
    activity = MapActivity(id="a1", name="Mystery Spot", latitude=0, longitude=0)
    html = _popup_html(activity, "Day 2")
    assert "Mystery Spot" in html
    assert "Cost:" not in html
    assert "Category:" not in html


# ---------------------------------------------------------------------------
# Folium-dependent tests -- skipped automatically if folium isn't installed.
# ---------------------------------------------------------------------------
folium = pytest.importorskip("folium")


def test_build_travel_map_writes_html_file(tmp_path):
    from ai_travel_agent.maps.travel_map_generator import build_travel_map

    hotel = MapHotel(id="h1", name="Hotel A", latitude=48.8629, longitude=2.3355)
    days = [
        [
            MapActivity(
                id="a1", name="Eiffel Tower", latitude=48.8584, longitude=2.2945
            ),
            MapActivity(id="a2", name="Louvre", latitude=48.8606, longitude=2.3376),
        ]
    ]

    output_path = tmp_path / "map.html"
    result_path = build_travel_map(hotel, days, output_path, animate=True)

    assert result_path.exists()
    html = result_path.read_text()
    assert "Eiffel Tower" in html
    assert "day-reveal-controls" in html  # animation control panel injected


def test_build_travel_map_without_animation_omits_controls(tmp_path):
    from ai_travel_agent.maps.travel_map_generator import build_travel_map

    hotel = MapHotel(id="h1", name="Hotel A", latitude=48.8629, longitude=2.3355)
    days = [
        [MapActivity(id="a1", name="Eiffel Tower", latitude=48.8584, longitude=2.2945)]
    ]

    output_path = tmp_path / "map_no_anim.html"
    result_path = build_travel_map(hotel, days, output_path, animate=False)

    html = result_path.read_text()
    assert "day-reveal-controls" not in html


def test_build_travel_map_handles_empty_day():
    """A day with zero geocoded activities shouldn't crash the whole map --
    it just contributes no polyline/pins for that day."""
    import tempfile

    from ai_travel_agent.maps.travel_map_generator import build_travel_map

    hotel = MapHotel(id="h1", name="Hotel A", latitude=48.8629, longitude=2.3355)
    days = [
        [],
        [MapActivity(id="a1", name="Eiffel Tower", latitude=48.8584, longitude=2.2945)],
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        result_path = build_travel_map(hotel, days, f"{tmpdir}/map.html")
        assert result_path.exists()
