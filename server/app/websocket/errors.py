"""Deterministic protocol error codes for the WebSocket transport.

Every rejection path returns one of these codes. Codes are stable, documented
(see docs/WEBSOCKET_PROTOCOL.md), and deliberately non-sensitive: they say
what rule was broken, never why internally (no stack traces, no configuration
values, no internal identifiers). This supports WS-009 in
docs/SECURITY_REQUIREMENTS.md.
"""

from __future__ import annotations

from enum import StrEnum


class ProtocolErrorCode(StrEnum):
    """Stable protocol-level error codes sent to clients."""

    INVALID_JSON = "WS_1001_INVALID_JSON"
    SCHEMA_VALIDATION_FAILED = "WS_1002_SCHEMA_VALIDATION_FAILED"
    UNKNOWN_MESSAGE_TYPE = "WS_1003_UNKNOWN_MESSAGE_TYPE"
    UNSUPPORTED_PROTOCOL_VERSION = "WS_1004_UNSUPPORTED_PROTOCOL_VERSION"
    INVALID_RECIPIENT = "WS_1005_INVALID_RECIPIENT"
    RECIPIENT_UNAVAILABLE = "WS_1006_RECIPIENT_UNAVAILABLE"
    SENDER_MISMATCH = "WS_1007_SENDER_MISMATCH"
    MESSAGE_TOO_LARGE = "WS_1008_MESSAGE_TOO_LARGE"
    RATE_LIMITED = "WS_1009_RATE_LIMITED"
    ORIGIN_REJECTED = "WS_1010_ORIGIN_REJECTED"
    CONNECTION_LIMIT = "WS_1011_CONNECTION_LIMIT"
    INTERNAL_PROTOCOL_ERROR = "WS_1012_INTERNAL_PROTOCOL_ERROR"
    IDLE_TIMEOUT = "WS_1013_IDLE_TIMEOUT"
    QUEUE_OVERFLOW = "WS_1014_QUEUE_OVERFLOW"
    INVALID_CLIENT_ID = "WS_1015_INVALID_CLIENT_ID"


# Human-readable, non-sensitive descriptions returned alongside the code.
ERROR_DESCRIPTIONS: dict[ProtocolErrorCode, str] = {
    ProtocolErrorCode.INVALID_JSON: "Message was not valid JSON.",
    ProtocolErrorCode.SCHEMA_VALIDATION_FAILED: "Message failed schema validation.",
    ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE: "Message type is not supported.",
    ProtocolErrorCode.UNSUPPORTED_PROTOCOL_VERSION: "Protocol version is not supported.",
    ProtocolErrorCode.INVALID_RECIPIENT: "Recipient identifier is missing or malformed.",
    ProtocolErrorCode.RECIPIENT_UNAVAILABLE: "Recipient is not currently reachable.",
    ProtocolErrorCode.SENDER_MISMATCH: "Sender does not match the connection identity.",
    ProtocolErrorCode.MESSAGE_TOO_LARGE: "Message exceeds the maximum allowed size.",
    ProtocolErrorCode.RATE_LIMITED: "Message rate limit exceeded.",
    ProtocolErrorCode.ORIGIN_REJECTED: "Origin is not allowed.",
    ProtocolErrorCode.CONNECTION_LIMIT: "Connection limit reached.",
    ProtocolErrorCode.INTERNAL_PROTOCOL_ERROR: "Internal protocol error.",
    ProtocolErrorCode.IDLE_TIMEOUT: "Connection idle for too long.",
    ProtocolErrorCode.QUEUE_OVERFLOW: "Outgoing queue is full.",
    ProtocolErrorCode.INVALID_CLIENT_ID: "Transport client identifier is malformed.",
}


class WebSocketCloseCode:
    """WebSocket close codes used by this transport.

    1000/1008/1009/1011 are standard RFC 6455 codes; 4000+ are the
    application-defined range.
    """

    NORMAL = 1000
    POLICY_VIOLATION = 1008
    MESSAGE_TOO_BIG = 1009
    INTERNAL_ERROR = 1011

    ORIGIN_REJECTED = 4403
    CONNECTION_LIMIT = 4429
    RATE_LIMITED = 4430
    IDLE_TIMEOUT = 4408
    INVALID_CLIENT_ID = 4400


def describe(code: ProtocolErrorCode) -> str:
    """Return the non-sensitive description for an error code."""
    return ERROR_DESCRIPTIONS[code]
