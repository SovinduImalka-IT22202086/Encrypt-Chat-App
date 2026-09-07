"""Direct recipient routing, acknowledgements, and the no-broadcast guarantee."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.websocket import TransportLimits
from tests.conftest import envelope, make_client, manager_of, ws_url


def test_direct_routing_a_to_b(client: TestClient) -> None:
    """B receives A's message and A receives a delivered acknowledgement."""
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        message = envelope(sender="alice", recipient="bob", payload={"text": "hello"})
        ws_a.send_json(message)

        receipt = ws_b.receive_json()
        ack = ws_a.receive_json()

    assert receipt["type"] == "message.receipt"
    assert receipt["sender"] == "alice"
    assert receipt["recipient"] == "bob"
    assert receipt["payload"] == {"text": "hello"}
    assert receipt["message_id"] == message["message_id"]

    assert ack["type"] == "message.delivery_ack"
    assert ack["status"] == "delivered"
    assert ack["message_id"] == message["message_id"]


def test_direct_routing_b_to_a(client: TestClient) -> None:
    """Routing works in both directions."""
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        ws_b.send_json(envelope(sender="bob", recipient="alice", payload={"text": "hi back"}))

        receipt = ws_a.receive_json()
        ack = ws_b.receive_json()

    assert receipt["sender"] == "bob"
    assert receipt["recipient"] == "alice"
    assert ack["status"] == "delivered"


def test_private_message_is_not_delivered_to_third_party(client: TestClient) -> None:
    """Assertion A (mandatory): A->B must never reach unrelated client C.

    C sends its own heartbeat after the A->B exchange has been fully
    acknowledged. If C's first inbound frame is the pong rather than a
    receipt, no part of A's message leaked to C.
    """
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
        client.websocket_connect(ws_url("carol")) as ws_c,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_c.receive_json()

        secret = envelope(sender="alice", recipient="bob", payload={"text": "for bob only"})
        ws_a.send_json(secret)

        receipt = ws_b.receive_json()
        ack = ws_a.receive_json()
        assert receipt["payload"] == {"text": "for bob only"}
        assert ack["status"] == "delivered"

        ws_c.send_json(envelope(sender="carol", message_type="heartbeat.ping"))
        first_for_carol = ws_c.receive_json()

    assert first_for_carol["type"] == "heartbeat.pong"
    assert first_for_carol["type"] != "message.receipt"


def test_message_to_offline_recipient_is_queued(client: TestClient) -> None:
    """An unavailable recipient yields a deterministic queued status."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": "later"}))
        ack = ws_a.receive_json()

        assert ack["status"] == "queued"
        assert manager.offline_queue.count("bob") == 1


def test_queued_message_is_delivered_on_reconnect(client: TestClient) -> None:
    """Queued transport data is drained when the recipient connects."""
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        sent = envelope(sender="alice", recipient="bob", payload={"text": "while away"})
        ws_a.send_json(sent)
        assert ws_a.receive_json()["status"] == "queued"

    with client.websocket_connect(ws_url("bob")) as ws_b:
        ready = ws_b.receive_json()
        assert ready["queued_message_count"] == 1
        receipt = ws_b.receive_json()

    assert receipt["type"] == "message.receipt"
    assert receipt["message_id"] == sent["message_id"]
    assert receipt["sender"] == "alice"


def test_offline_queue_is_drained_once(client: TestClient) -> None:
    """A drained queue does not redeliver on the next connection."""
    manager = manager_of(client)
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient="bob"))
        ws_a.receive_json()

    with client.websocket_connect(ws_url("bob")) as ws_b:
        ws_b.receive_json()
        ws_b.receive_json()

    assert manager.offline_queue.count("bob") == 0

    with client.websocket_connect(ws_url("bob")) as ws_b:
        ready = ws_b.receive_json()
        assert ready["queued_message_count"] == 0


def test_offline_queue_overflow_reports_recipient_unavailable() -> None:
    """A full offline queue fails deterministically instead of growing."""
    limits = TransportLimits(max_queued_per_recipient=2)
    with make_client(limits) as client:
        manager = manager_of(client)
        with client.websocket_connect(ws_url("alice")) as ws_a:
            ws_a.receive_json()
            statuses = []
            for _ in range(4):
                ws_a.send_json(envelope(sender="alice", recipient="bob"))
                statuses.append(ws_a.receive_json()["status"])

        assert statuses == ["queued", "queued", "recipient_unavailable", "recipient_unavailable"]
        assert manager.offline_queue.count("bob") == 2


def test_self_addressed_message_is_routed_back(client: TestClient) -> None:
    """A->A is permitted and routed to that identity's own connection."""
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient="alice", payload={"text": "note"}))

        first = ws_a.receive_json()
        second = ws_a.receive_json()

    types = {first["type"], second["type"]}
    assert types == {"message.receipt", "message.delivery_ack"}


def test_message_send_without_recipient_is_rejected(client: TestClient) -> None:
    """message.send requires a recipient."""
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        ws_a.send_json(envelope(sender="alice"))
        error = ws_a.receive_json()

    assert error["type"] == "protocol.error"
    assert error["code"] == "WS_1005_INVALID_RECIPIENT"


def test_delivery_to_every_session_of_one_identity(client: TestClient) -> None:
    """Direct routing reaches each live session of the target identity only."""
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b1,
        client.websocket_connect(ws_url("bob")) as ws_b2,
        client.websocket_connect(ws_url("carol")) as ws_c,
    ):
        for socket in (ws_a, ws_b1, ws_b2, ws_c):
            socket.receive_json()

        ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": "both"}))

        assert ws_b1.receive_json()["payload"] == {"text": "both"}
        assert ws_b2.receive_json()["payload"] == {"text": "both"}
        assert ws_a.receive_json()["status"] == "delivered"

        ws_c.send_json(envelope(sender="carol", message_type="heartbeat.ping"))
        assert ws_c.receive_json()["type"] == "heartbeat.pong"


@pytest.mark.parametrize("recipient", ["Bob", "bob!", "b" * 65, ""])
def test_malformed_recipient_is_rejected(client: TestClient, recipient: str) -> None:
    """Malformed recipient identifiers fail schema validation."""
    with client.websocket_connect(ws_url("alice")) as ws_a:
        ws_a.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient=recipient))
        error = ws_a.receive_json()

    assert error["type"] == "protocol.error"
    assert error["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"
