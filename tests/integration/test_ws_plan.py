"""
tests/integration/test_ws_plan.py — Week 17

WebSocket integration tests for /ws/plan.  Uses FastAPI's TestClient
WebSocket support so every LangGraph call is mocked and no live server
is required.

Run: pytest tests/integration/test_ws_plan.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_travel_agent.api.main import app

client = TestClient(app)


# ── helpers ──────────────────────────────────────────────────────────────


def _fake_stream_chunks():
    """Simulate the graph.stream() generator that _stream_graph wraps."""
    yield {"parse_preferences": {"destination": "Paris", "days": 5, "budget": 1500}}
    yield {"search_flights": {"flight_results": []}}
    yield {
        "find_attractions": {
            "attraction_results": [
                {"id": "a1", "name": "Eiffel Tower", "category": "landmark"},
            ]
        }
    }
    yield {"build_itinerary": {"itinerary_result": {}}}
    yield {
        "assemble_output": {
            "final_output": {
                "destination": "Paris",
                "itinerary": {
                    "days": [
                        {
                            "day_number": 1,
                            "activities": [
                                {
                                    "name": "Eiffel Tower",
                                    "time_slot": "morning",
                                    "cost": 0,
                                }
                            ],
                        }
                    ]
                },
                "flights": [],
                "hotels": [],
                "weather": [],
                "budget": {"total_budget": 1500, "spent_total": 0},
            }
        }
    }


# ── core WebSocket flow ─────────────────────────────────────────────────


class TestWsPlan:
    def test_full_planning_flow(self):
        """Connect → send payload → receive session, progress*, done."""
        with patch(
            "ai_travel_agent.api.main._graph.stream", return_value=_fake_stream_chunks()
        ):
            with client.websocket_connect("/ws/plan") as ws:
                ws.send_json({"destination": "Paris", "days": 5, "budget": 1500})

                messages = []
                while True:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg.get("type") in ("done", "error"):
                        break

                types = [m["type"] for m in messages]

                # first message is the session id
                assert types[0] == "session"
                assert "session_id" in messages[0]

                # at least one progress message
                assert "progress" in types

                # last message is "done" with itinerary
                done = messages[-1]
                assert done["type"] == "done"
                assert "itinerary" in done
                assert "session_id" in done

    def test_session_stored_after_done(self):
        """After ws/plan completes, the session is stored for /export."""
        with patch(
            "ai_travel_agent.api.main._graph.stream", return_value=_fake_stream_chunks()
        ):
            with client.websocket_connect("/ws/plan") as ws:
                ws.send_json({"destination": "Paris", "days": 3, "budget": 1000})

                session_id = None
                while True:
                    msg = ws.receive_json()
                    if msg.get("type") == "session":
                        session_id = msg["session_id"]
                    if msg.get("type") in ("done", "error"):
                        break

                assert session_id is not None

                # /export should now work for this session
                r = client.get(
                    "/export", params={"session_id": session_id, "fmt": "json"}
                )
                assert r.status_code == 200
                assert isinstance(r.json(), dict)


class TestWsPlanErrors:
    def test_missing_destination_returns_error(self):
        """Sending an empty destination triggers an error message."""
        with client.websocket_connect("/ws/plan") as ws:
            ws.send_json({"destination": "", "days": 5, "budget": 1500})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "destination" in msg["message"].lower()

    def test_graph_exception_returns_error(self):
        """If the graph raises, the WS should send an error message."""
        with patch(
            "ai_travel_agent.api.main._graph.stream", side_effect=RuntimeError("boom")
        ):
            with client.websocket_connect("/ws/plan") as ws:
                ws.send_json({"destination": "Tokyo", "days": 3, "budget": 2000})
                messages = []
                while True:
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg.get("type") in ("done", "error"):
                        break

                last = messages[-1]
                assert last["type"] == "error"
                assert "boom" in last["message"]


class TestWsPlanProgressMessages:
    def test_progress_contains_node_name(self):
        """Each progress message should include the node name."""
        with patch(
            "ai_travel_agent.api.main._graph.stream", return_value=_fake_stream_chunks()
        ):
            with client.websocket_connect("/ws/plan") as ws:
                ws.send_json({"destination": "Rome", "days": 4, "budget": 1800})

                progress_msgs = []
                while True:
                    msg = ws.receive_json()
                    if msg.get("type") == "progress":
                        progress_msgs.append(msg)
                    if msg.get("type") in ("done", "error"):
                        break

                assert len(progress_msgs) > 0
                for pm in progress_msgs:
                    assert "node" in pm
                    assert "message" in pm


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
