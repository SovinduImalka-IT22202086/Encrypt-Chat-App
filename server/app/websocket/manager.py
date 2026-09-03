"""Connection registry and per-connection transport state.

All live WebSocket state lives inside a `ConnectionManager` instance owned by
the FastAPI application (`app.state.ws_manager`). Nothing here is a module-level
mutable global, so tests construct an isolated manager instead of having to
reset shared state between cases.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.websocket.limits import RateLimiter, TransportLimits
from app.websocket.queue import OfflineQueue


class ConnectionRejected(Exception):
    """Raised when a connection cannot be registered."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(slots=True)
class ConnectionContext:
    """Per-connection transport state.

    PHASE 2 LIMITATION
    ------------------
    `transport_client_id` is a TRANSPORT_TEST_IDENTITY. It is NOT_AUTHENTICATED
    and is not an account identity. Phase 3 will bind WebSocket actions to an
    authenticated account/session identity; `authenticated` and
    `account_id` exist as the hook for that and must stay False/None until then.

    The server is authoritative over this mapping: it is established at
    connection time and never updated from the contents of a client message.
    """

    connection_id: str
    transport_client_id: str
    connected_at: datetime
    outbound: asyncio.Queue[dict[str, Any]]
    rate_limiter: RateLimiter
    last_activity_monotonic: float

    # --- Phase 3 hook (do not populate in Phase 2) -------------------------
    authenticated: bool = False
    account_id: str | None = None

    protocol_version: str = "1"
    remote_host: str | None = None
    _closing: bool = field(default=False, init=False)

    def touch(self, now_monotonic: float) -> None:
        """Record inbound activity, resetting the idle timer."""
        self.last_activity_monotonic = now_monotonic

    def idle_seconds(self, now_monotonic: float) -> float:
        """Seconds since the last inbound activity."""
        return now_monotonic - self.last_activity_monotonic

    def enqueue_outbound(self, message: dict[str, Any]) -> bool:
        """Queue a message for delivery to this connection.

        Returns False when the connection's bounded outbound queue is full.
        The caller is expected to surface that as a deterministic
        `recipient_unavailable` outcome rather than waiting, which is what
        keeps a slow reader from consuming unbounded memory (WS-007).
        """
        if self._closing:
            return False
        try:
            self.outbound.put_nowait(message)
        except asyncio.QueueFull:
            return False
        return True

    def mark_closing(self) -> None:
        """Stop accepting further outbound messages."""
        self._closing = True

    @property
    def pending_outbound(self) -> int:
        """Number of messages waiting to be written to this connection."""
        return self.outbound.qsize()


class ConnectionManager:
    """Tracks live connections and routes messages to a specific recipient."""

    __slots__ = ("_by_client", "_connections", "_limits", "_offline_queue")

    def __init__(self, limits: TransportLimits) -> None:
        self._limits = limits
        self._connections: dict[str, ConnectionContext] = {}
        self._by_client: dict[str, set[str]] = {}
        self._offline_queue = OfflineQueue(
            max_per_recipient=limits.max_queued_per_recipient,
            max_recipients=limits.max_queued_recipients,
        )

    # --- Registration ------------------------------------------------------

    def register(
        self,
        transport_client_id: str,
        *,
        remote_host: str | None = None,
        now_monotonic: float | None = None,
    ) -> ConnectionContext:
        """Create and register a connection context.

        Raises `ConnectionRejected` when a limit would be exceeded. The caller
        is responsible for translating that into a protocol error and close.
        """
        if len(self._connections) >= self._limits.max_total_connections:
            raise ConnectionRejected("total connection limit reached")

        existing = self._by_client.get(transport_client_id, set())
        if len(existing) >= self._limits.max_connections_per_client:
            raise ConnectionRejected("per-client connection limit reached")

        now = time.monotonic() if now_monotonic is None else now_monotonic
        context = ConnectionContext(
            connection_id=uuid4().hex,
            transport_client_id=transport_client_id,
            connected_at=datetime.now(UTC),
            outbound=asyncio.Queue(maxsize=self._limits.max_pending_outbound),
            rate_limiter=RateLimiter(
                max_messages=self._limits.max_messages_per_window,
                window_seconds=self._limits.rate_limit_window_seconds,
            ),
            last_activity_monotonic=now,
            remote_host=remote_host,
        )

        self._connections[context.connection_id] = context
        self._by_client.setdefault(transport_client_id, set()).add(context.connection_id)
        return context

    def unregister(self, connection_id: str) -> ConnectionContext | None:
        """Remove a connection from the registry.

        Safe to call more than once; the second call returns None. This is what
        guarantees no stale record survives a disconnect, however the
        connection ended (normal close, network drop, timeout, or rejection).
        """
        context = self._connections.pop(connection_id, None)
        if context is None:
            return None

        context.mark_closing()
        client_connections = self._by_client.get(context.transport_client_id)
        if client_connections is not None:
            client_connections.discard(connection_id)
            if not client_connections:
                del self._by_client[context.transport_client_id]
        return context

    # --- Lookup ------------------------------------------------------------

    def get(self, connection_id: str) -> ConnectionContext | None:
        """Return a connection by id, or None."""
        return self._connections.get(connection_id)

    def connections_for(self, transport_client_id: str) -> list[ConnectionContext]:
        """Return every live connection belonging to a transport identity."""
        ids = self._by_client.get(transport_client_id)
        if not ids:
            return []
        return [self._connections[cid] for cid in ids if cid in self._connections]

    def is_connected(self, transport_client_id: str) -> bool:
        """Whether the identity currently has at least one live connection."""
        return bool(self._by_client.get(transport_client_id))

    @property
    def connection_count(self) -> int:
        """Total live connections."""
        return len(self._connections)

    @property
    def client_count(self) -> int:
        """Distinct transport identities currently connected."""
        return len(self._by_client)

    @property
    def offline_queue(self) -> OfflineQueue:
        """The bounded in-memory offline queue."""
        return self._offline_queue

    @property
    def limits(self) -> TransportLimits:
        """Limits this manager enforces."""
        return self._limits

    # --- Routing -----------------------------------------------------------

    def deliver_to_client(self, transport_client_id: str, message: dict[str, Any]) -> bool:
        """Deliver a message to one identity's live connection(s).

        This is direct routing, never a broadcast: only connections belonging
        to `transport_client_id` are considered, and a message is never sent to
        any other identity (WS-010 / Assertion A).

        Returns True if at least one connection accepted the message. False
        means every candidate connection's bounded queue was full, which the
        caller reports as `recipient_unavailable`.
        """
        targets = self.connections_for(transport_client_id)
        if not targets:
            return False
        # Materialize the results first: a generator inside any() would
        # short-circuit on the first success and skip the identity's other
        # sessions, silently delivering to only one of them.
        accepted = [target.enqueue_outbound(message) for target in targets]
        return any(accepted)

    # --- Liveness ----------------------------------------------------------

    def stale_connections(self, now_monotonic: float) -> list[ConnectionContext]:
        """Return connections idle beyond the configured timeout."""
        timeout = self._limits.idle_timeout_seconds
        return [
            context
            for context in self._connections.values()
            if context.idle_seconds(now_monotonic) >= timeout
        ]

    def reset(self) -> None:
        """Drop all connection and queue state. Intended for tests."""
        self._connections.clear()
        self._by_client.clear()
        self._offline_queue.clear()
