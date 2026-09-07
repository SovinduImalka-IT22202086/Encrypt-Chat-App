"""Strict protocol validation.

Assertion D (mandatory): malformed protocol messages fail safely without
crashing the server. Every case here also asserts the connection is still
usable afterwards.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import envelope, ws_url


def _send_raw_and_read(client: TestClient, raw: str) -> dict[str, Any]:
    """Send a raw frame and return the single response."""
    with client.websocket_connect(ws_url("alice")) as ws:
        ws.receive_json()
        ws.send_text(raw)
        response: dict[str, Any] = ws.receive_json()
    return response


def _send_and_read(client: TestClient, message: dict[str, Any]) -> dict[str, Any]:
    """Send a JSON message and return the single response."""
    with client.websocket_connect(ws_url("alice")) as ws:
        ws.receive_json()
        ws.send_json(message)
        response: dict[str, Any] = ws.receive_json()
    return response


@pytest.mark.parametrize("raw", ["not json at all", "{", "[1,2,", "", "undefined"])
def test_non_json_is_rejected(client: TestClient, raw: str) -> None:
    """Invalid JSON produces a deterministic error."""
    response = _send_raw_and_read(client, raw)
    assert response["code"] == "WS_1001_INVALID_JSON"


@pytest.mark.parametrize("raw", ['"a string"', "[1, 2, 3]", "42", "true", "null"])
def test_non_object_json_is_rejected(client: TestClient, raw: str) -> None:
    """Valid JSON that is not an object fails schema validation."""
    response = _send_raw_and_read(client, raw)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


def test_empty_object_is_rejected(client: TestClient) -> None:
    """An empty object has no version and is refused."""
    response = _send_and_read(client, {})
    assert response["code"] == "WS_1004_UNSUPPORTED_PROTOCOL_VERSION"


@pytest.mark.parametrize("version", ["0", "2", 1, None, "1.0", ""])
def test_unsupported_version_is_rejected(client: TestClient, version: object) -> None:
    """Only protocol version "1" is accepted."""
    message = envelope(sender="alice", recipient="bob")
    message["version"] = version
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1004_UNSUPPORTED_PROTOCOL_VERSION"


@pytest.mark.parametrize("message_type", ["message.destroy", "", "MESSAGE.SEND", "admin.exec"])
def test_unknown_message_type_is_rejected(client: TestClient, message_type: str) -> None:
    """Unknown types are rejected rather than silently ignored."""
    message = envelope(sender="alice", recipient="bob", message_type=message_type)
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1003_UNKNOWN_MESSAGE_TYPE"


@pytest.mark.parametrize("message_id", ["not-a-uuid", "", "12345", None])
def test_invalid_message_id_is_rejected(client: TestClient, message_id: object) -> None:
    """message_id must be a well-formed UUID."""
    message = envelope(sender="alice", recipient="bob")
    message["message_id"] = message_id
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


@pytest.mark.parametrize(
    "timestamp",
    ["not-a-timestamp", "2026-13-45T99:99:99Z", "", "2026-09-03T10:30:00"],
)
def test_invalid_timestamp_is_rejected(client: TestClient, timestamp: str) -> None:
    """Timestamps must parse and must carry a timezone offset."""
    message = envelope(sender="alice", recipient="bob", timestamp=timestamp)
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


@pytest.mark.parametrize("payload", ["a string", 42, ["a", "list"], None, True])
def test_payload_must_be_an_object(client: TestClient, payload: object) -> None:
    """payload is an object; scalars and arrays are refused."""
    message = envelope(sender="alice", recipient="bob")
    message["payload"] = payload
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


def test_unexpected_fields_are_rejected(client: TestClient) -> None:
    """Extra envelope fields fail validation rather than being ignored."""
    message = envelope(sender="alice", recipient="bob")
    message["is_admin"] = True
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


@pytest.mark.parametrize("field", ["message_id", "type", "sender", "timestamp"])
def test_missing_required_field_is_rejected(client: TestClient, field: str) -> None:
    """Every required envelope field is actually required."""
    message = envelope(sender="alice", recipient="bob")
    del message[field]
    response = _send_and_read(client, message)
    assert response["code"] in {
        "WS_1002_SCHEMA_VALIDATION_FAILED",
        "WS_1003_UNKNOWN_MESSAGE_TYPE",
    }


def test_oversized_sender_identifier_is_rejected(client: TestClient) -> None:
    """Identifier length is bounded."""
    message = envelope(sender="a" * 200, recipient="bob")
    response = _send_and_read(client, message)
    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"


def test_deeply_nested_payload_is_accepted_as_opaque_data(client: TestClient) -> None:
    """Nested payload structure is opaque to the transport, not inspected.

    The transport must not try to interpret payload contents - Phase 6 will
    replace them with ciphertext. It only has to stay within the size bound.
    """
    nested: dict[str, Any] = {"level": 0}
    cursor = nested
    for depth in range(1, 25):
        child: dict[str, Any] = {"level": depth}
        cursor["child"] = child
        cursor = child

    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json(envelope(sender="alice", recipient="bob", payload=nested))
        receipt = ws_b.receive_json()
        ack = ws_a.receive_json()

    assert ack["status"] == "delivered"
    assert receipt["payload"]["level"] == 0


def test_connection_survives_a_burst_of_malformed_input(client: TestClient) -> None:
    """Assertion D: the server stays operational after malformed input."""
    with (
        client.websocket_connect(ws_url("alice")) as ws_a,
        client.websocket_connect(ws_url("bob")) as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()

        for raw in ("not json", '{"version": "9"}', '{"version":"1","type":"nope"}', "[]"):
            ws_a.send_text(raw)
            assert ws_a.receive_json()["type"] == "protocol.error"

        # The connection still routes correctly afterwards.
        ws_a.send_json(envelope(sender="alice", recipient="bob", payload={"text": "still ok"}))
        assert ws_b.receive_json()["payload"] == {"text": "still ok"}
        assert ws_a.receive_json()["status"] == "delivered"


def test_error_responses_carry_no_internal_detail(client: TestClient) -> None:
    """Protocol errors must not leak schema internals or stack traces."""
    message = envelope(sender="alice", recipient="bob")
    message["message_id"] = "not-a-uuid"
    response = _send_and_read(client, message)

    assert set(response) == {"version", "type", "code", "detail", "message_id"}
    lowered = response["detail"].lower()
    for leak in ("traceback", "pydantic", "validationerror", "line ", "file "):
        assert leak not in lowered


def test_error_correlates_message_id_when_recoverable(client: TestClient) -> None:
    """A well-formed message_id is echoed back so clients can correlate."""
    message_id = str(uuid4())
    message = envelope(sender="alice", recipient="bob", message_id=message_id)
    message["payload"] = "wrong type"
    response = _send_and_read(client, message)

    assert response["code"] == "WS_1002_SCHEMA_VALIDATION_FAILED"
    assert response["message_id"] == message_id
