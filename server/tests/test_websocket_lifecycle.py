"""Heartbeat, idle timeout, stale-connection cleanup and reconnect behaviour."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.websocket import TransportLimits
from app.websocket.limits import default_limits
from app.websocket.manager import ConnectionManager
from tests.conftest import envelope, make_client, manager_of, ws_url

# --- Heartbeat ------------------------------------------------------------


def test_heartbeat_ping_receives_pong(client: TestClient) -> None:
    """heartbeat.ping is answered with a correlated heartbeat.pong."""
    with client.websocket_connect(ws_url("alice")) as ws:
        ws.receive_json()
        ping = envelope(sender="alice", message_type="heartbeat.ping")
        ws.send_json(ping)
        pong = ws.receive_json()

    assert pong["type"] == "heartbeat.pong"
    assert pong["message_id"] == ping["message_id"]
    assert pong["server_time"]


def test_connection_ready_advertises_heartbeat_policy(client: TestClient) -> None:
    """Clients are told the interval and timeout rather than guessing."""
    limits = default_limits()
    with client.websocket_connect(ws_url("alice")) as ws:
        ready = ws.receive_json()

    assert ready["heartbeat_interval_seconds"] == limits.heartbeat_interval_seconds
    assert ready["idle_timeout_seconds"] == limits.idle_timeout_seconds
    assert ready["heartbeat_interval_seconds"] < ready["idle_timeout_seconds"]
    assert ready["max_message_bytes"] == limits.max_message_bytes


def test_heartbeat_keeps_connection_alive() -> None:
    """Activity resets the idle timer, so a pinging client is not closed."""
    limits = TransportLimits(idle_timeout_seconds=1.0)
    with make_client(limits) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            for _ in range(3):
                ws.send_json(envelope(sender="alice", message_type="heartbeat.ping"))
                assert ws.receive_json()["type"] == "heartbeat.pong"

            # Still usable well after a single idle window would have elapsed.
            ws.send_json(envelope(sender="alice", message_type="heartbeat.ping"))
            assert ws.receive_json()["type"] == "heartbeat.pong"


# --- Idle timeout ---------------------------------------------------------


def test_idle_connection_is_closed_with_a_deterministic_error() -> None:
    """An idle connection is told why before being closed."""
    limits = TransportLimits(idle_timeout_seconds=0.3)
    with make_client(limits) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            error = ws.receive_json()

    assert error["type"] == "protocol.error"
    assert error["code"] == "WS_1013_IDLE_TIMEOUT"


def test_idle_timeout_removes_connection_from_registry() -> None:
    """Idle cleanup must not leave a stale registry entry."""
    limits = TransportLimits(idle_timeout_seconds=0.3)
    with make_client(limits) as client:
        manager = manager_of(client)
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            assert manager.is_connected("alice")
            assert ws.receive_json()["code"] == "WS_1013_IDLE_TIMEOUT"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

        assert manager.connection_count == 0
        assert not manager.is_connected("alice")


def test_stale_connections_are_identifiable() -> None:
    """The manager can report connections past the idle threshold."""

    async def scenario() -> tuple[int, int]:
        manager = ConnectionManager(TransportLimits(idle_timeout_seconds=10.0))
        fresh = manager.register("fresh", now_monotonic=100.0)
        manager.register("stale", now_monotonic=0.0)

        stale = manager.stale_connections(now_monotonic=100.0)
        fresh.touch(100.0)
        return len(stale), len(manager.stale_connections(now_monotonic=100.0))

    stale_count, still_stale = asyncio.run(scenario())
    assert stale_count == 1
    assert still_stale == 1


def test_touch_resets_idle_measurement() -> None:
    """Recording activity resets how idle a connection appears."""

    async def scenario() -> tuple[float, float]:
        manager = ConnectionManager(default_limits())
        context = manager.register("alice", now_monotonic=0.0)
        before = context.idle_seconds(50.0)
        context.touch(50.0)
        return before, context.idle_seconds(50.0)

    before, after = asyncio.run(scenario())
    assert before == 50.0
    assert after == 0.0


# --- Disconnect and reconnect --------------------------------------------


def test_reconnect_restores_routing(client: TestClient) -> None:
    """A reconnected client can send and receive again."""
    with client.websocket_connect(ws_url("bob")) as ws_b:
        ws_b.receive_json()

    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": "again"}))

        assert ws_b.receive_json()["payload"] == {"text": "again"}
        assert ws_a.receive_json()["status"] == "delivered"


def test_message_to_disconnected_peer_is_queued_then_delivered(client: TestClient) -> None:
    """Documented Phase 2 reconnect policy: queued data is drained on return."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()

        with client.websocket_connect(ws_url("bob")) as ws_b:
            ws_b.receive_json()
            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"n": 1}))
            assert ws_b.receive_json()["payload"] == {"n": 1}
            assert ws_a.receive_json()["status"] == "delivered"

        # Bob is gone: the next message is queued rather than lost or broadcast.
        ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"n": 2}))
        assert ws_a.receive_json()["status"] == "queued"
        assert manager.offline_queue.count("bob") == 1

        with client.websocket_connect(ws_url("bob")) as ws_b:
            ready = ws_b.receive_json()
            assert ready["queued_message_count"] == 1
            assert ws_b.receive_json()["payload"] == {"n": 2}


def test_reconnected_client_is_still_unauthenticated(client: TestClient) -> None:
    """Reconnecting must never be treated as having authenticated."""
    for _ in range(2):
        with client.websocket_connect(ws_url("alice")) as ws:
            ready = ws.receive_json()
            assert ready["authenticated"] is False
            assert ready["identity_status"] == "TRANSPORT_TEST_IDENTITY"


def test_abrupt_disconnect_cleans_up_registry(client: TestClient) -> None:
    """A client vanishing mid-session leaves no stale state."""
    manager = manager_of(client)
    socket = client.websocket_connect(ws_url("alice"))
    ws = socket.__enter__()
    ws.receive_json()
    assert manager.connection_count == 1

    ws.close()
    socket.__exit__(None, None, None)

    assert manager.connection_count == 0
    assert manager.client_count == 0


def test_many_sequential_connections_leave_no_residue(client: TestClient) -> None:
    """Repeated connect/disconnect cycles do not accumulate state."""
    manager = manager_of(client)
    for _ in range(25):
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()

    assert manager.connection_count == 0
    assert manager.client_count == 0
