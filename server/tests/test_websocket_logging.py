"""Logging hygiene and plaintext-persistence safety.

Two Phase 0 requirements are guarded here:

* LOG-001 - server logs must not contain private-message content.
* SERVER-002 - no durable plaintext message persistence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import envelope, manager_of, ws_url

WEBSOCKET_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "websocket"

MARKER = "extremely-distinctive-payload-marker-for-log-scanning"


def _transport_extra(record: logging.LogRecord) -> dict[str, Any] | None:
    """Return a record's structured transport payload, if it has one.

    `transport` is attached via logging `extra`, so it is not a declared
    LogRecord attribute and must be read dynamically.
    """
    extra = getattr(record, "transport", None)
    return extra if isinstance(extra, dict) else None


def _all_log_text(records: list[logging.LogRecord]) -> str:
    """Flatten every record - message, args, and structured extras - to text."""
    parts: list[str] = []
    for record in records:
        parts.append(str(record.getMessage()))
        parts.append(str(record.args))
        extra = _transport_extra(record)
        if extra is not None:
            parts.append(str(extra))
    return " ".join(parts)


def test_message_payload_is_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """LOG-001: routing a message must not write its content to the log."""
    with caplog.at_level(logging.DEBUG, logger="app.websocket"):
        with (
            client.websocket_connect(ws_url("alice")) as ws_a,
            client.websocket_connect(ws_url("bob")) as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": MARKER}))
            assert ws_b.receive_json()["payload"] == {"text": MARKER}
            assert ws_a.receive_json()["status"] == "delivered"

    assert MARKER not in _all_log_text(caplog.records)


def test_queued_message_payload_is_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Queuing a message for an offline recipient must not log its content."""
    with caplog.at_level(logging.DEBUG, logger="app.websocket"):
        with client.websocket_connect(ws_url("alice")) as ws_a:
            ws_a.receive_json()
            ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": MARKER}))
            assert ws_a.receive_json()["status"] == "queued"

    assert MARKER not in _all_log_text(caplog.records)


def test_rejected_message_payload_is_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """A schema failure must not log the offending payload either."""
    with caplog.at_level(logging.DEBUG, logger="app.websocket"):
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            message = envelope(sender="alice", recipient="bob")
            message["payload"] = {"text": MARKER}
            message["unexpected_field"] = MARKER
            ws.send_json(message)
            assert ws.receive_json()["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"

    assert MARKER not in _all_log_text(caplog.records)


def test_transport_events_are_structured(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Events carry correlation identifiers, which is what makes content
    logging unnecessary in the first place."""
    with caplog.at_level(logging.INFO, logger="app.websocket"):
        with (
            client.websocket_connect(ws_url("alice")) as ws_a,
            client.websocket_connect(ws_url("bob")) as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json(envelope(sender="alice", recipient="bob"))
            ws_b.receive_json()
            ws_a.receive_json()

    extras = [e for e in (_transport_extra(r) for r in caplog.records) if e is not None]
    events = {extra["event"] for extra in extras}
    assert "websocket_connected" in events
    assert "message_routed" in events

    routed = next(extra for extra in extras if extra["event"] == "message_routed")
    assert set(routed) == {
        "event",
        "connection_id",
        "transport_client_id",
        "message_id",
        "status",
    }


def test_rejection_events_are_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    """Security-relevant rejections are observable without content."""
    with caplog.at_level(logging.INFO, logger="app.websocket"):
        with client.websocket_connect(ws_url("attacker")) as ws:
            ws.receive_json()
            ws.send_json(envelope(sender="victim", recipient="target"))
            ws.receive_json()
            ws.receive_json()

    extras = [e for e in (_transport_extra(r) for r in caplog.records) if e is not None]
    reasons = {extra.get("reason") for extra in extras}
    assert "sender_mismatch" in reasons


# --- Plaintext persistence safety ----------------------------------------


def test_offline_queue_holds_no_state_after_clear(client: TestClient) -> None:
    """Queue state is in-process only and fully discardable."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws:
        ws.receive_json()
        ws.send_json(envelope(sender="alice", recipient="bob"))
        ws.receive_json()

    assert manager.offline_queue.total_queued == 1
    manager.offline_queue.clear()
    assert manager.offline_queue.total_queued == 0
    assert manager.offline_queue.recipient_count == 0


@pytest.mark.parametrize(
    "forbidden",
    ["sqlite3", "psycopg", "sqlalchemy", "shelve", "pickle", "aiofiles"],
)
def test_transport_imports_no_persistence_library(forbidden: str) -> None:
    """SERVER-002: the transport must not gain a durable storage backend.

    A guard test: if a future change introduces message persistence here, it
    fails loudly rather than quietly contradicting the threat model.
    """
    for source in WEBSOCKET_PACKAGE.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert f"import {forbidden}" not in text, f"{source.name} imports {forbidden}"


def test_transport_writes_no_files() -> None:
    """The transport package performs no file writes."""
    for source in WEBSOCKET_PACKAGE.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert ".write_text(" not in text, f"{source.name} writes a file"
        assert ".write_bytes(" not in text, f"{source.name} writes a file"
        assert "open(" not in text.replace("# ", ""), f"{source.name} opens a file"
