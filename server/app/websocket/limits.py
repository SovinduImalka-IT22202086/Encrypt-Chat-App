"""Configurable transport limits and Origin policy.

Every bound the transport enforces is defined here so it is explicit,
configurable, documented, and testable rather than scattered as magic numbers.
Supports WS-002, WS-004..WS-008 and AVAIL-001..AVAIL-004 in
docs/SECURITY_REQUIREMENTS.md.

Values are read from the environment once at import time via `default_limits()`
so tests can construct their own `TransportLimits` without touching global
state.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Development Origins. Production Origins are supplied via the environment;
# a wildcard is never accepted (see `allowed_origins`).
_DEFAULT_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment, falling back to default."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _float_env(name: str, default: float) -> float:
    """Read a positive float from the environment, falling back to default."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _origins_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated Origin allowlist from the environment.

    A literal ``*`` is rejected rather than honoured: wildcard Origin policy is
    forbidden for WebSockets by WS-002, and silently accepting it would
    reintroduce the CSWSH exposure (TM-011) this control exists to close.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    parsed = tuple(item.strip() for item in raw.split(",") if item.strip() and item.strip() != "*")
    return parsed or default


@dataclass(frozen=True, slots=True)
class TransportLimits:
    """Bounds enforced by the WebSocket transport layer."""

    # --- Message size (WS-004) ---------------------------------------------
    # Application-level cap on a single inbound protocol message, measured on
    # the raw text before parsing so oversized input is dropped before any
    # expensive work happens.
    max_message_bytes: int = 64 * 1024

    # Maximum length of a transport client / recipient identifier.
    max_identifier_length: int = 64

    # --- Connection limits (WS-005) ----------------------------------------
    max_total_connections: int = 500
    max_connections_per_client: int = 3

    # --- Message rate limit (WS-008) ---------------------------------------
    # Fixed-window counter: at most `max_messages_per_window` inbound protocol
    # messages per `rate_limit_window_seconds` per connection.
    max_messages_per_window: int = 30
    rate_limit_window_seconds: float = 1.0

    # --- Backpressure (WS-007) ---------------------------------------------
    # Bounded per-connection outbound queue. When full, delivery to that
    # recipient fails deterministically instead of growing memory.
    max_pending_outbound: int = 100

    # --- Offline queue (WS-012) --------------------------------------------
    max_queued_per_recipient: int = 50
    max_queued_recipients: int = 500

    # --- Liveness (WS-006) -------------------------------------------------
    # Server closes a connection with no inbound activity for this long.
    # Clients should send heartbeat.ping well inside this window.
    idle_timeout_seconds: float = 60.0
    heartbeat_interval_seconds: float = 20.0

    # A connection that never authenticates is closed quickly: it can do
    # nothing useful and holding it open only consumes a connection slot.
    unauthenticated_timeout_seconds: float = 15.0

    # --- Origin policy (WS-002) --------------------------------------------
    allowed_origins: tuple[str, ...] = _DEFAULT_ORIGINS
    # Whether a connection with no Origin header is allowed. Browsers always
    # send Origin; non-browser clients (tests, CLI tools) do not. Defaults to
    # True for development and is documented as a Phase 2 limitation that
    # Phase 10 must revisit for production.
    allow_missing_origin: bool = True

    def is_origin_allowed(self, origin: str | None) -> bool:
        """Return whether an Origin header value is acceptable."""
        if origin is None:
            return self.allow_missing_origin
        return origin in self.allowed_origins


def default_limits() -> TransportLimits:
    """Build limits from the environment, falling back to safe defaults."""
    return TransportLimits(
        max_message_bytes=_int_env("WS_MAX_MESSAGE_BYTES", 64 * 1024),
        max_identifier_length=_int_env("WS_MAX_IDENTIFIER_LENGTH", 64),
        max_total_connections=_int_env("WS_MAX_TOTAL_CONNECTIONS", 500),
        max_connections_per_client=_int_env("WS_MAX_CONNECTIONS_PER_CLIENT", 3),
        max_messages_per_window=_int_env("WS_MAX_MESSAGES_PER_WINDOW", 30),
        rate_limit_window_seconds=_float_env("WS_RATE_LIMIT_WINDOW_SECONDS", 1.0),
        max_pending_outbound=_int_env("WS_MAX_PENDING_OUTBOUND", 100),
        max_queued_per_recipient=_int_env("WS_MAX_QUEUED_PER_RECIPIENT", 50),
        max_queued_recipients=_int_env("WS_MAX_QUEUED_RECIPIENTS", 500),
        idle_timeout_seconds=_float_env("WS_IDLE_TIMEOUT_SECONDS", 60.0),
        unauthenticated_timeout_seconds=_float_env("WS_UNAUTHENTICATED_TIMEOUT_SECONDS", 15.0),
        heartbeat_interval_seconds=_float_env("WS_HEARTBEAT_INTERVAL_SECONDS", 20.0),
        allowed_origins=_origins_env("WS_ALLOWED_ORIGINS", _DEFAULT_ORIGINS),
    )


@dataclass(slots=True)
class RateLimiter:
    """Fixed-window inbound message rate limiter for a single connection.

    Deliberately simple: Phase 2 establishes bounded behaviour, not Phase 10's
    production rate-limiting infrastructure. State is a counter and a window
    start, so it cannot grow with traffic.
    """

    max_messages: int
    window_seconds: float
    _window_started_at: float = field(default=0.0, init=False)
    _count: int = field(default=0, init=False)

    def allow(self, now: float) -> bool:
        """Record an inbound message at `now`; return False if over the limit."""
        if now - self._window_started_at >= self.window_seconds:
            self._window_started_at = now
            self._count = 0
        self._count += 1
        return self._count <= self.max_messages
