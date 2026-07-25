"""
tests/unit/test_build_pdf_node.py — Week 14

Tests generate_pdf's state plumbing and context assembly, mocking
_PDFGenerator.build so this suite doesn't require WeasyPrint. Also
verifies _build_pdf_context and _resolve_map_share_url directly, since
those are where most of the real logic (pulling budget rows out of
allocation + actual spend, building the executive summary, deciding the QR
target) actually lives.
"""

from __future__ import annotations

from unittest.mock import patch

from ai_travel_agent.agents.nodes import (
    _build_executive_summary,
    _build_pdf_context,
    _resolve_map_share_url,
    generate_pdf,
)


def _make_state():
    return {
        "preferences": {"destination_city": "Paris", "trip_dates": "July 10-15, 2026"},
        "itinerary": {
            "days": [
                {
                    "activities": [
                        {
                            "id": "a1",
                            "name": "Eiffel Tower",
                            "time_slot": "9:00 AM",
                            "cost": 20.0,
                        }
                    ]
                },
            ]
        },
        "budget_allocation": {
            "total_budget": 3000.0,
            "profile": "mid_range",
            "allocations": {"flights": {"amount": 840.0, "percentage": 0.28}},
        },
        "budget_adherence": {"overall_score": 87.5, "verdict": "good_adherence"},
        "flights": [{"price": 700.0}],
        "hotels": [{"price_per_night": 150.0, "nights": 5}],
        "map_output": {
            "html_path": "outputs/maps/travel_map.html",
            "thumbnail_path": "outputs/maps/thumb.png",
        },
    }


def test_build_pdf_context_produces_valid_context():
    context = _build_pdf_context(_make_state())
    assert context.destination == "Paris"
    assert context.num_days == 1
    assert context.total_budget == 3000.0
    assert any(
        row.category == "Flights" and row.allocated == 840.0
        for row in context.budget_rows
    )
    assert context.map_thumbnail_path == "outputs/maps/thumb.png"


def test_build_executive_summary_includes_adherence_when_present():
    summary = _build_executive_summary(
        "Paris",
        5,
        {"profile": "mid_range"},
        {"overall_score": 87.5, "verdict": "good_adherence"},
    )
    assert "5-day" in summary
    assert "Paris" in summary
    assert "87.5" in summary
    assert "good adherence" in summary


def test_build_executive_summary_omits_adherence_when_absent():
    summary = _build_executive_summary("Paris", 5, {"profile": "backpacker"}, {})
    assert "5-day" in summary
    assert "score" not in summary.lower()


def test_resolve_map_share_url_uses_public_base_when_set(monkeypatch):
    monkeypatch.setenv("PUBLIC_MAP_BASE_URL", "https://example.com/maps")
    url = _resolve_map_share_url("outputs/maps/travel_map.html")
    assert url == "https://example.com/maps/travel_map.html"


def test_resolve_map_share_url_falls_back_to_file_uri_without_public_base(monkeypatch):
    monkeypatch.delenv("PUBLIC_MAP_BASE_URL", raising=False)
    url = _resolve_map_share_url("outputs/maps/travel_map.html")
    assert url.startswith("file://")


def test_generate_pdf_returns_none_without_itinerary():
    result = generate_pdf({})
    assert result["pdf_output"] is None


def test_generate_pdf_reports_generated_status_on_success():
    state = _make_state()
    with patch("ai_travel_agent.agents.nodes._pdf_generator") as mock_generator:
        mock_generator.build.return_value = "outputs/pdf/itinerary.pdf"
        result = generate_pdf(state)

        assert mock_generator.build.called
        assert result["pdf_output"]["status"] == "generated"
        assert result["pdf_output"]["pdf_path"] == "outputs/pdf/itinerary.pdf"
        assert result["pdf_output"]["error"] is None


def test_generate_pdf_reports_failed_status_without_crashing():
    from ai_travel_agent.pdf.pdf_generator import PDFGenerationError

    state = _make_state()
    with patch("ai_travel_agent.agents.nodes._pdf_generator") as mock_generator:
        mock_generator.build.side_effect = PDFGenerationError("weasyprint missing")
        result = generate_pdf(state)

        assert result["pdf_output"]["status"] == "failed"
        assert result["pdf_output"]["pdf_path"] is None
        assert "weasyprint missing" in result["pdf_output"]["error"]


def test_generate_pdf_never_raises_on_empty_state():
    result = generate_pdf({})
    assert result["pdf_output"] is None
