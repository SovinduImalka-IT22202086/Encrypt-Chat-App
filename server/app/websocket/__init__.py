"""WebSocket transport layer (Phase 2).

Provides connection lifecycle management, direct recipient routing, strict
versioned protocol validation, delivery acknowledgements, a bounded offline
queue, Origin validation, and resource limits.

PHASE 3 SECURITY STATUS
-----------------------
AUTHENTICATION:              IMPLEMENTED - Phase 3. Connections must present a
                             valid access token before any privileged action,
                             and sender identity is derived from that token.
CRYPTOGRAPHIC IDENTITY:      NOT IMPLEMENTED - Phase 4.
IDENTITY VERIFICATION:       NOT IMPLEMENTED - Phase 4.
AUTHENTICATED KEY AGREEMENT: NOT IMPLEMENTED - Phase 5.
END-TO-END ENCRYPTION:       NOT IMPLEMENTED - Phase 6.
FORWARD-SECRECY RATCHET:     NOT IMPLEMENTED - Phase 7.

An authenticated account is NOT a cryptographically verified conversation
identity, and message payloads are still plaintext to the relay.
"""

from app.websocket.endpoint import router
from app.websocket.limits import TransportLimits, default_limits
from app.websocket.manager import ConnectionContext, ConnectionManager, ConnectionRejected
from app.websocket.protocol import (
    PRIVILEGED_TYPES,
    PROTOCOL_VERSION,
    UNAUTHENTICATED_SENDABLE_TYPES,
    WEBSOCKET_PATH,
    DeliveryStatus,
    MessageType,
)

__all__ = [
    "PRIVILEGED_TYPES",
    "PROTOCOL_VERSION",
    "UNAUTHENTICATED_SENDABLE_TYPES",
    "WEBSOCKET_PATH",
    "ConnectionContext",
    "ConnectionManager",
    "ConnectionRejected",
    "DeliveryStatus",
    "MessageType",
    "TransportLimits",
    "default_limits",
    "router",
]
