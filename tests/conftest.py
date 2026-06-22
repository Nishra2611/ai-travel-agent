"""Pytest configuration and shared fixtures."""

import datetime

import pytest

from ai_travel_agent.utils.cache import cache


@pytest.fixture(autouse=True)
def reset_serpapi_budget() -> None:
    """Reset the SerpApi daily call counter before every test."""
    key = f"api_calls:serpapi:{datetime.date.today().isoformat()}"
    try:
        cache.client.set(key, 0)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Clear the shared cache before every test."""
    try:
        cache.clear()
    except Exception:
        pass
