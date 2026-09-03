"""Strict Pydantic schemas for the WebSocket protocol envelope.

Every inbound message is validated against `InboundEnvelope` before any
routing logic runs (WS-003). Unknown fields are rejected rather than ignored,
so a client cannot smuggle extra data past validation.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.websocket.protocol import PROTOCOL_VERSION, DeliveryStatus, MessageType

#: Transport client identifiers are deliberately restrictive: lowercase
#: alphanumerics, dash and underscore. This keeps them safe to use as dict keys
#: and log fields, and rules out control characters and homograph tricks.
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

MAX_IDENTIFIER_LENGTH = 64

TransportIdentifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_IDENTIFIER_LENGTH, pattern=IDENTIFIER_PATTERN),
]


def is_valid_identifier(value: str) -> bool:
    """Return whether a string is an acceptable transport identifier."""
    return bool(IDENTIFIER_PATTERN.fullmatch(value))


class InboundEnvelope(BaseModel):
    """A protocol message received from a client.

    `extra="forbid"` makes unexpected fields a validation failure (WS-003).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1"]
    message_id: UUID
    type: MessageType
    sender: TransportIdentifier
    recipient: TransportIdentifier | None = None
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        """Reject naive timestamps.

        A timestamp without an offset is ambiguous across clients and would
        make any future replay/ordering logic unreliable.
        """
        if value.tzinfo is None:
            msg = "timestamp must include a timezone offset"
            raise ValueError(msg)
        return value


class OutboundMessage(BaseModel):
    """Base for messages the server sends. Serialized with `mode="json"`."""

    model_config = ConfigDict(extra="forbid")

    version: Literal["1"] = PROTOCOL_VERSION


class ConnectionReady(OutboundMessage):
    """Sent once, immediately after a connection is accepted and registered.

    `authenticated` is always False in Phase 2 and is present specifically so
    the client can never mistake a transport identity for an authenticated
    account. Phase 3 owns changing it.
    """

    type: Literal[MessageType.CONNECTION_READY] = MessageType.CONNECTION_READY
    connection_id: str
    transport_client_id: str
    authenticated: Literal[False] = False
    identity_status: Literal["TRANSPORT_TEST_IDENTITY"] = "TRANSPORT_TEST_IDENTITY"
    protocol_version: Literal["1"] = PROTOCOL_VERSION
    heartbeat_interval_seconds: float
    idle_timeout_seconds: float
    max_message_bytes: int
    queued_message_count: int


class MessageReceipt(OutboundMessage):
    """A routed message delivered to its recipient.

    `sender` is always the server-derived transport identity of the originating
    connection, never a client-supplied value (WS-011 / AUTHZ-002).
    """

    type: Literal[MessageType.MESSAGE_RECEIPT] = MessageType.MESSAGE_RECEIPT
    message_id: UUID
    sender: str
    recipient: str
    timestamp: datetime
    payload: dict[str, Any]


class DeliveryAck(OutboundMessage):
    """Acknowledgement returned to the sender of a message.send."""

    type: Literal[MessageType.MESSAGE_DELIVERY_ACK] = MessageType.MESSAGE_DELIVERY_ACK
    message_id: UUID
    status: DeliveryStatus


class HeartbeatPong(OutboundMessage):
    """Response to a client heartbeat.ping."""

    type: Literal[MessageType.HEARTBEAT_PONG] = MessageType.HEARTBEAT_PONG
    message_id: UUID
    server_time: datetime


class QueueStatus(OutboundMessage):
    """Reports how many messages are queued for this connection's identity."""

    type: Literal[MessageType.QUEUE_STATUS] = MessageType.QUEUE_STATUS
    message_id: UUID
    queued_message_count: int


class ProtocolError(OutboundMessage):
    """A deterministic, non-sensitive protocol error.

    `detail` is a fixed description keyed by `code`. Exception text, stack
    traces, and internal state are never included (WS-009).
    """

    type: Literal[MessageType.PROTOCOL_ERROR] = MessageType.PROTOCOL_ERROR
    code: str
    detail: str
    message_id: UUID | None = None
