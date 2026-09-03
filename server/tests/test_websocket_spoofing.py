"""Sender-spoofing resistance at the transport layer.

Assertion B (mandatory): a client cannot impersonate another sender by
modifying the `sender` field. The server derives sender identity from the
connection, never from the message body (WS-011 / AUTHZ-002).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import envelope, manager_of, ws_url


def test_spoofed_sender_is_rejected(client: TestClient) -> None:
    """A mismatched sender field is refused, not silently rewritten."""
    with client.websocket_connect(ws_url("attacker")) as ws:
        ws.receive_json()
        ws.send_json(envelope(sender="victim", recipient="target"))

        error = ws.receive_json()
        ack = ws.receive_json()

    assert error["type"] == "protocol.error"
    assert error["code"] == "WS_1007_SENDER_MISMATCH"
    assert ack["type"] == "message.delivery_ack"
    assert ack["status"] == "rejected"


def test_spoofed_message_never_reaches_the_recipient(client: TestClient) -> None:
    """The victim's peer must not receive anything attributed to the victim."""
    with (
        client.websocket_connect(ws_url("attacker")) as ws_attacker,
        client.websocket_connect(ws_url("target")) as ws_target,
    ):
        ws_attacker.receive_json()
        ws_target.receive_json()

        ws_attacker.send_json(
            envelope(sender="victim", recipient="target", payload={"text": "trust me"})
        )
        assert ws_attacker.receive_json()["code"] == "WS_1007_SENDER_MISMATCH"
        assert ws_attacker.receive_json()["status"] == "rejected"

        # The target's next inbound frame is its own pong: nothing was routed.
        ws_target.send_json(envelope(sender="target", message_type="heartbeat.ping"))
        first_for_target = ws_target.receive_json()

    assert first_for_target["type"] == "heartbeat.pong"


def test_spoofed_message_is_not_queued_for_offline_victim(client: TestClient) -> None:
    """A rejected spoof must not reach the offline queue either."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("attacker")) as ws:
        ws.receive_json()
        ws.send_json(envelope(sender="victim", recipient="offline-user"))
        ws.receive_json()
        ws.receive_json()

        assert manager.offline_queue.count("offline-user") == 0
        assert manager.offline_queue.total_queued == 0


def test_receipt_sender_is_the_connection_identity(client: TestClient) -> None:
    """Delivered receipts carry the server-derived sender, always."""
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        ws_a.send_json(envelope(sender="alice", recipient="bob"))
        receipt = ws_b.receive_json()

    assert receipt["sender"] == "alice"


def test_server_only_message_types_cannot_be_injected(client: TestClient) -> None:
    """A client cannot forge server-originated types such as connection.ready."""
    with client.websocket_connect(ws_url("attacker")) as ws:
        ws.receive_json()
        for forged in (
            "connection.ready",
            "message.receipt",
            "message.delivery_ack",
            "heartbeat.pong",
            "protocol.error",
        ):
            ws.send_json(envelope(sender="attacker", recipient="target", message_type=forged))
            error = ws.receive_json()
            assert error["type"] == "protocol.error"
            assert error["code"] == "WS_1003_UNKNOWN_MESSAGE_TYPE"
