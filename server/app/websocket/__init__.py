"""WebSocket transport layer (Phase 2).

Provides connection lifecycle management, direct recipient routing, strict
versioned protocol validation, delivery acknowledgements, a bounded offline
queue, Origin validation, and resource limits.

PHASE 2 SECURITY LIMITATIONS
----------------------------
AUTHENTICATION:            NOT IMPLEMENTED - Phase 3.
CRYPTOGRAPHIC IDENTITY:    NOT IMPLEMENTED - Phase 4.
AUTHENTICATED KEY AGREEMENT: NOT IMPLEMENTED - Phase 5.
END-TO-END ENCRYPTION:     NOT IMPLEMENTED - Phase 6.
FORWARD-SECRECY RATCHET:   NOT IMPLEMENTED - Phase 7.

TRANSPORT SECURITY STATUS: Phase 2 validates routing/protocol behaviour only.
Connections are TRANSPORT_TEST_IDENTITY / NOT_AUTHENTICATED.
"""

from app.websocket.endpoint import router
from app.websocket.limits import TransportLimits, default_limits
from app.websocket.manager import ConnectionContext, ConnectionManager, ConnectionRejected
from app.websocket.protocol import PROTOCOL_VERSION, WEBSOCKET_PATH, DeliveryStatus, MessageType

__all__ = [
    "PROTOCOL_VERSION",
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
