from unittest.mock import patch

from ai_travel_agent.tools.restaurant_finder import (
    RestaurantFinderTool,
)


@patch(
    "ai_travel_agent.tools.restaurant_finder.places_text_search"
)
def test_min_rating_filter(
    mock_places,
):
    mock_places.return_value = [
        {
            "name": "A",
            "rating": 4.8,
            "price_level": 1,
        },
        {
            "name": "B",
            "rating": 3.2,
            "price_level": 1,
        },
    ]

    tool = RestaurantFinderTool()

    results = tool._run(
        city="London",
        min_rating=4.0,
    )

    assert len(results) == 1
    assert results[0]["name"] == "A"


@patch(
    "ai_travel_agent.tools.restaurant_finder.places_text_search"
)
def test_budget_filter(
    mock_places,
):
    mock_places.return_value = [
        {
            "name": "Cheap",
            "rating": 4.5,
            "price_level": 0,
        },
        {
            "name": "Luxury",
            "rating": 4.5,
            "price_level": 3,
        },
    ]

    tool = RestaurantFinderTool()

    results = tool._run(
        city="London",
        budget="$",
    )

    assert len(results) == 1
    assert results[0]["name"] == "Cheap"


@patch(
    "ai_travel_agent.tools.restaurant_finder.places_text_search"
)
def test_limit_respected(
    mock_places,
):
    mock_places.return_value = [
        {
            "name": f"Restaurant {i}",
            "rating": 4.5,
            "price_level": 1,
        }
        for i in range(20)
    ]

    tool = RestaurantFinderTool()

    results = tool._run(
        city="London",
        limit=5,
    )

    assert len(results) == 5
