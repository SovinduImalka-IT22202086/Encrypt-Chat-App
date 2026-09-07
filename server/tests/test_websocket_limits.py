"""Resource bounds: message size, rate limiting, backpressure, queue caps.

Assertion E: oversized messages are rejected before uncontrolled processing.
Assertion G: resource/queue behaviour is bounded.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.websocket import TransportLimits
from app.websocket.limits import RateLimiter, default_limits
from app.websocket.manager import ConnectionManager, ConnectionRejected
from app.websocket.queue import OfflineQueue
from tests.conftest import envelope, make_client, ws_url

# --- Message size ---------------------------------------------------------


def test_message_below_limit_is_accepted() -> None:
    """A payload comfortably inside the limit routes normally."""
    with make_client(TransportLimits(max_message_bytes=2048)) as client:
        with (
            client.websocket_connect(ws_url("alice")) as ws_a,
            client.websocket_connect(ws_url("bob")) as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"t": "x" * 100}))
            assert ws_b.receive_json()["type"] == "message.receipt"
            assert ws_a.receive_json()["status"] == "delivered"


def test_message_above_limit_is_rejected() -> None:
    """An oversized frame is refused with a deterministic error."""
    with make_client(TransportLimits(max_message_bytes=1024)) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            ws.send_json(envelope(sender="alice", recipient="bob", payload={"t": "x" * 4096}))
            error = ws.receive_json()

    assert error["type"] == "protocol.error"
    assert error["code"] == "WS_1008_MESSAGE_TOO_LARGE"


def test_oversized_message_is_not_routed() -> None:
    """An oversized message must never reach the recipient."""
    with make_client(TransportLimits(max_message_bytes=1024)) as client:
        with (
            client.websocket_connect(ws_url("alice")) as ws_a,
            client.websocket_connect(ws_url("bob")) as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"t": "x" * 4096}))
            assert ws_a.receive_json()["code"] == "WS_1008_MESSAGE_TOO_LARGE"

            ws_b.send_json(envelope(sender="bob", message_type="heartbeat.ping"))
            assert ws_b.receive_json()["type"] == "heartbeat.pong"


def test_size_limit_boundary_is_inclusive() -> None:
    """A frame of exactly the limit is accepted; one byte more is not.

    Documented behaviour: the check is `size > limit`, so `size == limit`
    passes.
    """
    limit = 1024
    with make_client(TransportLimits(max_message_bytes=limit)) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()

            base = envelope(sender="alice", recipient="bob", payload={"t": ""})
            overhead = len(json.dumps(base, separators=(",", ":")).encode())
            base["payload"] = {"t": "x" * (limit - overhead)}
            raw = json.dumps(base, separators=(",", ":"))
            assert len(raw.encode()) == limit

            ws.send_text(raw)
            assert ws.receive_json()["type"] == "message.delivery_ack"

            base["payload"] = {"t": "x" * (limit - overhead + 1)}
            oversized = json.dumps(base, separators=(",", ":"))
            assert len(oversized.encode()) == limit + 1

            ws.send_text(oversized)
            assert ws.receive_json()["code"] == "WS_1008_MESSAGE_TOO_LARGE"


def test_connection_survives_oversized_message() -> None:
    """Rejecting an oversized frame must not tear down the connection."""
    with make_client(TransportLimits(max_message_bytes=1024)) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            ws.send_json(envelope(sender="alice", recipient="bob", payload={"t": "x" * 8192}))
            assert ws.receive_json()["code"] == "WS_1008_MESSAGE_TOO_LARGE"

            ws.send_json(envelope(sender="alice", message_type="heartbeat.ping"))
            assert ws.receive_json()["type"] == "heartbeat.pong"


# --- Rate limiting --------------------------------------------------------


def test_message_burst_is_rate_limited() -> None:
    """A burst beyond the window limit is throttled deterministically."""
    limits = TransportLimits(max_messages_per_window=3, rate_limit_window_seconds=60.0)
    with make_client(limits) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            codes = []
            for _ in range(6):
                ws.send_json(envelope(sender="alice", message_type="heartbeat.ping"))
                codes.append(ws.receive_json())

    assert [c["type"] for c in codes[:3]] == ["heartbeat.pong"] * 3
    assert all(c["code"] == "WS_1009_RATE_LIMITED" for c in codes[3:])


def test_rate_limited_messages_are_not_routed() -> None:
    """Throttled traffic must not reach the recipient."""
    limits = TransportLimits(max_messages_per_window=1, rate_limit_window_seconds=60.0)
    with make_client(limits) as client:
        with (
            client.websocket_connect(ws_url("alice")) as ws_a,
            client.websocket_connect(ws_url("bob")) as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"n": 1}))
            assert ws_b.receive_json()["payload"] == {"n": 1}
            assert ws_a.receive_json()["status"] == "delivered"

            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"n": 2}))
            assert ws_a.receive_json()["code"] == "WS_1009_RATE_LIMITED"

            ws_b.send_json(envelope(sender="bob", message_type="heartbeat.ping"))
            assert ws_b.receive_json()["type"] == "heartbeat.pong"


def test_rate_limiter_window_resets() -> None:
    """The fixed window resets, so throttling is temporary, not permanent."""
    limiter = RateLimiter(max_messages=2, window_seconds=10.0)

    assert limiter.allow(100.0) is True
    assert limiter.allow(100.1) is True
    assert limiter.allow(100.2) is False

    assert limiter.allow(111.0) is True


def test_rate_limiter_state_is_constant_size() -> None:
    """The limiter holds a counter, not a growing history."""
    limiter = RateLimiter(max_messages=5, window_seconds=1.0)
    for tick in range(10_000):
        limiter.allow(tick * 0.0001)

    assert limiter.__slots__ == ("max_messages", "window_seconds", "_window_started_at", "_count")


# --- Backpressure ---------------------------------------------------------


def test_outbound_queue_is_bounded() -> None:
    """A connection's outbound queue refuses work once full (WS-007)."""

    async def scenario() -> tuple[list[bool], int]:
        manager = ConnectionManager(TransportLimits(max_pending_outbound=3))
        context = manager.register("bob")
        accepted = [context.enqueue_outbound({"n": index}) for index in range(6)]
        return accepted, context.pending_outbound

    accepted, pending = asyncio.run(scenario())

    assert accepted == [True, True, True, False, False, False]
    assert pending == 3


def test_saturated_recipient_reports_unavailable() -> None:
    """Delivery to a saturated recipient fails rather than buffering."""

    async def scenario() -> bool:
        manager = ConnectionManager(TransportLimits(max_pending_outbound=2))
        manager.register("bob")
        for index in range(2):
            manager.deliver_to_client("bob", {"n": index})
        return manager.deliver_to_client("bob", {"n": 99})

    assert asyncio.run(scenario()) is False


def test_closing_connection_accepts_no_further_messages() -> None:
    """Once closing, a connection stops accepting outbound work."""

    async def scenario() -> bool:
        manager = ConnectionManager(default_limits())
        context = manager.register("bob")
        context.mark_closing()
        return context.enqueue_outbound({"n": 1})

    assert asyncio.run(scenario()) is False


# --- Connection limits ----------------------------------------------------


def test_manager_enforces_total_connection_limit() -> None:
    """The registry refuses to exceed the global connection bound."""

    async def scenario() -> None:
        manager = ConnectionManager(TransportLimits(max_total_connections=2))
        manager.register("a")
        manager.register("b")
        with pytest.raises(ConnectionRejected):
            manager.register("c")

    asyncio.run(scenario())


def test_manager_enforces_per_client_limit() -> None:
    """The registry refuses too many sessions for one identity."""

    async def scenario() -> None:
        manager = ConnectionManager(TransportLimits(max_connections_per_client=2))
        manager.register("a")
        manager.register("a")
        with pytest.raises(ConnectionRejected):
            manager.register("a")

    asyncio.run(scenario())


def test_unregister_frees_capacity() -> None:
    """Capacity is reclaimed when a connection goes away."""

    async def scenario() -> int:
        manager = ConnectionManager(TransportLimits(max_total_connections=1))
        context = manager.register("a")
        manager.unregister(context.connection_id)
        manager.register("b")
        return manager.connection_count

    assert asyncio.run(scenario()) == 1


def test_unregister_is_idempotent() -> None:
    """Removing an already-removed connection is safe."""

    async def scenario() -> tuple[object, int]:
        manager = ConnectionManager(default_limits())
        context = manager.register("a")
        manager.unregister(context.connection_id)
        second = manager.unregister(context.connection_id)
        return second, manager.connection_count

    second, count = asyncio.run(scenario())
    assert second is None
    assert count == 0


# --- Offline queue bounds -------------------------------------------------


def test_offline_queue_bounds_per_recipient() -> None:
    """A single recipient cannot exceed its queue depth."""
    queue = OfflineQueue(max_per_recipient=2, max_recipients=10)

    assert queue.enqueue("bob", {"n": 1}) is True
    assert queue.enqueue("bob", {"n": 2}) is True
    assert queue.enqueue("bob", {"n": 3}) is False
    assert queue.count("bob") == 2


def test_offline_queue_bounds_recipient_count() -> None:
    """The number of queued recipients is bounded too."""
    queue = OfflineQueue(max_per_recipient=5, max_recipients=2)

    assert queue.enqueue("a", {}) is True
    assert queue.enqueue("b", {}) is True
    assert queue.enqueue("c", {}) is False
    assert queue.recipient_count == 2


def test_offline_queue_drains_in_order_and_empties() -> None:
    """Draining returns FIFO order and clears the recipient's queue."""
    queue = OfflineQueue(max_per_recipient=5, max_recipients=5)
    for index in range(3):
        queue.enqueue("bob", {"n": index})

    drained = queue.drain("bob")

    assert [item["n"] for item in drained] == [0, 1, 2]
    assert queue.count("bob") == 0
    assert queue.recipient_count == 0
    assert queue.drain("bob") == []


def test_offline_queue_total_is_bounded_under_flood() -> None:
    """Assertion G: sustained flooding cannot grow the queue without limit."""
    queue = OfflineQueue(max_per_recipient=10, max_recipients=5)
    for recipient_index in range(50):
        for _ in range(50):
            queue.enqueue(f"user-{recipient_index}", {"x": 1})

    assert queue.recipient_count == 5
    assert queue.total_queued == 50


# --- Limit configuration --------------------------------------------------


def test_limits_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limits are configurable rather than hard-coded."""
    monkeypatch.setenv("WS_MAX_MESSAGE_BYTES", "2048")
    monkeypatch.setenv("WS_MAX_TOTAL_CONNECTIONS", "7")
    monkeypatch.setenv("WS_IDLE_TIMEOUT_SECONDS", "12.5")
    limits = default_limits()

    assert limits.max_message_bytes == 2048
    assert limits.max_total_connections == 7
    assert limits.idle_timeout_seconds == 12.5


@pytest.mark.parametrize("bad", ["0", "-5", "not-a-number", ""])
def test_invalid_limit_configuration_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    """A nonsensical limit must not disable the bound."""
    monkeypatch.setenv("WS_MAX_MESSAGE_BYTES", bad)
    assert default_limits().max_message_bytes == 64 * 1024
