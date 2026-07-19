"""
Week 12 - Failure Analysis + Dashboard

Reads baseline_results.csv, identifies top 5 failure modes,
writes improvement tasks, and generates CSV export + HTML report.

Usage:
    poetry run python tests/evaluation/dashboard.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from ai_travel_agent.evaluation.rubric import DIMENSIONS

RESULTS_CSV = Path(__file__).parent / "baseline_results.csv"
REPORT_HTML = Path(__file__).parent / "evaluation_report.html"
FAILURE_JSON = Path(__file__).parent / "failure_analysis.json"


def load_results() -> list[dict]:
    if not RESULTS_CSV.exists():
        print(f"ERROR: {RESULTS_CSV} not found. Run run_baseline.py first.")
        sys.exit(1)
    with RESULTS_CSV.open() as f:
        return list(csv.DictReader(f))


def avg_scores(rows: list[dict]) -> dict[str, float]:
    totals: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for row in rows:
        for dim in DIMENSIONS:
            try:
                totals[dim].append(float(row[dim]))
            except (ValueError, KeyError):
                pass
    return {
        d: round(sum(v) / len(v), 2) if v else 0.0
        for d, v in totals.items()
    }


def avg_scores_by_category(rows: list[dict]) -> dict[str, dict[str, float]]:
    by_cat: dict[str, list[dict]] = {}
    for row in rows:
        cat = row.get("category", "unknown")
        by_cat.setdefault(cat, []).append(row)
    return {cat: avg_scores(cat_rows) for cat, cat_rows in by_cat.items()}


IMPROVEMENT_TASKS = {
    "feasibility": "Tighten opening-hours validation in ItineraryBuilder; add a pre-flight check that rejects activities outside their open window before scheduling.",
    "budget_accuracy": "Improve cost estimation for restaurants and transport; add a post-build budget reconciliation pass that trims activities until within 5% of budget.",
    "geo_efficiency": "Strengthen cluster-to-day assignment so build_itinerary always picks activities from the same DBSCAN cluster for a given day.",
    "weather_match": "Extend WeatherScheduler lookahead from 2 to 4 days and add a fallback indoor activity pool for destinations with limited indoor options.",
    "completeness": "Ensure every day has at least one morning, one afternoon, and one evening slot filled; add a gap-filler pass after conflict resolution.",
    "priority_adherence": "Increase backtrack cap from 20 to 50 for trips with many must-sees; add a pre-check that aborts if must-sees alone exceed the budget.",
    "walking_balance": "Lower BALANCE_VARIANCE_THRESHOLD from 0.30 to 0.20 and run two rebalancing passes instead of one.",
    "time_realism": "Pull estimated_duration_hours from Google Places API instead of using the 2h default; add a 15-min buffer between every consecutive activity.",
    "activity_diversity": "Add a diversity constraint to _pick_from_pool: no more than 2 activities of the same category per day.",
    "preference_match": "Pass activity_types and travel_style from preferences into the cluster-to-day assignment so preferred categories are prioritised in slot selection.",
}


def top_failures(avgs: dict[str, float], n: int = 5) -> list[tuple[str, float]]:
    return sorted(avgs.items(), key=lambda x: x[1])[:n]


def build_html(
    rows: list[dict],
    avgs: dict[str, float],
    cat_avgs: dict[str, dict[str, float]],
    failures: list[tuple[str, float]],
) -> str:
    dim_bars = "\n".join(
        f'<tr><td>{d}</td>'
        f'<td><div class="bar" style="width:{avgs[d]/5*100:.0f}%"></div></td>'
        f'<td>{avgs[d]:.2f}</td></tr>'
        for d in DIMENSIONS
    )

    cat_headers = "".join(f"<th>{c}</th>" for c in cat_avgs)
    cat_rows = "\n".join(
        f'<tr><td>{d}</td>'
        + "".join(f'<td>{cat_avgs[c].get(d, 0):.2f}</td>' for c in cat_avgs)
        + "</tr>"
        for d in DIMENSIONS
    )

    failure_rows = "\n".join(
        f'<tr><td>{rank}</td><td>{dim}</td><td>{score:.2f}</td>'
        f'<td>{IMPROVEMENT_TASKS.get(dim, "")}</td></tr>'
        for rank, (dim, score) in enumerate(failures, 1)
    )

    scenario_rows = "\n".join(
        f'<tr><td>{r["id"]}</td><td>{r["category"]}</td><td>{r["destination"]}</td>'
        f'<td>{r["duration_days"]}</td><td>${r["budget_usd"]}</td>'
        f'<td>{r["planning_time_ms"]}</td>'
        + "".join(f'<td>{r.get(d, "")}</td>' for d in DIMENSIONS)
        + "</tr>"
        for r in rows
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Travel Agent - Week 12 Evaluation Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; }}
  h1 {{ color: #1a5276; }}
  h2 {{ color: #2874a6; border-bottom: 1px solid #aed6f1; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; font-size: 0.85rem; }}
  th, td {{ border: 1px solid #d5d8dc; padding: 6px 10px; text-align: left; }}
  th {{ background: #2874a6; color: white; }}
  tr:nth-child(even) {{ background: #f2f3f4; }}
  .bar {{ background: #2874a6; height: 14px; border-radius: 3px; min-width: 2px; }}
  .failure {{ background: #fdf2f8; }}
</style>
</head>
<body>
<h1>AI Travel Agent - Week 12 Evaluation Report</h1>
<p>Baseline metrics across {len(rows)} scenarios | {len(DIMENSIONS)} evaluation dimensions</p>

<h2>Average Score per Dimension</h2>
<table>
  <tr><th>Dimension</th><th>Score (out of 5)</th><th>Avg</th></tr>
  {dim_bars}
</table>

<h2>Average Score by Trip Category</h2>
<table>
  <tr><th>Dimension</th>{cat_headers}</tr>
  {cat_rows}
</table>

<h2>Top 5 Failure Modes</h2>
<table class="failure">
  <tr><th>#</th><th>Dimension</th><th>Avg Score</th><th>Improvement Task</th></tr>
  {failure_rows}
</table>

<h2>All Scenario Results</h2>
<table>
  <tr>
    <th>ID</th><th>Category</th><th>Destination</th><th>Days</th><th>Budget</th>
    <th>Plan ms</th>
    {"".join(f"<th>{d[:6]}</th>" for d in DIMENSIONS)}
  </tr>
  {scenario_rows}
</table>
</body>
</html>"""


def main() -> None:
    rows = load_results()
    avgs = avg_scores(rows)
    cat_avgs = avg_scores_by_category(rows)
    failures = top_failures(avgs)

    print("\n=== Average Scores per Dimension ===")
    for dim, score in sorted(avgs.items(), key=lambda x: x[1]):
        bar = "=" * int(score * 4)
        print(f"  {dim:<22} {score:.2f}  {bar}")

    print("\n=== Top 5 Failure Modes ===")
    for rank, (dim, score) in enumerate(failures, 1):
        print(f"  {rank}. {dim} (avg={score:.2f}): {IMPROVEMENT_TASKS.get(dim, '')[:80]}")

    failure_data = [
        {
            "rank": rank,
            "dimension": dim,
            "avg_score": score,
            "improvement_task": IMPROVEMENT_TASKS.get(dim, ""),
        }
        for rank, (dim, score) in enumerate(failures, 1)
    ]
    FAILURE_JSON.write_text(json.dumps(failure_data, indent=2))
    print(f"\nFailure analysis saved to {FAILURE_JSON}")

    html = build_html(rows, avgs, cat_avgs, failures)
    REPORT_HTML.write_text(html)
    print(f"HTML report saved to {REPORT_HTML}")


if __name__ == "__main__":
    main()
