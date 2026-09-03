"""FastAPI WebSocket endpoint for the Phase 2 transport protocol.

Connection lifecycle
--------------------
1. Validate Origin (before the upgrade is accepted).
2. Validate the requested transport client identifier.
3. Enforce connection limits.
4. Accept, register, and send `connection.ready`.
5. Drain any offline-queued messages for that identity.
6. Serve the receive loop until disconnect, idle timeout, or close.
7. Unregister, guaranteeing no stale registry entry survives.

Sending is done exclusively by a writer task draining a bounded per-connection
queue, so a slow reader cannot block routing for other connections or grow
memory without limit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.websocket.errors import ProtocolErrorCode, WebSocketCloseCode, describe
from app.websocket.manager import ConnectionContext, ConnectionManager, ConnectionRejected
from app.websocket.protocol import (
    CLIENT_SENDABLE_TYPES,
    PROTOCOL_VERSION,
    WEBSOCKET_PATH,
    DeliveryStatus,
    MessageType,
)
from app.websocket.schemas import (
    ConnectionReady,
    DeliveryAck,
    HeartbeatPong,
    InboundEnvelope,
    MessageReceipt,
    OutboundMessage,
    ProtocolError,
    QueueStatus,
    is_valid_identifier,
)

logger = logging.getLogger("app.websocket")

router = APIRouter()

#: How long to wait for queued outbound messages to flush before closing.
_FLUSH_TIMEOUT_SECONDS = 2.0


def _log(event: str, context: ConnectionContext | None = None, **fields: object) -> None:
    """Emit a structured transport event.

    Message payload contents are never logged (LOG-001). Only correlation
    identifiers and status fields are recorded, which is enough to debug
    routing without exposing message content.
    """
    record: dict[str, object] = {"event": event}
    if context is not None:
        record["connection_id"] = context.connection_id
        record["transport_client_id"] = context.transport_client_id
    record.update(fields)
    logger.info(event, extra={"transport": record})


def _dump(model: OutboundMessage) -> dict[str, Any]:
    """Serialize an outbound model to JSON-compatible primitives."""
    return model.model_dump(mode="json")


def _error(code: ProtocolErrorCode, message_id: UUID | None = None) -> dict[str, Any]:
    """Build a deterministic, non-sensitive protocol error message."""
    return _dump(ProtocolError(code=code.value, detail=describe(code), message_id=message_id))


def _extract_message_id(raw: object) -> UUID | None:
    """Best-effort message_id extraction for correlating a rejection.

    Returns None unless the value is a genuinely well-formed UUID, so a
    malformed message can never inject arbitrary text into an error response.
    """
    if not isinstance(raw, dict):
        return None
    candidate = raw.get("message_id")
    if not isinstance(candidate, str):
        return None
    try:
        return UUID(candidate)
    except ValueError:
        return None


async def _writer_loop(websocket: WebSocket, context: ConnectionContext) -> None:
    """Drain the connection's bounded outbound queue to the socket."""
    while True:
        message = await context.outbound.get()
        try:
            await websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError):
            # Socket already gone; stop writing. The receive loop owns cleanup.
            context.outbound.task_done()
            return
        finally:
            with suppress(ValueError):
                context.outbound.task_done()


def _route_message(
    manager: ConnectionManager,
    context: ConnectionContext,
    envelope: InboundEnvelope,
    recipient: str,
) -> DeliveryStatus:
    """Route a validated message to exactly one recipient identity.

    The receipt's `sender` is taken from the connection context, never from the
    envelope, so a delivered message always attributes the connection that
    actually sent it (WS-011).
    """
    receipt = _dump(
        MessageReceipt(
            message_id=envelope.message_id,
            sender=context.transport_client_id,
            recipient=recipient,
            timestamp=envelope.timestamp,
            payload=envelope.payload,
        )
    )

    if manager.is_connected(recipient):
        if manager.deliver_to_client(recipient, receipt):
            _log(
                "message_routed",
                context,
                message_id=str(envelope.message_id),
                status=DeliveryStatus.DELIVERED.value,
            )
            return DeliveryStatus.DELIVERED
        # Every candidate connection's outbound queue was saturated.
        _log(
            "message_rejected",
            context,
            message_id=str(envelope.message_id),
            reason="outbound_queue_full",
        )
        return DeliveryStatus.RECIPIENT_UNAVAILABLE

    if manager.offline_queue.enqueue(recipient, receipt):
        _log(
            "message_queued",
            context,
            message_id=str(envelope.message_id),
            status=DeliveryStatus.QUEUED.value,
        )
        return DeliveryStatus.QUEUED

    _log(
        "message_rejected",
        context,
        message_id=str(envelope.message_id),
        reason="offline_queue_full",
    )
    return DeliveryStatus.RECIPIENT_UNAVAILABLE


def _handle_message_send(
    manager: ConnectionManager,
    context: ConnectionContext,
    envelope: InboundEnvelope,
) -> list[dict[str, Any]]:
    """Validate and route a message.send, returning responses for the sender."""
    # Sender spoofing: the envelope's sender is compared against the identity
    # the server bound at connection time. A mismatch is rejected outright and
    # never routed under the claimed identity (Assertion B / AUTHZ-002).
    if envelope.sender != context.transport_client_id:
        _log(
            "message_rejected",
            context,
            message_id=str(envelope.message_id),
            reason="sender_mismatch",
        )
        return [
            _error(ProtocolErrorCode.SENDER_MISMATCH, envelope.message_id),
            _dump(DeliveryAck(message_id=envelope.message_id, status=DeliveryStatus.REJECTED)),
        ]

    recipient = envelope.recipient
    if recipient is None:
        return [_error(ProtocolErrorCode.INVALID_RECIPIENT, envelope.message_id)]

    status = _route_message(manager, context, envelope, recipient)
    return [_dump(DeliveryAck(message_id=envelope.message_id, status=status))]


def _handle_inbound(
    manager: ConnectionManager,
    context: ConnectionContext,
    raw_text: str,
) -> list[dict[str, Any]]:
    """Validate one inbound frame and produce the responses owed to the sender.

    Ordering matters: cheap structural checks run before schema validation so
    malformed input is discarded before any expensive work.
    """
    try:
        parsed: object = json.loads(raw_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _log("protocol_validation_failed", context, reason="invalid_json")
        return [_error(ProtocolErrorCode.INVALID_JSON)]

    if not isinstance(parsed, dict):
        _log("protocol_validation_failed", context, reason="not_an_object")
        return [_error(ProtocolErrorCode.SCHEMA_VALIDATION_FAILED)]

    message_id = _extract_message_id(parsed)

    # Version is checked before type so a client on an unsupported protocol
    # gets an accurate version error rather than a confusing type error.
    version = parsed.get("version")
    if version != PROTOCOL_VERSION:
        _log("protocol_validation_failed", context, reason="unsupported_version")
        return [_error(ProtocolErrorCode.UNSUPPORTED_PROTOCOL_VERSION, message_id)]

    raw_type = parsed.get("type")
    if not isinstance(raw_type, str) or raw_type not in set(MessageType):
        _log("protocol_validation_failed", context, reason="unknown_type")
        return [_error(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE, message_id)]

    message_type = MessageType(raw_type)
    if message_type not in CLIENT_SENDABLE_TYPES:
        # Server-only types (e.g. connection.ready) must not be injectable.
        _log("protocol_validation_failed", context, reason="server_only_type")
        return [_error(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE, message_id)]

    try:
        envelope = InboundEnvelope.model_validate(parsed)
    except ValidationError:
        # Validation detail is deliberately not forwarded to the client: it
        # would leak internal schema structure. It is not logged either,
        # because it can echo payload content (LOG-001).
        _log("protocol_validation_failed", context, reason="schema_validation_failed")
        return [_error(ProtocolErrorCode.SCHEMA_VALIDATION_FAILED, message_id)]

    if envelope.type is MessageType.MESSAGE_SEND:
        return _handle_message_send(manager, context, envelope)

    if envelope.type is MessageType.HEARTBEAT_PING:
        return [_dump(HeartbeatPong(message_id=envelope.message_id, server_time=datetime.now(UTC)))]

    if envelope.type is MessageType.QUEUE_STATUS:
        return [
            _dump(
                QueueStatus(
                    message_id=envelope.message_id,
                    queued_message_count=manager.offline_queue.count(context.transport_client_id),
                )
            )
        ]

    # Unreachable: CLIENT_SENDABLE_TYPES is exhaustively handled above. Kept as
    # a fail-closed guard rather than falling through silently.
    return [_error(ProtocolErrorCode.INTERNAL_PROTOCOL_ERROR, envelope.message_id)]


async def _receive_loop(
    websocket: WebSocket,
    manager: ConnectionManager,
    context: ConnectionContext,
) -> int:
    """Serve inbound frames until the connection ends. Returns a close code."""
    limits = manager.limits

    while True:
        try:
            raw_text = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=limits.idle_timeout_seconds,
            )
        except TimeoutError:
            _log("websocket_idle_timeout", context)
            context.enqueue_outbound(_error(ProtocolErrorCode.IDLE_TIMEOUT))
            return WebSocketCloseCode.IDLE_TIMEOUT
        except (WebSocketDisconnect, RuntimeError):
            return WebSocketCloseCode.NORMAL

        now = time.monotonic()
        context.touch(now)

        # Size is checked on the raw frame, before parsing (Assertion E).
        if len(raw_text.encode("utf-8")) > limits.max_message_bytes:
            _log("oversized_message_rejected", context, size_bytes=len(raw_text))
            context.enqueue_outbound(_error(ProtocolErrorCode.MESSAGE_TOO_LARGE))
            continue

        if not context.rate_limiter.allow(now):
            _log("rate_limit_triggered", context)
            context.enqueue_outbound(_error(ProtocolErrorCode.RATE_LIMITED))
            continue

        for response in _handle_inbound(manager, context, raw_text):
            if not context.enqueue_outbound(response):
                # This connection's own outbound queue is saturated; stop
                # rather than spin, and let the client reconnect.
                _log("websocket_backpressure_close", context)
                return WebSocketCloseCode.POLICY_VIOLATION


async def _reject_upgrade(
    websocket: WebSocket,
    code: int,
    error_code: ProtocolErrorCode,
    **log_fields: object,
) -> None:
    """Deny a WebSocket upgrade before accepting it."""
    _log("websocket_rejected", None, reason=error_code.value, **log_fields)
    await websocket.close(code=code)


@router.websocket(WEBSOCKET_PATH)
async def websocket_transport(websocket: WebSocket) -> None:
    """Phase 2 transport endpoint.

    PHASE 2 LIMITATION: connections are NOT_AUTHENTICATED. The
    `client_id` query parameter selects a TRANSPORT_TEST_IDENTITY only; it
    proves nothing about who the peer is. Phase 3 replaces it with an
    authenticated account/session identity.
    """
    manager: ConnectionManager = websocket.app.state.ws_manager
    limits = manager.limits

    # --- Origin (WS-002, mitigates TM-011 CSWSH) ---------------------------
    origin = websocket.headers.get("origin")
    if not limits.is_origin_allowed(origin):
        _log("origin_rejected", None)
        await _reject_upgrade(
            websocket,
            WebSocketCloseCode.ORIGIN_REJECTED,
            ProtocolErrorCode.ORIGIN_REJECTED,
        )
        return

    # --- Transport identity ------------------------------------------------
    requested = websocket.query_params.get("client_id")
    transport_client_id = requested if requested is not None else uuid4().hex
    if not is_valid_identifier(transport_client_id):
        await _reject_upgrade(
            websocket,
            WebSocketCloseCode.INVALID_CLIENT_ID,
            ProtocolErrorCode.INVALID_CLIENT_ID,
        )
        return

    # --- Connection limits (WS-005) ----------------------------------------
    remote_host = websocket.client.host if websocket.client is not None else None
    try:
        context = manager.register(transport_client_id, remote_host=remote_host)
    except ConnectionRejected:
        await _reject_upgrade(
            websocket,
            WebSocketCloseCode.CONNECTION_LIMIT,
            ProtocolErrorCode.CONNECTION_LIMIT,
        )
        return

    await websocket.accept()
    _log("websocket_connected", context, active_connections=manager.connection_count)

    close_code = WebSocketCloseCode.NORMAL
    writer = asyncio.create_task(_writer_loop(websocket, context))
    try:
        queued = manager.offline_queue.drain(transport_client_id)
        context.enqueue_outbound(
            _dump(
                ConnectionReady(
                    connection_id=context.connection_id,
                    transport_client_id=transport_client_id,
                    heartbeat_interval_seconds=limits.heartbeat_interval_seconds,
                    idle_timeout_seconds=limits.idle_timeout_seconds,
                    max_message_bytes=limits.max_message_bytes,
                    queued_message_count=len(queued),
                )
            )
        )
        for envelope in queued:
            context.enqueue_outbound(envelope)

        close_code = await _receive_loop(websocket, manager, context)
    finally:
        # Flush anything already queued, then tear the connection down. The
        # registry entry is removed unconditionally so no stale record can
        # survive a disconnect however it ended (Assertion F).
        context.mark_closing()
        with suppress(TimeoutError, asyncio.CancelledError):
            await asyncio.wait_for(context.outbound.join(), timeout=_FLUSH_TIMEOUT_SECONDS)
        writer.cancel()
        with suppress(asyncio.CancelledError):
            await writer
        manager.unregister(context.connection_id)
        _log("websocket_disconnected", context, active_connections=manager.connection_count)
        with suppress(RuntimeError):
            await websocket.close(code=close_code)
