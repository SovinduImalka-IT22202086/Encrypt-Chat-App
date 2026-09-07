"""Connection lifecycle tests: registration, limits, cleanup, reconnect."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.websocket import PROTOCOL_VERSION, TransportLimits
from tests.conftest import make_client, manager_of, ws_url


def test_connection_ready_is_first_message(client: TestClient) -> None:
    """A new connection receives a deterministic connection.ready."""
    with client.websocket_connect(ws_url("alice")) as ws:
        ready = ws.receive_json()

    assert ready["type"] == "connection.ready"
    assert ready["version"] == PROTOCOL_VERSION
    assert ready["protocol_version"] == PROTOCOL_VERSION
    assert ready["transport_client_id"] == "alice"
    assert ready["connection_id"]
    assert ready["queued_message_count"] == 0


def test_connection_ready_never_claims_authentication(client: TestClient) -> None:
    """Phase 2 must not present a connection as authenticated."""
    with client.websocket_connect(ws_url("alice")) as ws:
        ready = ws.receive_json()

    assert ready["authenticated"] is False
    assert ready["identity_status"] == "TRANSPORT_TEST_IDENTITY"


def test_server_generates_identity_when_not_requested(client: TestClient) -> None:
    """Omitting client_id yields a server-generated transport identity."""
    with client.websocket_connect(ws_url()) as ws:
        ready = ws.receive_json()

    assert ready["transport_client_id"]
    assert ready["transport_client_id"] != ""


def test_multiple_clients_connect_and_are_tracked(client: TestClient) -> None:
    """The registry reflects every live connection."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        assert manager.connection_count == 1

        with client.websocket_connect(ws_url("bob")) as ws_b:
            ws_b.receive_json()
            assert manager.connection_count == 2
            assert manager.client_count == 2
            assert manager.is_connected("alice")
            assert manager.is_connected("bob")


def test_disconnect_removes_connection_from_registry(client: TestClient) -> None:
    """Assertion F: disconnected clients are removed from active state."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws:
        ws.receive_json()
        assert manager.is_connected("alice")

    assert manager.connection_count == 0
    assert manager.client_count == 0
    assert not manager.is_connected("alice")


def test_reconnect_produces_fresh_connection_id(client: TestClient) -> None:
    """Reconnecting registers new state rather than reviving the old entry."""
    manager = manager_of(client)

    with client.websocket_connect(ws_url("alice")) as ws:
        first = ws.receive_json()["connection_id"]
    assert manager.connection_count == 0

    with client.websocket_connect(ws_url("alice")) as ws:
        second = ws.receive_json()["connection_id"]
        assert manager.connection_count == 1

    assert first != second
    assert manager.connection_count == 0


def test_same_identity_may_hold_several_connections(client: TestClient) -> None:
    """Multiple sessions per transport identity are allowed up to the limit."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as first:
        first.receive_json()
        with client.websocket_connect(ws_url("alice")) as second:
            second.receive_json()
            assert manager.connection_count == 2
            assert manager.client_count == 1
            assert len(manager.connections_for("alice")) == 2


def test_total_connection_limit_rejects_upgrade() -> None:
    """Exceeding the global connection limit denies the WebSocket upgrade."""
    with make_client(TransportLimits(max_total_connections=1)) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(ws_url("bob")) as rejected:
                    rejected.receive_json()


def test_per_client_connection_limit_rejects_upgrade() -> None:
    """Exceeding the per-identity connection limit denies the upgrade."""
    limits = TransportLimits(max_connections_per_client=1)
    with make_client(limits) as client:
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(ws_url("alice")) as rejected:
                    rejected.receive_json()


def test_connection_slot_is_released_after_limit_rejection() -> None:
    """A rejected connection must not leak a registry slot."""
    with make_client(TransportLimits(max_total_connections=1)) as client:
        manager = manager_of(client)
        with client.websocket_connect(ws_url("alice")) as ws:
            ws.receive_json()
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(ws_url("bob")) as rejected:
                    rejected.receive_json()
            assert manager.connection_count == 1

    assert manager.connection_count == 0


@pytest.mark.parametrize(
    "client_id",
    [
        "UPPERCASE",
        "has space",
        "has/slash",
        "-leading-dash",
        "a" * 65,
        "unicodeé",
    ],
)
def test_malformed_client_identifier_rejects_upgrade(client: TestClient, client_id: str) -> None:
    """Malformed transport identifiers are refused at the handshake."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_url(client_id)) as ws:
            ws.receive_json()


def test_empty_client_identifier_rejects_upgrade(client: TestClient) -> None:
    """An explicitly empty client_id is malformed, not 'unspecified'."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"{ws_url()}?client_id=") as ws:
            ws.receive_json()
