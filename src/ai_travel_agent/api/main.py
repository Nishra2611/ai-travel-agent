"""FastAPI application — Week 15: WebSocket streaming, sessions, rate limiting, background jobs."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ai_travel_agent.agents.graph import build_graph
from ai_travel_agent.evaluation.judge import evaluate_itinerary
from ai_travel_agent.tools.attraction_finder import AttractionFinderTool
from ai_travel_agent.tools.budget_tracker import BudgetTrackerTool
from ai_travel_agent.tools.dummy_tool import DummyFlightTool
from ai_travel_agent.tools.hotel_search import HotelSearchTool
from ai_travel_agent.tools.restaurant_finder import RestaurantFinderTool
from ai_travel_agent.tools.weather_checker import WeatherCheckerTool
from ai_travel_agent.utils.cache import cache


def _safe_json(obj: Any) -> Any:
    """Recursively convert any non-JSON-serializable values to strings."""
    from datetime import date, datetime
    from enum import Enum
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(i) for i in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    return str(obj)


def _build_pdf(itinerary: dict[str, Any], title: str = "Trip Itinerary") -> bytes:
    """Build a PDF from the normalized itinerary dict using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(79, 70, 229)  # accent purple
    pdf.cell(0, 12, "AI Travel Planner", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, title, ln=True, align="C")
    pdf.ln(6)

    # divider
    pdf.set_draw_color(79, 70, 229)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    if not itinerary:
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, "No itinerary data available.", ln=True)
    else:
        for day, activities in itinerary.items():
            # day header
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(238, 242, 255)
            pdf.cell(0, 9, str(day), ln=True, fill=True)
            pdf.ln(1)

            items = activities if isinstance(activities, list) else [str(activities)]
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(60, 60, 60)
            for item in items:
                pdf.cell(6)  # indent
                pdf.multi_cell(0, 7, f"\u2022  {item}")
            pdf.ln(3)

    return bytes(pdf.output())


# ── rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ── graph + tools ─────────────────────────────────────────────────────────────
_graph = build_graph(db_path="data/checkpoints.db")
_attraction_tool = AttractionFinderTool()
_restaurant_tool = RestaurantFinderTool()
flight_tool = DummyFlightTool()
hotel_tool = HotelSearchTool()
_weather_tool = WeatherCheckerTool()
_budget_tool = BudgetTrackerTool()

# ── in-memory job store (replace with Redis/DB for production) ────────────────
_jobs: dict[str, dict[str, Any]] = {}

# ── session store ─────────────────────────────────────────────────────────────
_sessions: dict[str, dict[str, Any]] = {}

# ── API key (env-var based) ───────────────────────────────────────────────────
_API_KEY = os.getenv("API_KEY", "dev-key-change-me")


def _require_api_key(request: Request) -> None:
    key = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Travel Agent",
    description="Production backend — Week 15",
    version="0.2.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────
class PlanPayload(BaseModel):
    destination: str
    days: int = 5
    budget: float = 1500
    extra: str = ""


class RefinePayload(BaseModel):
    session_id: str
    instruction: str  # e.g. "less walking", "add museums"


class EvaluatePayload(BaseModel):
    itinerary: dict[str, Any]
    request: str


class BudgetPayload(BaseModel):
    trip_id: str
    action: str
    total_budget: float | None = None
    category: str | None = None
    amount: float | None = None
    description: str | None = None


# ── helpers ───────────────────────────────────────────────────────────────────
def _build_raw_input(p: PlanPayload) -> str:
    parts = [f"{p.destination} {p.days} days ${p.budget:.0f}"]
    if p.extra:
        parts.append(p.extra)
    return " ".join(parts)


def _run_graph(raw_input: str, thread_id: str) -> dict[str, Any]:
    return _graph.invoke(
        {"raw_input": raw_input, "status": "parse", "messages": []},
        config={"configurable": {"thread_id": thread_id}},
    )


async def _stream_graph(raw_input: str, thread_id: str) -> AsyncIterator[dict[str, Any]]:
    """Yield each node's output as it completes — uses sync .stream() in a thread."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def _run_sync() -> None:
        try:
            for chunk in _graph.stream(
                {"raw_input": raw_input, "status": "parse", "messages": []},
                config={"configurable": {"thread_id": thread_id}},
            ):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_run_sync)
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk


def _background_plan(job_id: str, raw_input: str, thread_id: str) -> None:
    try:
        result = _run_graph(raw_input, thread_id)
        itinerary = (result.get("final_output") or {}).get("itinerary") or {}
        _jobs[job_id] = {"status": "completed", "result": itinerary, "thread_id": thread_id}
    except Exception as exc:
        _jobs[job_id] = {"status": "failed", "error": str(exc)}


# ── root / health ─────────────────────────────────────────────────────────────
@app.get("/")
def root() -> dict[str, Any]:
    return {"message": "AI Travel Agent is running", "version": app.version}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok" if cache.is_healthy() else "degraded"}


@app.get("/cache/health")
def cache_health() -> dict[str, Any]:
    return {"healthy": cache.is_healthy()}


# ── Week 15: POST /plan ───────────────────────────────────────────────────────
@app.post("/plan")
@limiter.limit("20/minute")
def plan_trip(request: Request, payload: PlanPayload, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start async planning. Returns session_id + job_id for polling."""
    session_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    raw_input = _build_raw_input(payload)

    _sessions[session_id] = {"raw_input": raw_input, "payload": payload.model_dump(), "itinerary": None}
    _jobs[job_id] = {"status": "running"}

    background_tasks.add_task(_background_plan, job_id, raw_input, session_id)
    return {"session_id": session_id, "job_id": job_id, "status": "planning"}


# ── Week 15: GET /status/{job_id} ─────────────────────────────────────────────
@app.get("/status/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Week 15: POST /refine ─────────────────────────────────────────────────────
@app.post("/refine")
@limiter.limit("20/minute")
def refine_trip(request: Request, payload: RefinePayload, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Refine an existing itinerary with a natural-language instruction."""
    session = _sessions.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    job_id = str(uuid.uuid4())
    raw_input = session["raw_input"] + f". Refinement: {payload.instruction}"
    _jobs[job_id] = {"status": "running"}

    background_tasks.add_task(_background_plan, job_id, raw_input, payload.session_id)
    return {"session_id": payload.session_id, "job_id": job_id, "status": "refining"}


# ── Week 15: GET /export ──────────────────────────────────────────────────────
@app.get("/export")
def export_itinerary(
    session_id: str = Query(...),
    fmt: str = Query("json", pattern="^(json|markdown|pdf)$"),
) -> Response:
    """Export itinerary as JSON, Markdown, or PDF."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # find itinerary: prefer session's normalized copy, fall back to job result
    itinerary: dict[str, Any] = session.get("itinerary") or {}
    if not itinerary:
        for job in reversed(list(_jobs.values())):
            if job.get("status") == "completed" and job.get("thread_id") == session_id:
                itinerary = job.get("result", {})
                break

    if not itinerary:
        raise HTTPException(status_code=404, detail="No completed itinerary for this session")

    if fmt == "json":
        return JSONResponse(content=itinerary)

    if fmt == "markdown":
        lines = [f"# Itinerary\n"]
        for day, activities in itinerary.items():
            lines.append(f"## {day}")
            if isinstance(activities, list):
                for a in activities:
                    lines.append(f"- {a}")
            else:
                lines.append(str(activities))
        md = "\n".join(lines)
        return Response(content=md, media_type="text/markdown",
                        headers={"Content-Disposition": "attachment; filename=itinerary.md"})

    # pdf — build with fpdf2 from the normalized itinerary
    try:
        pdf_bytes = _build_pdf(itinerary, session.get("raw_input", "Trip"))
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=itinerary.pdf"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc


# ── Week 15: WebSocket /ws/plan ───────────────────────────────────────────────
@app.websocket("/ws/plan")
async def ws_plan(websocket: WebSocket) -> None:
    """Stream planning progress node-by-node to the frontend."""
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        destination = data.get("destination", "")
        days = int(data.get("days", 5))
        budget = float(data.get("budget", 1500))
        extra = data.get("extra", "")

        if not destination:
            await websocket.send_json({"type": "error", "message": "destination required"})
            return

        session_id = str(uuid.uuid4())
        raw_input = f"{destination} {days} days ${budget:.0f}"
        if extra:
            raw_input += f" {extra}"

        _sessions[session_id] = {"raw_input": raw_input, "itinerary": None}
        await websocket.send_json({"type": "session", "session_id": session_id})

        node_labels: dict[str, str] = {
            "parse_preferences": "Parsing your request...",
            "allocate_budget": "Allocating budget...",
            "search_flights": "Searching flights...",
            "search_hotels": "Finding hotels...",
            "find_attractions": "Discovering attractions...",
            "find_restaurants": "Finding restaurants...",
            "check_weather": "Checking weather...",
            "track_budget": "Tracking budget...",
            "build_geo_clusters": "Clustering locations...",
            "build_itinerary": "Building itinerary...",
            "optimize_routes": "Optimizing routes...",
            "evaluate_budget": "Evaluating budget...",
            "assemble_output": "Assembling final plan...",
        }

        final_output: dict[str, Any] = {}
        final_state: dict[str, Any] = {}

        async for chunk in _stream_graph(raw_input, session_id):
            for node_name, node_output in chunk.items():
                label = node_labels.get(node_name, f"Running {node_name}...")
                await websocket.send_json({"type": "progress", "node": node_name, "message": label})
                await asyncio.sleep(0)
                if isinstance(node_output, dict):
                    final_state.update(node_output)
                    if node_name == "assemble_output":
                        final_output = node_output.get("final_output") or {}

        # build attraction id→name lookup from state
        attractions = final_state.get("attraction_results") or []
        attr_map = {a.get("id", ""): a.get("name", "Activity") for a in attractions if a.get("id")}
        attr_map.update({a.get("name", ""): a.get("name", "Activity") for a in attractions if a.get("name")})

        # normalize itinerary days → {"Day 1": ["morning: Name ($cost)", ...]}
        raw_itin = final_output.get("itinerary") or {}
        normalized: dict[str, list[str]] = {}
        if isinstance(raw_itin, dict) and "days" in raw_itin:
            for day in raw_itin["days"]:
                day_num = day.get("day_number", 1)
                acts = day.get("activities") or []
                lines = []
                for a in acts:
                    name = a.get("name") or attr_map.get(a.get("attraction_id", ""), "Activity")
                    slot = a.get("time_slot", "")
                    slot_str = slot.value if hasattr(slot, "value") else str(slot)
                    cost = a.get("cost") or 0
                    cost_str = f" (${cost:.0f}" + ")" if cost else ""
                    lines.append(f"{slot_str.capitalize()}: {name}{cost_str}")
                if not lines:
                    lines = ["Free exploration"]
                normalized[f"Day {day_num}"] = lines
        elif isinstance(raw_itin, dict):
            normalized = {k: v if isinstance(v, list) else [str(v)] for k, v in raw_itin.items()}

        # clean flights for display
        flights_clean = []
        for f in (final_output.get("flights") or [])[:3]:
            segs = f.get("segments") or []
            seg = segs[0] if segs else {}
            flights_clean.append({
                "airline": seg.get("airline", "Flight"),
                "from": seg.get("departure_airport", ""),
                "to": seg.get("arrival_airport", ""),
                "price": f.get("total_price_usd", 0),
                "duration": f.get("total_duration_minutes", 0),
                "stops": f.get("num_stops", 0),
            })

        # clean hotels for display
        hotels_clean = []
        for h in (final_output.get("hotels") or [])[:3]:
            hotels_clean.append({
                "name": h.get("name", "Hotel"),
                "stars": h.get("star_rating", 0),
                "rating": h.get("review_score", 0),
                "price_per_night": h.get("price_per_night_usd", 0),
                "amenities": (h.get("amenities") or [])[:4],
            })

        # clean weather
        weather_clean = []
        for w in (final_output.get("weather") or [])[:7]:
            weather_clean.append({
                "date": str(w.get("date", "")),
                "condition": w.get("condition", w.get("description", "")),
                "temp_max": w.get("temp_max", w.get("temperature", "")),
                "temp_min": w.get("temp_min", ""),
                "rain": w.get("rain_chance_pct", 0),
            })

        # budget
        budget_raw = final_output.get("budget") or {}
        budget_clean = {
            "total": budget_raw.get("total_budget"),
            "spent": budget_raw.get("spent_total", 0),
            "remaining": budget_raw.get("remaining"),
            "by_category": budget_raw.get("by_category", {}),
        }

        dest = final_output.get("destination") or destination
        payload_out = _safe_json({
            "type": "done",
            "session_id": session_id,
            "destination": dest,
            "itinerary": normalized,
            "flights": flights_clean,
            "hotels": hotels_clean,
            "weather": weather_clean,
            "budget": budget_clean,
        })
        _sessions[session_id]["itinerary"] = normalized
        _sessions[session_id]["full_output"] = _safe_json(final_output)
        await websocket.send_json(payload_out)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ── legacy endpoints (kept for backward compat) ───────────────────────────────
@app.post("/api/trip/plan")
@limiter.limit("20/minute")
def plan_trip_legacy(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("request", "")
    if not raw:
        raise HTTPException(status_code=422, detail="request field required")
    thread_id = str(uuid.uuid4())
    result = _run_graph(raw, thread_id)
    itinerary = (result.get("final_output") or {}).get("itinerary") or {}
    if not itinerary:
        raise HTTPException(status_code=500, detail=result.get("error", "planning failed"))
    return {"thread_id": thread_id, "itinerary": itinerary}


@app.post("/api/trip/evaluate")
def evaluate_trip(payload: EvaluatePayload) -> dict[str, Any]:
    try:
        return evaluate_itinerary(payload.itinerary, payload.request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/flights")
def search_flights(
    origin: str = Query("AMD", min_length=3, max_length=3),
    destination: str = Query("DEL", min_length=3, max_length=3),
) -> dict[str, Any]:
    result = flight_tool._run(origin=origin, destination=destination)
    return {"origin": origin, "destination": destination, "results": result}


@app.get("/api/hotels")
def search_hotels(
    city: str, check_in: str, check_out: str,
    adults: int = 2,
    max_price_per_night: float | None = None,
    min_rating: float | None = None,
    hotel_class: str | None = None,
) -> dict[str, Any]:
    result = hotel_tool._run(city=city, check_in=check_in, check_out=check_out,
                              adults=adults, max_price_per_night=max_price_per_night,
                              min_rating=min_rating, hotel_class=hotel_class)
    return {"city": city, "check_in": check_in, "check_out": check_out,
            "adults": adults, "count": len(result), "results": result}


@app.get("/api/trip/attractions")
def get_attractions(city: str, country: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    try:
        return _attraction_tool._run(city=city, country=country, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"attraction lookup failed: {exc}") from exc


@app.get("/api/trip/weather")
def get_weather(city: str, days: int = 7) -> list[dict[str, Any]]:
    return _weather_tool._run(city=city, days=days)


@app.get("/api/trip/restaurants")
def get_restaurants(
    city: str, cuisine: str | None = None,
    budget: str | None = None, min_rating: float = 0.0, limit: int = 10,
) -> list[dict[str, Any]]:
    try:
        return _restaurant_tool._run(city=city, cuisine=cuisine, budget=budget,
                                      min_rating=min_rating, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"restaurant lookup failed: {exc}") from exc


@app.post("/api/trip/budget")
def update_budget(payload: BudgetPayload) -> dict[str, Any]:
    return _budget_tool._run(**payload.model_dump())


@app.get("/api/trip/budget/{trip_id}")
def get_budget_summary(trip_id: str) -> dict[str, Any]:
    return _budget_tool._run(trip_id=trip_id, action="get_summary")
