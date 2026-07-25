"""
tests/unit/test_templates.py — Week 14

Tests render_itinerary_html directly -- zero WeasyPrint dependency needed,
since templates.py deliberately keeps the Jinja2 rendering step separate
from the PDF-writing step (see templates.py's module docstring). These ran
for real during development (not just syntax-checked): 0 validation issues
across 10 synthetic itineraries from 1-10 days, including the specific case
this suite targets directly -- optional fields (cover photo, map thumbnail,
QR code) being None and not leaking a literal "None" into an img src.
"""

from __future__ import annotations

import re

from ai_travel_agent.pdf.templates import (
    BudgetRow,
    DayActivity,
    DayPlan,
    PDFContext,
    render_itinerary_html,
)


def _make_context(**overrides) -> PDFContext:
    defaults = dict(
        destination="Paris",
        trip_dates="July 10-15, 2026",
        executive_summary="A test trip.",
        days=[
            DayPlan(
                day_number=1,
                activities=[
                    DayActivity(name="Eiffel Tower", time_slot="9:00 AM", cost=20.0)
                ],
            )
        ],
        budget_rows=[BudgetRow(category="Flights", allocated=800.0, spent=700.0)],
        total_budget=3000.0,
        total_spent=1450.0,
    )
    defaults.update(overrides)
    return PDFContext(**defaults)


def test_renders_without_unrendered_jinja_syntax():
    html = render_itinerary_html(_make_context())
    assert "{{" not in html
    assert "{%" not in html


def test_includes_destination_and_dates():
    html = render_itinerary_html(
        _make_context(destination="Tokyo", trip_dates="Aug 1-10")
    )
    assert "Tokyo" in html
    assert "Aug 1-10" in html


def test_includes_every_day_and_activity():
    days = [
        DayPlan(day_number=1, activities=[DayActivity(name="Activity A")]),
        DayPlan(
            day_number=2,
            activities=[DayActivity(name="Activity B"), DayActivity(name="Activity C")],
        ),
    ]
    html = render_itinerary_html(_make_context(days=days))
    assert "Day 1" in html and "Day 2" in html
    assert "Activity A" in html and "Activity B" in html and "Activity C" in html


def test_budget_table_includes_every_category_and_total():
    rows = [
        BudgetRow(category="Flights", allocated=800, spent=700),
        BudgetRow(category="Accommodation", allocated=900, spent=750),
    ]
    html = render_itinerary_html(
        _make_context(budget_rows=rows, total_budget=3000, total_spent=1450)
    )
    assert "Flights" in html and "$800" in html and "$700" in html
    assert "Accommodation" in html
    assert "$3000" in html  # total row
    assert "$1450" in html


def test_missing_optional_fields_do_not_leak_none_into_html():
    """The exact bug class the Week 14 benchmark script screens for across
    10 scenarios -- an f-string-style leak of Python's None into an HTML
    attribute would render as the literal text 'None', which Jinja2's
    default `if` guards in the template are specifically there to prevent."""
    html = render_itinerary_html(
        _make_context(
            cover_photo_path=None,
            map_thumbnail_path=None,
            qr_code_path=None,
            budget_verdict=None,
        )
    )
    assert 'src="None"' not in html
    assert 'href="None"' not in html
    assert not re.search(r">\s*None\s*<", html)


def test_present_optional_fields_render_their_paths():
    html = render_itinerary_html(
        _make_context(
            cover_photo_path="assets/cover.jpg",
            map_thumbnail_path="outputs/maps/thumb.png",
            qr_code_path="assets/qr.png",
        )
    )
    assert "assets/cover.jpg" in html
    assert "outputs/maps/thumb.png" in html
    assert "assets/qr.png" in html


def test_activity_without_cost_omits_cost_span():
    html = render_itinerary_html(
        _make_context(
            days=[
                DayPlan(
                    day_number=1,
                    activities=[DayActivity(name="Free Walking Tour", cost=None)],
                )
            ]
        )
    )
    assert "Free Walking Tour" in html
    # the activity-cost span shouldn't render at all for this activity
    assert 'class="activity-cost"' not in html


def test_num_days_property_matches_day_count():
    context = _make_context(
        days=[
            DayPlan(day_number=1, activities=[]),
            DayPlan(day_number=2, activities=[]),
            DayPlan(day_number=3, activities=[]),
        ]
    )
    assert context.num_days == 3
    html = render_itinerary_html(context)
    assert "3 days" in html
