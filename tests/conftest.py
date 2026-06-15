"""Pytest configuration and shared fixtures."""

import datetime

import pytest


@pytest.fixture(autouse=True)
def reset_serpapi_budget() -> None:
    """Reset the SerpApi daily call counter before every test."""
    from src.utils.cache import cache

    key = f"api_calls:serpapi:{datetime.date.today().isoformat()}"
    try:
        cache.client.set(key, 0)
    except Exception:
        pass
