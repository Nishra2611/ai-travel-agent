"""
scripts/demo_pdf_generator.py — Week 14

Exercises render_itinerary_html + _PDFGenerator directly, no
graph/LangChain involved. The HTML rendering step needs nothing but
Jinja2 (already a hard dependency) and always runs; the actual PDF write
needs `poetry add weasyprint` (plus its system libs -- see
pdf_generator.py's module docstring) and degrades to "HTML written,
PDF skipped" if that's not available yet.

Run: poetry run python scripts/demo_pdf_generator.py
"""

from __future__ import annotations

from pathlib import Path

from ai_travel_agent.pdf.pdf_generator import PDFGenerationError, _PDFGenerator
from ai_travel_agent.pdf.templates import (
    BudgetRow,
    DayActivity,
    DayPlan,
    PDFContext,
    render_itinerary_html,
)

OUTPUT_DIR = Path(__file__).parent.parent / "outputs" / "pdf"


def main() -> None:
    context = PDFContext(
        destination="Paris",
        trip_dates="July 10-15, 2026",
        executive_summary="A 5-day mid-range trip to Paris focused on iconic landmarks and great food.",
        days=[
            DayPlan(
                day_number=1,
                date="July 10",
                activities=[
                    DayActivity(name="Eiffel Tower", time_slot="9:00 AM", cost=20.0),
                    DayActivity(
                        name="Seine River Cruise", time_slot="2:00 PM", cost=15.0
                    ),
                ],
            ),
            DayPlan(
                day_number=2,
                date="July 11",
                activities=[
                    DayActivity(name="Louvre Museum", time_slot="10:00 AM", cost=17.0),
                ],
            ),
        ],
        budget_rows=[
            BudgetRow(category="Flights", allocated=840, spent=700),
            BudgetRow(category="Accommodation", allocated=960, spent=750),
            BudgetRow(category="Food", allocated=600, spent=310),
            BudgetRow(category="Activities", allocated=360, spent=180),
            BudgetRow(category="Transport", allocated=150, spent=90),
            BudgetRow(category="Misc", allocated=90, spent=20),
        ],
        total_budget=3000.0,
        total_spent=2050.0,
        budget_verdict="good_adherence",
    )

    html = render_itinerary_html(context)
    html_path = OUTPUT_DIR / "demo_itinerary.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html)
    print(f"HTML rendered ({len(html)} chars) -> {html_path}")
    print(
        "Open that file in a browser for a quick visual check before WeasyPrint is set up."
    )

    try:
        pdf_path = _PDFGenerator().build(context, OUTPUT_DIR / "demo_itinerary.pdf")
        print(f"PDF written -> {pdf_path}")
    except PDFGenerationError as exc:
        print(f"PDF generation skipped: {exc}")


if __name__ == "__main__":
    main()
