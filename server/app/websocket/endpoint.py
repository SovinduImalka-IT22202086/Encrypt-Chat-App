"""FastAPI WebSocket endpoint for the transport protocol.

Connection lifecycle (Phase 3)
------------------------------
1. Validate Origin (before the upgrade is accepted).
2. Enforce connection limits.
3. Accept and register the connection as **unauthenticated**.
4. Send `connection.ready` (authenticated: false).
5. The client sends `auth.authenticate` with an access token. Until it does,
   every privileged action is refused with `WS_1016_AUTH_REQUIRED`, and the
   connection is closed if it does not authenticate within the deadline.
6. On success the connection is re-keyed onto the account identity and
   `auth.ready` is sent; queued messages for that account are drained.
7. Serve the receive loop until disconnect, idle timeout, or close.
8. Unregister, guaranteeing no stale registry entry survives.

Why the token arrives in the first message rather than a header or a cookie:
the browser WebSocket API cannot set headers, a query parameter would leak the
token into logs, history and proxies (`AUTH-008`), and cookie-based WebSocket
auth is precisely the pattern that makes cross-site WebSocket hijacking
possible. A token in the first application message avoids all three.
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

from app.auth.errors import AuthError
from app.auth.service import AuthenticatedIdentity, AuthService
from app.websocket.errors import ProtocolErrorCode, WebSocketCloseCode, describe
from app.websocket.manager import ConnectionContext, ConnectionManager, ConnectionRejected
from app.websocket.protocol import (
    CLIENT_SENDABLE_TYPES,
    PRIVILEGED_TYPES,
    PROTOCOL_VERSION,
    UNAUTHENTICATED_SENDABLE_TYPES,
    WEBSOCKET_PATH,
    DeliveryStatus,
    MessageType,
)
from app.websocket.schemas import (
    AuthReady,
    ConnectionReady,
    DeliveryAck,
    HeartbeatPong,
    InboundEnvelope,
    MessageReceipt,
    OutboundMessage,
    ProtocolError,
    QueueStatus,
)

logger = logging.getLogger("app.websocket")

router = APIRouter()

#: How long to wait for queued outbound messages to flush before closing.
_FLUSH_TIMEOUT_SECONDS = 2.0

#: Maximum accepted length of an access token in an auth.authenticate payload.
#: Bounds the work done before the token is even parsed.
_MAX_TOKEN_LENGTH = 4096


def _log(event: str, context: ConnectionContext | None = None, **fields: object) -> None:
    """Emit a structured transport event.

    Message payloads, access tokens, and refresh tokens are never logged
    (`LOG-001`, `LOG-002`). Only correlation identifiers and status fields.
    """
    record: dict[str, object] = {"event": event}
    if context is not None:
        record["connection_id"] = context.connection_id
        record["authenticated"] = context.authenticated
        if context.user_id is not None:
            record["user_id"] = context.user_id
        if context.session_id is not None:
            record["session_id"] = context.session_id
    record.update(fields)
    logger.info(event, extra={"transport": record})


def _dump(model: OutboundMessage) -> dict[str, Any]:
    """Serialize an outbound model to JSON-compatible primitives."""
    return model.model_dump(mode="json")


def _error(code: ProtocolErrorCode, message_id: UUID | None = None) -> dict[str, Any]:
    """Build a deterministic, non-sensitive protocol error message."""
    return _dump(ProtocolError(code=code.value, detail=describe(code), message_id=message_id))


def _extract_message_id(raw: object) -> UUID | None:
    """Best-effort message_id extraction for correlating a rejection."""
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
            context.outbound.task_done()
            return
        finally:
            with suppress(ValueError):
                context.outbound.task_done()


# --- Routing --------------------------------------------------------------


def _route_message(
    manager: ConnectionManager,
    context: ConnectionContext,
    envelope: InboundEnvelope,
    recipient: str,
) -> DeliveryStatus:
    """Route a validated message to exactly one recipient identity.

    The receipt's `sender` is the connection's authenticated account identity,
    never the envelope's `sender` field (`AUTHZ-002`, Assertion F).
    """
    receipt = _dump(
        MessageReceipt(
            message_id=envelope.message_id,
            sender=context.routing_identity,
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
    """Validate and route a message.send from an authenticated connection."""
    # The envelope's sender is compared against the account identity bound at
    # authentication time. A mismatch is refused and never routed under the
    # claimed identity - an authenticated user cannot impersonate another.
    if envelope.sender != context.routing_identity:
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


def _handle_privileged(
    manager: ConnectionManager,
    context: ConnectionContext,
    envelope: InboundEnvelope,
) -> list[dict[str, Any]]:
    """Dispatch an action that requires an authenticated connection."""
    if envelope.type is MessageType.MESSAGE_SEND:
        return _handle_message_send(manager, context, envelope)

    if envelope.type is MessageType.QUEUE_STATUS:
        return [
            _dump(
                QueueStatus(
                    message_id=envelope.message_id,
                    queued_message_count=manager.offline_queue.count(context.routing_identity),
                )
            )
        ]

    return [_error(ProtocolErrorCode.INTERNAL_PROTOCOL_ERROR, envelope.message_id)]


# --- Validation -----------------------------------------------------------


def _validate_inbound(
    context: ConnectionContext, raw_text: str
) -> tuple[InboundEnvelope | None, list[dict[str, Any]]]:
    """Validate one inbound frame.

    Returns the envelope when it is acceptable, otherwise the errors owed to
    the sender. Cheap structural checks run before schema validation so
    malformed input is discarded before any expensive work.
    """
    try:
        parsed: object = json.loads(raw_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _log("protocol_validation_failed", context, reason="invalid_json")
        return None, [_error(ProtocolErrorCode.INVALID_JSON)]

    if not isinstance(parsed, dict):
        _log("protocol_validation_failed", context, reason="not_an_object")
        return None, [_error(ProtocolErrorCode.SCHEMA_VALIDATION_FAILED)]

    message_id = _extract_message_id(parsed)

    if parsed.get("version") != PROTOCOL_VERSION:
        _log("protocol_validation_failed", context, reason="unsupported_version")
        return None, [_error(ProtocolErrorCode.UNSUPPORTED_PROTOCOL_VERSION, message_id)]

    raw_type = parsed.get("type")
    if not isinstance(raw_type, str) or raw_type not in set(MessageType):
        _log("protocol_validation_failed", context, reason="unknown_type")
        return None, [_error(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE, message_id)]

    message_type = MessageType(raw_type)
    if message_type not in CLIENT_SENDABLE_TYPES:
        _log("protocol_validation_failed", context, reason="server_only_type")
        return None, [_error(ProtocolErrorCode.UNKNOWN_MESSAGE_TYPE, message_id)]

    # Authorization gate: an unauthenticated connection may only authenticate
    # or keep itself alive. This runs before schema validation so an
    # unauthenticated peer learns nothing from the shape of its errors.
    if not context.authenticated and message_type not in UNAUTHENTICATED_SENDABLE_TYPES:
        _log("websocket_auth_required", context, attempted_type=message_type.value)
        return None, [_error(ProtocolErrorCode.AUTH_REQUIRED, message_id)]

    try:
        envelope = InboundEnvelope.model_validate(parsed)
    except ValidationError:
        # Validation detail is neither returned nor logged: it would leak
        # schema internals to the client and payload content to the log.
        _log("protocol_validation_failed", context, reason="schema_validation_failed")
        return None, [_error(ProtocolErrorCode.SCHEMA_VALIDATION_FAILED, message_id)]

    return envelope, []


# --- Authentication -------------------------------------------------------


async def _authenticate_connection(
    websocket: WebSocket,
    manager: ConnectionManager,
    context: ConnectionContext,
    envelope: InboundEnvelope,
) -> list[dict[str, Any]]:
    """Handle auth.authenticate, binding a verified account to the connection."""
    if context.authenticated:
        return [_error(ProtocolErrorCode.ALREADY_AUTHENTICATED, envelope.message_id)]

    raw_token = envelope.payload.get("access_token")
    if not isinstance(raw_token, str) or not raw_token or len(raw_token) > _MAX_TOKEN_LENGTH:
        _log("websocket_auth_failure", context, reason="missing_or_oversized_token")
        return [_error(ProtocolErrorCode.AUTH_FAILED, envelope.message_id)]

    service: AuthService = websocket.app.state.auth_service
    factory = websocket.app.state.session_factory

    try:
        async with factory() as db:
            identity: AuthenticatedIdentity = await service.resolve_access_token(db, raw_token)
    except AuthError as exc:
        # The specific reason (expired, revoked, malformed) is logged but not
        # returned: the client gets one generic authentication failure.
        _log("websocket_auth_failure", context, reason=exc.internal_reason or exc.code.value)
        return [_error(ProtocolErrorCode.AUTH_FAILED, envelope.message_id)]

    manager.bind_identity(
        context,
        user_id=identity.user_id,
        username=identity.username,
        session_id=identity.session_id,
    )
    _log("websocket_auth_success", context)

    responses = [
        _dump(
            AuthReady(
                message_id=envelope.message_id,
                user_id=identity.user_id,
                username=identity.username,
                session_id=identity.session_id,
            )
        )
    ]
    # Deliver anything queued while this account was offline.
    responses.extend(manager.offline_queue.drain(identity.username))
    return responses


# --- Receive loop ---------------------------------------------------------


async def _receive_loop(
    websocket: WebSocket,
    manager: ConnectionManager,
    context: ConnectionContext,
) -> int:
    """Serve inbound frames until the connection ends. Returns a close code."""
    limits = manager.limits

    while True:
        # An unauthenticated connection gets a short deadline; an
        # authenticated one gets the normal idle timeout.
        timeout = (
            limits.idle_timeout_seconds
            if context.authenticated
            else limits.unauthenticated_timeout_seconds
        )

        try:
            raw_text = await asyncio.wait_for(websocket.receive_text(), timeout=timeout)
        except TimeoutError:
            if not context.authenticated:
                _log("websocket_auth_deadline_expired", context)
                context.enqueue_outbound(_error(ProtocolErrorCode.AUTH_REQUIRED))
                return WebSocketCloseCode.AUTH_REQUIRED
            _log("websocket_idle_timeout", context)
            context.enqueue_outbound(_error(ProtocolErrorCode.IDLE_TIMEOUT))
            return WebSocketCloseCode.IDLE_TIMEOUT
        except (WebSocketDisconnect, RuntimeError):
            return WebSocketCloseCode.NORMAL

        now = time.monotonic()
        context.touch(now)

        if len(raw_text.encode("utf-8")) > limits.max_message_bytes:
            _log("oversized_message_rejected", context, size_bytes=len(raw_text))
            context.enqueue_outbound(_error(ProtocolErrorCode.MESSAGE_TOO_LARGE))
            continue

        if not context.rate_limiter.allow(now):
            _log("rate_limit_triggered", context)
            context.enqueue_outbound(_error(ProtocolErrorCode.RATE_LIMITED))
            continue

        envelope, errors = _validate_inbound(context, raw_text)
        if envelope is None:
            responses = errors
        elif envelope.type is MessageType.AUTH_AUTHENTICATE:
            responses = await _authenticate_connection(websocket, manager, context, envelope)
        elif envelope.type is MessageType.HEARTBEAT_PING:
            responses = [
                _dump(HeartbeatPong(message_id=envelope.message_id, server_time=datetime.now(UTC)))
            ]
        elif envelope.type in PRIVILEGED_TYPES:
            responses = _handle_privileged(manager, context, envelope)
        else:
            responses = [_error(ProtocolErrorCode.INTERNAL_PROTOCOL_ERROR, envelope.message_id)]

        for response in responses:
            if not context.enqueue_outbound(response):
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
    """Transport endpoint.

    Connections start unauthenticated and can do nothing privileged until they
    present a valid access token via `auth.authenticate`. Account identity is
    derived from that token server-side; the client never supplies it.
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

    # A throwaway identifier so the registry has a key before authentication.
    # It grants nothing: privileged actions are refused while unauthenticated.
    provisional_id = f"anon-{uuid4().hex}"

    remote_host = websocket.client.host if websocket.client is not None else None
    try:
        context = manager.register(provisional_id, remote_host=remote_host)
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
        context.enqueue_outbound(
            _dump(
                ConnectionReady(
                    connection_id=context.connection_id,
                    authentication_deadline_seconds=limits.unauthenticated_timeout_seconds,
                    heartbeat_interval_seconds=limits.heartbeat_interval_seconds,
                    idle_timeout_seconds=limits.idle_timeout_seconds,
                    max_message_bytes=limits.max_message_bytes,
                )
            )
        )
        close_code = await _receive_loop(websocket, manager, context)
    finally:
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
