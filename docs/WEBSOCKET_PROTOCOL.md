# WebSocket Transport Protocol — v1

**Phase:** 2 — WebSocket Transport Infrastructure
**Status:** Implemented and tested for transport behaviour only.

---

## Phase 2 security limitations

Read this section before anything else.

```text
AUTHENTICATION:
NOT IMPLEMENTED — Phase 3.

CRYPTOGRAPHIC IDENTITY:
NOT IMPLEMENTED — Phase 4.

AUTHENTICATED KEY AGREEMENT:
NOT IMPLEMENTED — Phase 5.

END-TO-END ENCRYPTION:
NOT IMPLEMENTED — Phase 6.

FORWARD-SECRECY RATCHET:
NOT IMPLEMENTED — Phase 7.

TRANSPORT SECURITY STATUS:
Current Phase 2 validates routing/protocol behaviour only.
```

Additional limitations that follow from the above:

- **Connections are not authenticated.** The `client_id` query parameter selects
  a `TRANSPORT_TEST_IDENTITY`. Anyone can claim any unused identifier. It proves
  nothing about who the peer is.
- **Message payloads are plaintext.** The transport carries whatever the client
  sends. Phase 6 replaces payloads with ciphertext.
- **No replay protection.** `message_id` exists so replay/deduplication *can* be
  built on it in Phase 7. No replay resistance exists today — do not claim any.
- **Delivery acknowledgements are transport-level only.** They carry no
  cryptographic proof and do not prove the recipient's application read anything.

---

## Endpoint

```text
ws://<host>:<port>/ws/v1?client_id=<transport-identity>
```

- `client_id` is optional. If omitted, the server generates one.
- Production requires `wss://` (WS-013). Plain `ws://` is development only.

### Transport identifiers

Pattern: `^[a-z0-9][a-z0-9_-]{0,63}$` — lowercase alphanumerics, dash and
underscore, 1–64 characters, not starting with a dash or underscore.

A malformed identifier causes the **upgrade to be refused** (HTTP 403), not an
in-band error, because there is no valid connection to report an error on.

**The server is authoritative over connection→identity mapping.** It is fixed at
connection time and never updated from the contents of any client message.

---

## Connection lifecycle

```text
1. Client opens WebSocket to /ws/v1
2. Server validates Origin                  -> refuse upgrade if disallowed
3. Server validates client_id format        -> refuse upgrade if malformed
4. Server enforces connection limits        -> refuse upgrade if exceeded
5. Server accepts and registers connection
6. Server sends connection.ready
7. Server drains queued messages for this identity (as message.receipt)
8. Client sends/receives until disconnect, idle timeout, or close
9. Server unregisters the connection unconditionally
```

Step 9 runs in a `finally` block, so the registry entry is removed however the
connection ended: normal close, network drop, idle timeout, protocol close, or
server error.

---

## Message envelope

Every client→server message uses this envelope. Validation is strict: unknown
fields are **rejected**, not ignored.

```json
{
  "version": "1",
  "message_id": "3f8b2c1e-9d4a-4f7b-8c2e-1a5d6e7f8a9b",
  "type": "message.send",
  "sender": "alice",
  "recipient": "bob",
  "timestamp": "2026-09-03T10:30:00Z",
  "payload": {}
}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `version` | string | yes | Must be exactly `"1"` |
| `message_id` | string | yes | Well-formed UUID |
| `type` | string | yes | Must be in the client-sendable allowlist |
| `sender` | string | yes | Transport identifier; must match the connection |
| `recipient` | string | for `message.send` | Transport identifier |
| `timestamp` | string | yes | ISO-8601 **with** a timezone offset |
| `payload` | object | no (default `{}`) | Opaque to the transport |

`payload` is never inspected or interpreted by the server. That is deliberate:
when Phase 6 makes payloads ciphertext, nothing in the transport needs to change.

### Sender identity rule (mandatory)

The client-supplied `sender` field is **never** treated as authoritative.

- The server compares it against the identity bound to the connection.
- A mismatch is **rejected** with `WS_1007_SENDER_MISMATCH` plus a
  `message.delivery_ack` of `rejected`. The message is not routed and not queued.
- Delivered `message.receipt` messages always carry the **server-derived**
  sender.

Phase 3 replaces this transport binding with authenticated account identity.

---

## Message types

Unknown types are rejected deterministically. They are never silently ignored.

### Client → server (allowlist)

| Type | Purpose |
|---|---|
| `message.send` | Send a payload to one recipient |
| `heartbeat.ping` | Liveness check; resets the idle timer |
| `queue.status` | Ask how many messages are queued for this identity |

Any other type — including server-only types such as `connection.ready` — is
rejected with `WS_1003_UNKNOWN_MESSAGE_TYPE`. A client cannot inject
server-originated messages.

### Server → client

| Type | Purpose |
|---|---|
| `connection.ready` | Sent once after registration |
| `message.receipt` | A message routed to this connection |
| `message.delivery_ack` | Outcome of a `message.send` |
| `heartbeat.pong` | Response to `heartbeat.ping` |
| `queue.status` | Response to a `queue.status` request |
| `protocol.error` | A deterministic protocol error |

---

## Examples

### connection.ready

```json
{
  "version": "1",
  "type": "connection.ready",
  "connection_id": "9c1f0a7b4e2d43a5b6c7d8e9f0a1b2c3",
  "transport_client_id": "alice",
  "authenticated": false,
  "identity_status": "TRANSPORT_TEST_IDENTITY",
  "protocol_version": "1",
  "heartbeat_interval_seconds": 20.0,
  "idle_timeout_seconds": 60.0,
  "max_message_bytes": 65536,
  "queued_message_count": 0
}
```

`authenticated` is always `false` in Phase 2 and exists so a client can never
mistake a transport identity for an authenticated account.

### message.receipt

```json
{
  "version": "1",
  "type": "message.receipt",
  "message_id": "3f8b2c1e-9d4a-4f7b-8c2e-1a5d6e7f8a9b",
  "sender": "alice",
  "recipient": "bob",
  "timestamp": "2026-09-03T10:30:00Z",
  "payload": {"text": "transport test"}
}
```

### message.delivery_ack

```json
{
  "version": "1",
  "type": "message.delivery_ack",
  "message_id": "3f8b2c1e-9d4a-4f7b-8c2e-1a5d6e7f8a9b",
  "status": "delivered"
}
```

### protocol.error

```json
{
  "version": "1",
  "type": "protocol.error",
  "code": "WS_1002_SCHEMA_VALIDATION_FAILED",
  "detail": "Message failed schema validation.",
  "message_id": "3f8b2c1e-9d4a-4f7b-8c2e-1a5d6e7f8a9b"
}
```

`detail` is a fixed description keyed by `code`. Stack traces, exception text,
validation internals, and configuration values are never sent to clients.
`message_id` is echoed only when the inbound value was a well-formed UUID;
otherwise it is `null`.

---

## Acknowledgement semantics

A `message.send` that passes validation always produces exactly one
`message.delivery_ack`. The statuses are exact:

| Status | Meaning |
|---|---|
| `delivered` | Handed to the recipient's outbound queue on a live connection. Does **not** mean the recipient's application processed it, and carries no cryptographic proof. |
| `queued` | Recipient was not connected; the message was accepted into the bounded in-memory offline queue. |
| `recipient_unavailable` | Recipient was not reachable and the message could not be queued (offline queue full), or every live connection's outbound queue was saturated. **The message was dropped.** |
| `rejected` | Refused before routing (sender mismatch). Never routed, never queued. |

A `message.send` that fails validation receives a `protocol.error` instead of an
acknowledgement — except sender mismatch, which produces both (the error explains
why, the `rejected` acknowledgement gives the message a terminal status).

---

## Routing behaviour

- Messages are routed **only** to connections belonging to the named recipient
  identity. Private messages are never broadcast.
- If an identity has several live sessions, every one of its sessions receives
  the message. This is direct routing to one identity, not a broadcast.
- Self-addressed messages (`A -> A`) are permitted and routed back to that
  identity's own connections.
- If the recipient is not connected, the message is queued (see below).

---

## Offline queue

```text
PHASE 2 DEVELOPMENT ONLY

The current queue may carry test transport payloads in memory.

No durable plaintext message persistence is permitted.

Phase 6 will require ciphertext-only queue/storage.
```

- In-process memory only. Nothing is written to a database or to disk.
- Bounded on both axes: at most `max_queued_per_recipient` messages per
  recipient (default 50) and at most `max_queued_recipients` distinct recipients
  (default 500).
- When a bound is hit the message is **refused** (`recipient_unavailable`) rather
  than evicting an older message, so loss is visible to the sender.
- Drained in FIFO order when the recipient connects, then discarded. Queued
  messages are delivered exactly once.
- All queue state is lost on server restart. This is intentional for Phase 2.

---

## Heartbeat and idle timeout

| Setting | Default | Meaning |
|---|---|---|
| `HEARTBEAT_INTERVAL` | 20 s | How often clients *should* send `heartbeat.ping` |
| `HEARTBEAT_TIMEOUT` / idle timeout | 60 s | Server closes a connection with no inbound activity for this long |

Both values are advertised in `connection.ready` so clients do not have to guess.

Any inbound frame resets the idle timer, so an application that is actively
sending does not need heartbeats. On timeout the server sends
`WS_1013_IDLE_TIMEOUT`, closes with code `4408`, and unregisters the connection.

---

## Limits

| Limit | Env var | Default |
|---|---|---|
| Max application message size | `WS_MAX_MESSAGE_BYTES` | 65536 bytes |
| Max identifier length | `WS_MAX_IDENTIFIER_LENGTH` | 64 |
| Max total connections | `WS_MAX_TOTAL_CONNECTIONS` | 500 |
| Max connections per identity | `WS_MAX_CONNECTIONS_PER_CLIENT` | 3 |
| Max messages per window | `WS_MAX_MESSAGES_PER_WINDOW` | 30 |
| Rate-limit window | `WS_RATE_LIMIT_WINDOW_SECONDS` | 1.0 s |
| Max pending outbound per connection | `WS_MAX_PENDING_OUTBOUND` | 100 |
| Max queued per recipient | `WS_MAX_QUEUED_PER_RECIPIENT` | 50 |
| Max queued recipients | `WS_MAX_QUEUED_RECIPIENTS` | 500 |
| Idle timeout | `WS_IDLE_TIMEOUT_SECONDS` | 60.0 s |
| Heartbeat interval | `WS_HEARTBEAT_INTERVAL_SECONDS` | 20.0 s |
| Origin allowlist | `WS_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |

An unparseable or non-positive value falls back to the default rather than
disabling the bound.

**Message size** is measured on the raw UTF-8 frame *before* JSON parsing. The
check is `size > limit`, so a message of exactly the limit is accepted. Oversized
messages produce `WS_1008_MESSAGE_TOO_LARGE`; the connection stays open.

**Rate limiting** is a fixed-window counter per connection: constant memory, no
growing history. Throttled messages produce `WS_1009_RATE_LIMITED` and are not
routed. This is a Phase 2 baseline, not Phase 10's production infrastructure.

**Backpressure**: each connection has a bounded outbound queue drained by a
dedicated writer task. Routing never writes to a socket directly, so a slow
reader cannot block the sender's handler. When a recipient's queue is full,
delivery fails as `recipient_unavailable` instead of buffering without limit.

---

## Origin policy

Origin validation is **mandatory** and happens before the upgrade is accepted
(WS-002, mitigates TM-011 cross-site WebSocket hijacking).

- Default development allowlist: `http://localhost:5173`, `http://127.0.0.1:5173`.
- Configure via `WS_ALLOWED_ORIGINS` (comma-separated).
- A literal `*` is **discarded, not honoured**. Wildcard Origin policy cannot be
  configured; supplying only `*` falls back to the defaults.
- A disallowed Origin causes the handshake to be refused with HTTP 403. No
  WebSocket is established.
- **Missing Origin** (non-browser clients such as tests and CLI tools) is
  allowed by default in development and controlled by `allow_missing_origin`.
  This is an explicit, documented Phase 2 decision that Phase 10 must revisit
  before production.

CORS configuration does not protect WebSockets; this check is independent of it.

---

## Error codes

| Code | Meaning |
|---|---|
| `WS_1001_INVALID_JSON` | Frame was not valid JSON |
| `WS_1002_SCHEMA_VALIDATION_FAILED` | Envelope failed strict validation |
| `WS_1003_UNKNOWN_MESSAGE_TYPE` | Type unknown or not client-sendable |
| `WS_1004_UNSUPPORTED_PROTOCOL_VERSION` | `version` was not `"1"` |
| `WS_1005_INVALID_RECIPIENT` | Recipient missing or malformed |
| `WS_1006_RECIPIENT_UNAVAILABLE` | Recipient unreachable |
| `WS_1007_SENDER_MISMATCH` | `sender` did not match the connection identity |
| `WS_1008_MESSAGE_TOO_LARGE` | Frame exceeded the size limit |
| `WS_1009_RATE_LIMITED` | Rate limit exceeded |
| `WS_1010_ORIGIN_REJECTED` | Origin not allowed |
| `WS_1011_CONNECTION_LIMIT` | Connection limit reached |
| `WS_1012_INTERNAL_PROTOCOL_ERROR` | Internal protocol error |
| `WS_1013_IDLE_TIMEOUT` | Connection idle too long |
| `WS_1014_QUEUE_OVERFLOW` | Outgoing queue full |
| `WS_1015_INVALID_CLIENT_ID` | Transport identifier malformed |

### WebSocket close codes

| Code | Meaning |
|---|---|
| 1000 | Normal closure |
| 1008 | Policy violation (including outbound backpressure close) |
| 4400 | Invalid transport client identifier |
| 4403 | Origin rejected |
| 4408 | Idle timeout |
| 4429 | Connection limit reached |

Codes 4400, 4403 and 4429 are applied by refusing the upgrade, so a client sees
an HTTP 403 rather than a WebSocket close frame.

---

## Reconnect behaviour

- Reconnecting creates a **new** connection with a new `connection_id`. Old state
  is not revived.
- Messages queued while the identity was offline are delivered immediately after
  `connection.ready`, and `queued_message_count` says how many to expect.
- A reconnected client is **still not authenticated**. `authenticated` remains
  `false` and `identity_status` remains `TRANSPORT_TEST_IDENTITY`.
- Anyone may reconnect claiming a given `client_id`. Phase 3 makes reconnection
  meaningful by binding it to an authenticated session.

---

## Logging

Logged (structured, under the `transport` extra): `websocket_connected`,
`websocket_disconnected`, `websocket_rejected`, `websocket_idle_timeout`,
`origin_rejected`, `message_routed`, `message_queued`, `message_rejected`,
`rate_limit_triggered`, `oversized_message_rejected`,
`protocol_validation_failed`, `websocket_backpressure_close`.

Each record carries `event`, `connection_id`, `transport_client_id`, and where
relevant `message_id`, `status`, and `reason`.

**Never logged:** message payload contents, and (in later phases) passwords,
tokens, private keys, or session keys. Pydantic validation detail is not logged
either, because it can echo payload content. This is enforced by tests, not just
convention.

---

## Future authentication hook

`ConnectionContext` carries `authenticated: bool = False` and
`account_id: str | None = None`. These are placeholders for Phase 3 and must
stay `False`/`None` until then. The intent:

```text
ConnectionContext
    |
Phase 2: transport identity (unauthenticated)
    |
Phase 3: authenticated account identity
```

Phase 3 populates these from a verified session rather than from the
`client_id` query parameter, without restructuring the transport layer.
