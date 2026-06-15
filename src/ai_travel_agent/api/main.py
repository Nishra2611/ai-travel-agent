"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException, Query

from ai_travel_agent.tools.dummy_tool import DummyFlightTool
from ai_travel_agent.utils.cache import cache

app = FastAPI(
    title="AI Travel Agent",
    description="Autonomous AI Travel Planning Agent API",
    version="0.1.0",
)

flight_tool = DummyFlightTool()


@app.get("/")
def root():
    return {
        "message": "AI Travel Agent is running",
        "version": app.version,
        "endpoints": ["/health", "/flights", "/cache/health", "/docs"],
    }


@app.get("/health")
def health():
    healthy = cache.is_healthy()
    return {
        "status": "ok" if healthy else "degraded",
        "cache": "healthy" if healthy else "unavailable",
    }


@app.get("/cache/health")
def cache_health():
    healthy = cache.is_healthy()
    return {
        "redis": "connected" if healthy else "using fakeredis (dev mode)",
        "healthy": healthy,
    }


@app.get("/flights")
def search_flights(
    origin: str = Query(default="AMD", min_length=3, max_length=3),
    destination: str = Query(default="DEL", min_length=3, max_length=3),
):
    try:
        result = flight_tool._run(origin=origin, destination=destination)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"origin": origin, "destination": destination, "results": result}
