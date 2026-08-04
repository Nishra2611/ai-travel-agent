from unittest.mock import patch

from ai_travel_agent.tools.attraction_finder import AttractionFinderTool


@patch("ai_travel_agent.tools.attraction_finder.web_search")
@patch("ai_travel_agent.tools.attraction_finder.overpass_attractions_near")
@patch("ai_travel_agent.tools.attraction_finder.geocode")
def test_attraction_finder_returns_results(
    mock_geocode,
    mock_overpass,
    mock_web_search,
):
    mock_geocode.return_value = {
        "lat": 51.5074,
        "lng": -0.1278,
        "display_name": "London, UK",
    }

    mock_overpass.return_value = [
        {
            "name": "Tower of London",
            "lat": 51.5081,
            "lng": -0.0759,
            "category": "attraction",
            "hours": "09:00-17:00",
        },
        {
            "name": "Hyde Park",
            "lat": 51.5073,
            "lng": -0.1657,
            "category": "park",
            "hours": None,
        },
    ]

    mock_web_search.return_value = [
        {
            "title": "Top Tourist Attractions in London",
            "snippet": "Tower of London",
            "link": "https://example.com",
        }
    ]

    tool = AttractionFinderTool()

    results = tool._run(
        city="London",
        country="UK",
        limit=5,
    )

    assert len(results) == 2

    for item in results:
        assert "name" in item
        assert "lat" in item
        assert "lng" in item
        assert "hours" in item
        assert "rating" in item


@patch("ai_travel_agent.tools.attraction_finder.geocode")
def test_attraction_finder_returns_empty_when_city_not_found(
    mock_geocode,
):
    mock_geocode.return_value = None

    tool = AttractionFinderTool()

    results = tool._run(
        city="UnknownCity",
        limit=5,
    )

    assert results == []


@patch("ai_travel_agent.tools.attraction_finder.web_search")
@patch("ai_travel_agent.tools.attraction_finder.overpass_attractions_near")
@patch("ai_travel_agent.tools.attraction_finder.geocode")
def test_attraction_finder_respects_limit(
    mock_geocode,
    mock_overpass,
    mock_web_search,
):
    mock_geocode.return_value = {
        "lat": 51.5074,
        "lng": -0.1278,
        "display_name": "London, UK",
    }

    mock_overpass.return_value = [
        {
            "name": f"Attraction {i}",
            "lat": 1.0,
            "lng": 2.0,
            "category": "attraction",
            "hours": None,
        }
        for i in range(10)
    ]

    mock_web_search.return_value = []

    tool = AttractionFinderTool()

    results = tool._run(
        city="London",
        limit=3,
    )

    assert len(results) == 3
