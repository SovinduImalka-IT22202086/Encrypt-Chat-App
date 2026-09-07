"""Bounded in-memory offline queue for transport testing.

PHASE 2 DEVELOPMENT ONLY
------------------------
The current queue may carry test transport payloads in memory.

No durable plaintext message persistence is permitted.

Phase 6 will require ciphertext-only queue/storage.

Design note: this stores already-serialized envelope dictionaries and never
inspects `payload`. When Phase 6 replaces payloads with ciphertext, and when
Phase 10 swaps the in-memory backend for a durable one, neither change
requires restructuring this abstraction — the queue is deliberately ignorant
of what a payload contains. Nothing here writes to disk or to a database
(SERVER-002).
"""

from __future__ import annotations

from collections import deque
from typing import Any


class OfflineQueue:
    """Per-recipient bounded FIFO queue held only in process memory.

    Both dimensions are bounded so a sender cannot grow server memory without
    limit (AVAIL-004):

    * at most `max_per_recipient` messages for any one recipient;
    * at most `max_recipients` distinct recipients with a queue.
    """

    __slots__ = ("_max_per_recipient", "_max_recipients", "_queues")

    def __init__(self, max_per_recipient: int, max_recipients: int) -> None:
        self._queues: dict[str, deque[dict[str, Any]]] = {}
        self._max_per_recipient = max_per_recipient
        self._max_recipients = max_recipients

    def enqueue(self, recipient: str, envelope: dict[str, Any]) -> bool:
        """Queue an envelope for a recipient.

        Returns False when the message could not be accepted, either because
        this recipient's queue is full or because the server is already
        tracking the maximum number of queued recipients. Returning False
        rather than evicting keeps the failure visible to the sender as a
        `recipient_unavailable` acknowledgement instead of silently losing a
        message.
        """
        queued = self._queues.get(recipient)
        if queued is None:
            if len(self._queues) >= self._max_recipients:
                return False
            queued = deque()
            self._queues[recipient] = queued

        if len(queued) >= self._max_per_recipient:
            return False

        queued.append(envelope)
        return True

    def drain(self, recipient: str) -> list[dict[str, Any]]:
        """Remove and return every queued envelope for a recipient."""
        queued = self._queues.pop(recipient, None)
        if queued is None:
            return []
        return list(queued)

    def count(self, recipient: str) -> int:
        """Return how many envelopes are queued for a recipient."""
        queued = self._queues.get(recipient)
        return len(queued) if queued is not None else 0

    def discard(self, recipient: str) -> None:
        """Drop a recipient's queue entirely."""
        self._queues.pop(recipient, None)

    @property
    def recipient_count(self) -> int:
        """Number of recipients currently holding a queue."""
        return len(self._queues)

    @property
    def total_queued(self) -> int:
        """Total envelopes queued across all recipients."""
        return sum(len(queued) for queued in self._queues.values())

    def clear(self) -> None:
        """Drop all queued state."""
        self._queues.clear()
