"""Shared fixtures and helpers for the WebSocket transport tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.websocket import PROTOCOL_VERSION, WEBSOCKET_PATH, ConnectionManager, TransportLimits

ALLOWED_ORIGIN = "http://localhost:5173"


def envelope(
    *,
    sender: str,
    recipient: str | None = None,
    message_type: str = "message.send",
    payload: dict[str, Any] | None = None,
    version: str = PROTOCOL_VERSION,
    message_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a protocol envelope, defaulting every field to something valid.

    Tests override exactly the field under test, so a failure points at that
    field rather than at incidental invalidity elsewhere.
    """
    body: dict[str, Any] = {
        "version": version,
        "message_id": message_id if message_id is not None else str(uuid4()),
        "type": message_type,
        "sender": sender,
        "timestamp": timestamp
        if timestamp is not None
        else datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": payload if payload is not None else {"text": "transport test"},
    }
    if recipient is not None:
        body["recipient"] = recipient
    return body


def ws_url(client_id: str | None = None) -> str:
    """Build the WebSocket URL, optionally requesting a transport identity."""
    if client_id is None:
        return WEBSOCKET_PATH
    return f"{WEBSOCKET_PATH}?client_id={client_id}"


def make_client(limits: TransportLimits | None = None) -> TestClient:
    """Create a TestClient over an app with the given transport limits."""
    return TestClient(create_app(limits))


def manager_of(client: TestClient) -> ConnectionManager:
    """Return the live connection manager behind a TestClient."""
    app = cast("FastAPI", client.app)
    manager: ConnectionManager = app.state.ws_manager
    return manager


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient using default transport limits."""
    with make_client() as test_client:
        yield test_client
