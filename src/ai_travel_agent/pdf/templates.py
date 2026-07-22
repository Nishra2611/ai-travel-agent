"""
ai_travel_agent/pdf/templates.py — Week 14

HTML/CSS templates for the PDF itinerary, rendered with Jinja2 and handed
to WeasyPrint (pdf_generator.py) as a single HTML string. Deliberately
separated from pdf_generator.py: rendering the template to an HTML string
has zero WeasyPrint dependency, so render_itinerary_html can be (and is,
see tests/unit/test_templates.py) unit-tested without WeasyPrint installed
at all -- the same "keep the testable part dependency-light" instinct
behind every _Builder/_Optimizer class in this project, just applied to a
templating step instead of an algorithm.

CSS here targets WeasyPrint's supported subset (CSS 2.1 plus most of
Paged Media / GCPM: @page, page-break-*, running headers) rather than
assuming full browser CSS support -- flexbox and grid are only partially
supported by WeasyPrint as of this writing, so layout below leans on
floats/tables/block flow, which render identically in WeasyPrint and in a
browser if you want to preview the HTML directly during development.

Drop this file at: ai_travel_agent/pdf/templates.py
"""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment

_ENV = Environment(autoescape=True)

_BASE_CSS = """
@page {
  size: A4;
  margin: 2cm 1.8cm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 9px; color: #888; }
}
body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #222; font-size: 11pt; margin: 0; }
h1 { font-size: 26pt; margin: 0 0 4px 0; }
h2 { font-size: 16pt; border-bottom: 2px solid #3388ff; padding-bottom: 4px; margin-top: 28px; }
h3 { font-size: 13pt; color: #3388ff; margin-bottom: 4px; }
.cover-page { page-break-after: always; text-align: center; padding-top: 30%; }
.cover-photo { width: 100%; max-height: 320px; object-fit: cover; border-radius: 8px; margin-bottom: 24px; }
.subtitle { color: #666; font-size: 13pt; margin-top: 6px; }
.day-section { page-break-inside: avoid; margin-bottom: 20px; }
.activity-row { padding: 6px 0; border-bottom: 1px solid #eee; }
.activity-time { color: #888; font-size: 9pt; width: 70px; display: inline-block; }
.activity-name { font-weight: bold; }
.activity-cost { float: right; color: #444; }
table.budget-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
table.budget-table th { background: #3388ff; color: white; text-align: left; padding: 6px 10px; font-size: 9pt; }
table.budget-table td { padding: 6px 10px; border-bottom: 1px solid #eee; font-size: 10pt; }
table.budget-table tr.total-row td { font-weight: bold; border-top: 2px solid #222; }
.map-section { page-break-inside: avoid; text-align: center; margin-top: 20px; }
.map-thumbnail { width: 100%; max-width: 500px; border: 1px solid #ddd; border-radius: 6px; }
.qr-code { width: 90px; height: 90px; margin-top: 8px; }
.exec-summary-box { background: #f4f8ff; border-left: 4px solid #3388ff; padding: 14px 18px; margin-top: 10px; }
"""

_MASTER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>{{ css }}</style></head>
<body>

<div class="cover-page">
  {% if cover_photo_path %}
  <img class="cover-photo" src="{{ cover_photo_path }}">
  {% endif %}
  <h1>{{ destination }}</h1>
  <div class="subtitle">{{ trip_dates }} &middot; {{ num_days }} day{{ 's' if num_days != 1 else '' }}</div>
</div>

<h2>Trip Summary</h2>
<div class="exec-summary-box">
  <p>{{ executive_summary }}</p>
  <p><b>Total budget:</b> ${{ "%.0f"|format(total_budget) }} &middot;
     <b>Total planned spend:</b> ${{ "%.0f"|format(total_spent) }}
     {% if budget_verdict %} &middot; <b>Adherence:</b> {{ budget_verdict }}{% endif %}
  </p>
</div>

{% for day in days %}
<div class="day-section">
  <h3>Day {{ day.day_number }}{% if day.date %} &middot; {{ day.date }}{% endif %}</h3>
  {% for activity in day.activities %}
  <div class="activity-row">
    {% if activity.time_slot %}<span class="activity-time">{{ activity.time_slot }}</span>{% endif %}
    <span class="activity-name">{{ activity.name }}</span>
    {% if activity.cost is not none %}<span class="activity-cost">${{ "%.0f"|format(activity.cost) }}</span>{% endif %}
  </div>
  {% endfor %}
</div>
{% endfor %}

<h2>Budget Breakdown</h2>
<table class="budget-table">
  <tr><th>Category</th><th>Allocated</th><th>Spent</th></tr>
  {% for row in budget_rows %}
  <tr><td>{{ row.category }}</td><td>${{ "%.0f"|format(row.allocated) }}</td><td>${{ "%.0f"|format(row.spent) }}</td></tr>
  {% endfor %}
  <tr class="total-row"><td>Total</td><td>${{ "%.0f"|format(total_budget) }}</td><td>${{ "%.0f"|format(total_spent) }}</td></tr>
</table>

{% if map_thumbnail_path or qr_code_path %}
<div class="map-section">
  <h2>Interactive Map</h2>
  {% if map_thumbnail_path %}<img class="map-thumbnail" src="{{ map_thumbnail_path }}">{% endif %}
  {% if qr_code_path %}
  <div><img class="qr-code" src="{{ qr_code_path }}"><br><small>Scan for the interactive map</small></div>
  {% endif %}
</div>
{% endif %}

</body>
</html>
"""

_master_template = _ENV.from_string(_MASTER_TEMPLATE)


@dataclass
class BudgetRow:
    category: str
    allocated: float
    spent: float


@dataclass
class DayActivity:
    name: str
    time_slot: str | None = None
    cost: float | None = None


@dataclass
class DayPlan:
    day_number: int
    activities: list[DayActivity]
    date: str | None = None


@dataclass
class PDFContext:
    destination: str
    trip_dates: str
    executive_summary: str
    days: list[DayPlan]
    budget_rows: list[BudgetRow]
    total_budget: float
    total_spent: float
    budget_verdict: str | None = None
    cover_photo_path: str | None = None
    map_thumbnail_path: str | None = None
    qr_code_path: str | None = None

    @property
    def num_days(self) -> int:
        return len(self.days)

    def as_template_dict(self) -> dict:
        return {
            "css": _BASE_CSS,
            "destination": self.destination,
            "trip_dates": self.trip_dates,
            "num_days": self.num_days,
            "executive_summary": self.executive_summary,
            "days": [
                {
                    "day_number": d.day_number,
                    "date": d.date,
                    "activities": [
                        {"name": a.name, "time_slot": a.time_slot, "cost": a.cost}
                        for a in d.activities
                    ],
                }
                for d in self.days
            ],
            "budget_rows": [
                {"category": r.category, "allocated": r.allocated, "spent": r.spent}
                for r in self.budget_rows
            ],
            "total_budget": self.total_budget,
            "total_spent": self.total_spent,
            "budget_verdict": self.budget_verdict,
            "cover_photo_path": self.cover_photo_path,
            "map_thumbnail_path": self.map_thumbnail_path,
            "qr_code_path": self.qr_code_path,
        }


def render_itinerary_html(context: PDFContext) -> str:
    """Pure Jinja2 rendering, zero WeasyPrint/network dependency -- fully
    unit-testable on its own (see test_templates.py)."""
    return _master_template.render(**context.as_template_dict())
