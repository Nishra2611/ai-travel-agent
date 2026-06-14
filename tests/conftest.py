import pytest

from ai_travel_agent.utils.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    cache.client.flushall()
