"""WebSocket Origin validation.

Assertion C (mandatory): an unauthorized WebSocket Origin is rejected. These
tests exercise the actual upgrade behaviour - a refused Origin never reaches
an accepted WebSocket (WS-002, mitigates TM-011 CSWSH).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.websocket import TransportLimits
from app.websocket.limits import default_limits
from tests.conftest import ALLOWED_ORIGIN, make_client, manager_of, ws_url


def test_allowed_origin_is_accepted(client: TestClient) -> None:
    """An allowlisted development Origin completes the upgrade."""
    with client.websocket_connect(ws_url("alice"), headers={"origin": ALLOWED_ORIGIN}) as ws:
        ready = ws.receive_json()

    assert ready["type"] == "connection.ready"


def test_loopback_origin_variant_is_accepted(client: TestClient) -> None:
    """Both documented development Origins are allowed."""
    with client.websocket_connect(
        ws_url("alice"), headers={"origin": "http://127.0.0.1:5173"}
    ) as ws:
        assert ws.receive_json()["type"] == "connection.ready"


@pytest.mark.parametrize(
    "origin",
    [
        "http://malicious.example",
        "https://evil.test",
        "http://localhost:5174",
        "https://localhost:5173",
        "http://localhost.evil.example:5173",
        "null",
        "*",
    ],
)
def test_unauthorized_origin_is_rejected(client: TestClient, origin: str) -> None:
    """Any Origin outside the allowlist is refused at the handshake."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_url("attacker"), headers={"origin": origin}) as ws:
            ws.receive_json()


def test_rejected_origin_registers_no_connection(client: TestClient) -> None:
    """A refused Origin must not leave transport state behind."""
    manager = manager_of(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            ws_url("attacker"), headers={"origin": "http://malicious.example"}
        ) as ws:
            ws.receive_json()

    assert manager.connection_count == 0
    assert not manager.is_connected("attacker")


def test_missing_origin_is_allowed_in_development(client: TestClient) -> None:
    """Missing Origin is explicitly defined behaviour, not accidental.

    Non-browser clients send no Origin header. Development allows it; this is
    documented as a Phase 2 limitation for Phase 10 to revisit.
    """
    with client.websocket_connect(ws_url("alice")) as ws:
        assert ws.receive_json()["type"] == "connection.ready"


def test_missing_origin_can_be_refused_by_configuration() -> None:
    """The permissive missing-Origin behaviour is configurable, not fixed."""
    limits = TransportLimits(allow_missing_origin=False)
    with make_client(limits) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(ws_url("alice")) as ws:
                ws.receive_json()


def test_wildcard_origin_configuration_is_not_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wildcard Origin allowlist is ignored, never accepted (WS-002)."""
    monkeypatch.setenv("WS_ALLOWED_ORIGINS", "*")
    limits = default_limits()

    assert "*" not in limits.allowed_origins
    assert not limits.is_origin_allowed("http://malicious.example")


def test_configured_origin_allowlist_is_honoured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real allowlist from the environment replaces the defaults."""
    monkeypatch.setenv("WS_ALLOWED_ORIGINS", "https://app.example, https://admin.example")
    limits = default_limits()

    assert limits.is_origin_allowed("https://app.example")
    assert limits.is_origin_allowed("https://admin.example")
    assert not limits.is_origin_allowed("http://localhost:5173")
