"""Protocol constants: version and the message-type allowlist.

Message types are an explicit allowlist. Anything not listed is rejected
deterministically with WS_1003_UNKNOWN_MESSAGE_TYPE — unsupported types are
never silently ignored.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

#: Wire protocol version. Clients must send exactly this value.
PROTOCOL_VERSION: Final[Literal["1"]] = "1"

#: WebSocket route for this protocol version.
WEBSOCKET_PATH: Final[str] = "/ws/v1"


class MessageType(StrEnum):
    """Every message type this protocol defines."""

    # Server -> client
    CONNECTION_READY = "connection.ready"
    MESSAGE_RECEIPT = "message.receipt"
    MESSAGE_DELIVERY_ACK = "message.delivery_ack"
    HEARTBEAT_PONG = "heartbeat.pong"
    PROTOCOL_ERROR = "protocol.error"
    AUTH_READY = "auth.ready"

    # Client -> server
    MESSAGE_SEND = "message.send"
    HEARTBEAT_PING = "heartbeat.ping"
    AUTH_AUTHENTICATE = "auth.authenticate"

    # Client -> server (request) and server -> client (response)
    QUEUE_STATUS = "queue.status"


#: Types a client is permitted to send. Everything else is rejected, including
#: server-only types such as connection.ready — a client must not be able to
#: inject them.
CLIENT_SENDABLE_TYPES: Final[frozenset[MessageType]] = frozenset(
    {
        MessageType.AUTH_AUTHENTICATE,
        MessageType.MESSAGE_SEND,
        MessageType.HEARTBEAT_PING,
        MessageType.QUEUE_STATUS,
    }
)

#: Types an UNAUTHENTICATED connection may send. Everything else is refused
#: with WS_1016_AUTH_REQUIRED until the connection authenticates (Phase 3).
#: heartbeat is allowed so a client can hold the socket open while it obtains
#: an access token.
UNAUTHENTICATED_SENDABLE_TYPES: Final[frozenset[MessageType]] = frozenset(
    {
        MessageType.AUTH_AUTHENTICATE,
        MessageType.HEARTBEAT_PING,
    }
)

#: Actions that require an authenticated connection.
PRIVILEGED_TYPES: Final[frozenset[MessageType]] = frozenset(
    {
        MessageType.MESSAGE_SEND,
        MessageType.QUEUE_STATUS,
    }
)


class DeliveryStatus(StrEnum):
    """Delivery acknowledgement statuses.

    Meanings are exact and must not be blurred:

    * ``delivered``            - handed to the recipient's outbound queue on a
                                 live connection. It does NOT mean the
                                 recipient's application has processed it, and
                                 it carries no cryptographic proof.
    * ``queued``               - recipient was not connected; the envelope was
                                 accepted into the bounded in-memory offline
                                 queue for later delivery.
    * ``recipient_unavailable`` - recipient was not connected and the message
                                 could not be queued (queue full), or the
                                 recipient's outbound queue was saturated.
                                 The message was dropped.
    * ``rejected``             - the message was refused before routing (for
                                 example sender mismatch). Never routed.
    """

    DELIVERED = "delivered"
    QUEUED = "queued"
    RECIPIENT_UNAVAILABLE = "recipient_unavailable"
    REJECTED = "rejected"
