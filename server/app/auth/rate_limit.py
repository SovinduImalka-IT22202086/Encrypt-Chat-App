"""Brute-force controls for authentication.

Two complementary layers (`AUTH-006`):

1. **Per-IP**, applied by `slowapi` to the login and registration routes. This
   bounds a single source hammering the endpoint.
2. **Per-account**, implemented here. Per-IP limiting alone does not protect
   one account from a distributed attack, and per-account limiting alone does
   not protect the endpoint from an attacker spraying many accounts.

The per-account counter is a sliding window that **auto-recovers** and counts
only *failures*. It deliberately does not lock an account: a permanent lockout
triggered by an attacker would itself be a denial-of-service against the
victim (explicitly called out in the Phase 3 brief). A successful login clears
the counter immediately.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class FailedLoginTracker:
    """Sliding-window failure counter keyed by normalized account identifier.

    Memory is bounded two ways: entries older than the window are discarded on
    access, and an identifier whose window empties is dropped entirely.
    """

    max_failures: int
    window_seconds: float
    _failures: dict[str, deque[float]] = field(default_factory=dict, init=False)

    def _prune(self, identifier: str, now: float) -> deque[float]:
        """Drop expired attempts and return the live window for an identifier."""
        window = self._failures.get(identifier)
        if window is None:
            window = deque()
            self._failures[identifier] = window

        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()

        if not window:
            self._failures.pop(identifier, None)
        return window

    def is_blocked(self, identifier: str, *, now: float | None = None) -> bool:
        """Whether this identifier has too many recent failures."""
        moment = time.monotonic() if now is None else now
        return len(self._prune(identifier, moment)) >= self.max_failures

    def record_failure(self, identifier: str, *, now: float | None = None) -> int:
        """Record a failed attempt and return the current failure count."""
        moment = time.monotonic() if now is None else now
        window = self._prune(identifier, moment)
        window.append(moment)
        self._failures[identifier] = window
        return len(window)

    def reset(self, identifier: str) -> None:
        """Clear an identifier's failures after a successful authentication."""
        self._failures.pop(identifier, None)

    def failure_count(self, identifier: str, *, now: float | None = None) -> int:
        """Current failure count within the window."""
        moment = time.monotonic() if now is None else now
        return len(self._prune(identifier, moment))

    @property
    def tracked_identifiers(self) -> int:
        """How many identifiers currently hold failure state."""
        return len(self._failures)

    def clear(self) -> None:
        """Drop all failure state."""
        self._failures.clear()
