"""
Week 12 - Baseline Metrics Runner

Runs all 25 scenarios through the optimizer + LLM judge.
Stores results as CSV: one row per scenario, one column per dimension.

Usage:
    poetry run python tests/evaluation/run_baseline.py
    poetry run python tests/evaluation/run_baseline.py --no-anthropic
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
load_dotenv(Path(__file__).parents[2] / ".env")

from ai_travel_agent.agents.graph import build_graph
from ai_travel_agent.evaluation.judge import evaluate_itinerary
from ai_travel_agent.evaluation.rubric import DIMENSIONS

SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"
RESULTS_CSV = Path(__file__).parent / "baseline_results.csv"


def run_scenario(graph, scenario: dict) -> dict:
    t0 = time.perf_counter()
    try:
        result = graph.invoke(
            {"raw_input": scenario["request"], "status": "parse", "messages": []},
            config={"configurable": {"thread_id": f"eval_{scenario['id']}"}},
        )
        planning_time_ms = (time.perf_counter() - t0) * 1000
        itinerary = (result.get("final_output") or {}).get("itinerary") or {}
        return {"itinerary": itinerary, "planning_time_ms": planning_time_ms, "error": None}
    except Exception as exc:
        return {"itinerary": {}, "planning_time_ms": 0.0, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-anthropic", action="store_true")
    args = parser.parse_args()
    use_anthropic = not args.no_anthropic

    scenarios = json.loads(SCENARIOS_PATH.read_text())
    graph = build_graph(db_path="data/eval_checkpoints.db")

    fieldnames = (
        ["id", "category", "destination", "duration_days", "budget_usd",
         "planning_time_ms", "judge_time_ms", "error"]
        + DIMENSIONS
    )

    rows = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"[{i:02d}/{len(scenarios)}] {scenario['id']} - {scenario['request'][:60]}")

        run = run_scenario(graph, scenario)
        if run["error"]:
            print(f"  optimizer error: {run['error']}")

        eval_result = evaluate_itinerary(
            run["itinerary"],
            scenario["request"],
            use_anthropic=use_anthropic,
        )

        row: dict = {
            "id": scenario["id"],
            "category": scenario["category"],
            "destination": scenario["destination"],
            "duration_days": scenario["duration_days"],
            "budget_usd": scenario["budget_usd"],
            "planning_time_ms": round(run["planning_time_ms"], 1),
            "judge_time_ms": eval_result["planning_time_ms"],
            "error": run["error"] or eval_result.get("error") or "",
        }
        for dim in DIMENSIONS:
            score_entry = eval_result["scores"].get(dim, {})
            row[dim] = score_entry.get("score", "")

        rows.append(row)
        scores_str = " ".join(f"{d[:4]}={row.get(d, '?')}" for d in DIMENSIONS)
        print(f"  {scores_str} | plan={row['planning_time_ms']:.0f}ms")

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults saved to {RESULTS_CSV}")


if __name__ == "__main__":
    main()
