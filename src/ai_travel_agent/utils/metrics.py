"""
ai_travel_agent/utils/metrics.py — Week 19

Self-hosted observability (Prometheus + Grafana) since there's no
LangSmith key in .env and the LLM calls are local Ollama, not a
hosted Claude/OpenAI endpoint LangSmith would trace.

Two layers:
  1. HTTP-level metrics (automatic, zero code changes elsewhere) via
     prometheus-fastapi-instrumentator — request count, latency,
     in-progress requests, per-route.
  2. LangGraph node-level metrics (planning_duration_seconds,
     tool_error_rate) — call `record_node_result()` from the one place
     that already sees every node as it streams: `_stream_graph` in
     api/main.py (see WEEK17_18_19_GUIDE.md for the exact patch).

Add to pyproject.toml:
    prometheus-fastapi-instrumentator = ">=7.0.0,<8.0.0"
    prometheus-client = ">=0.20.0,<1.0.0"
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ── HTTP-level (automatic) ───────────────────────────────────────────────


def instrument_app(app) -> None:
    """Call once in api/main.py: Instrumentator().instrument(app).expose(app)
    equivalent, wrapped so main.py only needs one import."""
    Instrumentator().instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )


# ── LangGraph node-level (manual, called from _stream_graph) ────────────

planning_duration_seconds = Histogram(
    "planning_duration_seconds",
    "Wall-clock time for a full /plan or /ws/plan run, start to finish",
    buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300),
)

node_duration_seconds = Histogram(
    "node_duration_seconds",
    "Time spent in a single LangGraph node",
    labelnames=("node_name",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

tool_error_total = Counter(
    "tool_error_total",
    "Count of node/tool executions that raised or returned an error status",
    labelnames=("node_name",),
)

tool_call_total = Counter(
    "tool_call_total",
    "Count of node/tool executions, success or failure",
    labelnames=("node_name",),
)

budget_accuracy_pct = Histogram(
    "budget_accuracy_pct",
    "abs(total_cost_usd - budget_usd) / budget_usd * 100 for completed plans",
    buckets=(1, 2, 5, 10, 15, 20, 30, 50, 100),
)

ollama_request_seconds = Histogram(
    "ollama_request_seconds",
    "Latency of a single Ollama /api/generate call",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)


@contextmanager
def time_node(node_name: str):
    """Wrap a single node's execution during streaming:
    with time_node(node_name):
        ... process node_output ...
    """
    start = time.perf_counter()
    error = False
    try:
        yield
    except Exception:
        error = True
        raise
    finally:
        node_duration_seconds.labels(node_name=node_name).observe(
            time.perf_counter() - start
        )
        tool_call_total.labels(node_name=node_name).inc()
        if error:
            tool_error_total.labels(node_name=node_name).inc()


def record_node_result(node_name: str, node_output: dict) -> None:
    """Call this for chunks that don't raise but carry an internal error
    status (your nodes.py convention, if any — adjust the key check below
    to match how handle_error/error states are represented in state.py)."""
    if isinstance(node_output, dict) and node_output.get("status") == "error":
        tool_error_total.labels(node_name=node_name).inc()


def record_budget_accuracy(total_cost_usd: float, budget_usd: float | None) -> None:
    if budget_usd:
        budget_accuracy_pct.observe(abs(total_cost_usd - budget_usd) / budget_usd * 100)
