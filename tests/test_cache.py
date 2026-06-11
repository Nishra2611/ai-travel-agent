from src.utils.cache import cache


def test_cache():
    params = {
        "origin": "AMD",
        "destination": "DEL"
    }

    data = {
        "price": 5000
    }

    cache.set("flight", params, data, ttl=60)

    result = cache.get("flight", params)

    print(result)
    assert result == data, f"Expected {data}, got {result}"
    print("Cache test passed.")


if __name__ == "__main__":
    test_cache()
