# Phase 2 Evidence Log

**Phase:** 2 — WebSocket Transport Infrastructure
**Date:** 2026-09-03
**Scope:** Transport correctness and abuse resistance only. **No
authentication, cryptographic identity, key agreement, end-to-end encryption,
ratcheting, or cryptographic replay protection was implemented.**

All command output recorded here is actual output from this machine. Nothing is
fabricated or paraphrased into a success it did not have.

---

## 1. Previous-phase verification (before any Phase 2 work)

| Phase | Gate | Verified |
|---|---|---|
| 0 | `PHASE 0: COMPLETE` in `docs/PHASE_0_EVIDENCE.md` | Yes |
| 1 | `PHASE 1: COMPLETE` in `docs/PHASE_1_EVIDENCE.md` | Yes |

Phase 0 documentation (threat model, security requirements, ASVS mapping,
assumptions) and Phase 1 configuration (CI, lint/test setup, dependency
locking) were read before any change. **No Phase 0 or Phase 1 evidence file was
overwritten.**

The Phase 1 baseline was re-run first and passed unchanged:

```text
Ruff (lint) PASS   Ruff (format) PASS   mypy PASS   pytest PASS (4 tests)
pip-audit PASS     ESLint PASS          TypeScript PASS
Vitest PASS (3)    Frontend build PASS  npm audit PASS   Gitleaks PASS
ALL CHECKS PASSED.
```

---

## 2. Dependencies added

Added to `server/requirements.in` and recompiled through the Phase 1 pip-tools
strategy (`pip-compile requirements.in --output-file requirements.txt
--strip-extras`):

| Package | Version | Reason |
|---|---|---|
| `websockets` | 16.1.1 | Standalone client for the multi-client test against a real server |
| `pytest-asyncio` | 1.4.0 | Async test support (strict mode) |

Pinned package count: **73 → 74** (the two direct additions plus their
transitive closure, minus overlap with what was already pinned).

No other package was installed.

---

## 3. Files created

**Backend transport layer** (`server/app/websocket/`)

| File | Responsibility |
|---|---|
| `__init__.py` | Package exports and the Phase 2 limitations notice |
| `protocol.py` | Protocol version, message-type allowlist, delivery statuses |
| `schemas.py` | Strict Pydantic envelope and outbound message models |
| `errors.py` | 15 deterministic protocol error codes + WebSocket close codes |
| `limits.py` | Configurable transport limits, Origin policy, rate limiter |
| `queue.py` | Bounded in-memory offline queue |
| `manager.py` | Connection registry, connection context, direct routing |
| `endpoint.py` | FastAPI WebSocket endpoint and receive/writer loops |

**Backend tests** (`server/tests/`): `__init__.py`, `conftest.py`,
`test_websocket_connection.py`, `test_websocket_routing.py`,
`test_websocket_schema.py`, `test_websocket_spoofing.py`,
`test_websocket_origin.py`, `test_websocket_limits.py`,
`test_websocket_lifecycle.py`, `test_websocket_logging.py`,
`test_websocket_multiclient.py`.

**Frontend** (`client/src/transport/`): `protocol.ts`, `TransportTester.tsx`,
`TransportTester.test.tsx`.

**Documentation**: `docs/WEBSOCKET_PROTOCOL.md`, `docs/PHASE_2_EVIDENCE.md`.

## 4. Files modified

| File | Change |
|---|---|
| `server/app/main.py` | Refactored to a `create_app(limits)` factory; mounts the WebSocket router; health reports `"phase": "2"` |
| `server/pyproject.toml` | Added `asyncio_mode = "strict"` and `asyncio_default_fixture_loop_scope` |
| `server/requirements.in` / `requirements.txt` | Added the two dependencies above |
| `server/tests/test_smoke.py` | Health assertion `"phase": "1"` → `"2"`; docstring updated |
| `client/src/App.tsx` | Mounts the transport panel; status list and phase label updated |
| `client/src/App.test.tsx` | Capability count 7 → 6 (WebSocket transport moved out of the not-implemented list) |
| `client/src/App.css` | Styles for the transport panel |
| `client/package.json` / `package-lock.json` | Added `@testing-library/user-event` |
| `README.md` | Phase 2 status, run instructions, WebSocket section, structure |
| `CHANGELOG.md` | Phase 2 entry |
| `docs/ASVS_MAPPING.md` | Appended Phase 2 implementation status; Phase 0 baseline table unchanged |

---

## 5. WebSocket architecture

**Endpoint:** `/ws/v1` (versioned), `client_id` query parameter optional.

**Connection identity.** The server is authoritative. `client_id` selects a
`TRANSPORT_TEST_IDENTITY`, validated against `^[a-z0-9][a-z0-9_-]{0,63}$`; if
omitted the server generates one. The mapping is fixed at connection time and
never updated from message contents.

```text
PHASE 2 LIMITATION

Transport identifiers are not authenticated account identities.

Phase 3 will bind WebSocket actions to authenticated account/session identity.
```

**Connection manager.** A single `ConnectionManager` instance is owned by the
application on `app.state.ws_manager` — not a module-level global, so each app
instance (including one per test) has isolated state. It owns registration,
recipient lookup, limit enforcement, direct delivery, stale detection, and
unregistration.

**Message flow.**

```text
Client A --message.send--> receive loop
                             |-- size check (raw frame, pre-parse)
                             |-- rate limit
                             |-- JSON parse
                             |-- version / type allowlist
                             |-- strict schema validation
                             |-- sender == connection identity?
                             |-- route to recipient identity only
                             v
                    recipient bounded outbound queue
                             v
                    per-connection writer task --> Client B
                             |
                             +--> message.delivery_ack --> Client A
```

Routing never writes to a socket directly. Each connection has a bounded
outbound `asyncio.Queue` drained by a dedicated writer task, so a slow reader
cannot block the sender's handler or grow memory without limit.

**Queue.** Bounded, in-process memory only, drained FIFO on reconnect.

---

## 6. Protocol

```text
Protocol version:  1
Envelope fields:   version, message_id, type, sender, recipient, timestamp, payload
Client-sendable:   message.send, heartbeat.ping, queue.status
Server-sent:       connection.ready, message.receipt, message.delivery_ack,
                   heartbeat.pong, queue.status, protocol.error
Error-code scheme: WS_1001..WS_1015, deterministic and non-sensitive
```

Unknown types — including server-only types such as `connection.ready` — are
rejected with `WS_1003_UNKNOWN_MESSAGE_TYPE`, never ignored. Unknown envelope
fields are rejected (`extra="forbid"`).

Full specification: [WEBSOCKET_PROTOCOL.md](WEBSOCKET_PROTOCOL.md).

---

## 7. Direct routing verification

| Scenario | Result | Test |
|---|---|---|
| A → B | `message.receipt` to B, `delivered` ack to A | `test_direct_routing_a_to_b` |
| B → A | Symmetric | `test_direct_routing_b_to_a` |
| A → B with C connected | **C receives nothing**; C's next frame is its own pong | `test_private_message_is_not_delivered_to_third_party` |
| A → B over real sockets with C connected | C's `recv()` times out — nothing was sent to it | `test_no_broadcast_over_real_sockets` |
| A → offline B | `queued`; delivered on B's reconnect with `queued_message_count: 1` | `test_message_to_offline_recipient_is_queued`, `test_queued_message_is_delivered_on_reconnect` |
| A → offline B, queue full | `recipient_unavailable`, message dropped, queue stays at its bound | `test_offline_queue_overflow_reports_recipient_unavailable` |
| A → A | Allowed and routed back to A's own connections | `test_self_addressed_message_is_routed_back` |
| A → invalid recipient | `WS_1002_SCHEMA_VALIDATION_FAILED` | `test_malformed_recipient_is_rejected` |
| A → missing recipient | `WS_1005_INVALID_RECIPIENT` | `test_message_send_without_recipient_is_rejected` |
| A → B where B has 2 sessions | Both of B's sessions receive it; C receives nothing | `test_delivery_to_every_session_of_one_identity` |

### Sender spoofing (Assertion B)

A connection registered as `attacker` sending `"sender": "victim"`:

- receives `WS_1007_SENDER_MISMATCH` and a `message.delivery_ack` of `rejected`;
- the message is **not routed** — the target's next frame is its own pong;
- the message is **not queued** — `offline_queue.total_queued == 0`;
- delivered receipts always carry the server-derived sender.

Tests: `test_websocket_spoofing.py` (5 tests).

---

## 8. Origin security

Allowed by default: `http://localhost:5173`, `http://127.0.0.1:5173`
(configurable via `WS_ALLOWED_ORIGINS`).

| Origin | Result |
|---|---|
| `http://localhost:5173` | Accepted |
| `http://127.0.0.1:5173` | Accepted |
| `http://malicious.example` | Upgrade refused |
| `https://evil.test` | Upgrade refused |
| `http://localhost:5174` (wrong port) | Upgrade refused |
| `https://localhost:5173` (wrong scheme) | Upgrade refused |
| `http://localhost.evil.example:5173` (prefix trick) | Upgrade refused |
| `null` | Upgrade refused |
| `*` sent as an Origin | Upgrade refused |
| `WS_ALLOWED_ORIGINS="*"` configured | Discarded, not honoured; defaults retained |
| Missing Origin | Allowed in development (explicit, configurable) |
| Missing Origin with `allow_missing_origin=False` | Upgrade refused |

Rejection happens **before** the upgrade is accepted. Over a real socket the
client observes **HTTP 403**, asserted in
`test_unauthorized_origin_is_rejected_over_a_real_handshake`. A rejected Origin
registers no connection (`connection_count == 0`).

Tests: `test_websocket_origin.py` (14 tests).

---

## 9. Resource controls

```text
Maximum message size:  65536 bytes (WS_MAX_MESSAGE_BYTES), checked on the raw
                       frame before parsing; `size > limit` rejects, so exactly
                       the limit is accepted
Connection limit:      500 total (WS_MAX_TOTAL_CONNECTIONS),
                       3 per identity (WS_MAX_CONNECTIONS_PER_CLIENT)
Message rate limit:    30 per 1.0 s per connection, fixed window
Outgoing queue limit:  100 pending per connection (WS_MAX_PENDING_OUTBOUND)
Offline queue limits:  50 per recipient, 500 recipients
Heartbeat:             heartbeat.ping/pong, advertised interval 20 s
Idle timeout:          60 s (WS_IDLE_TIMEOUT_SECONDS)
```

Verified behaviour:

- **Size**: exact-boundary test constructs a frame of precisely the limit
  (accepted) and limit + 1 (rejected with `WS_1008_MESSAGE_TOO_LARGE`).
  Oversized messages are not routed and the connection survives.
- **Rate**: with a limit of 3/window, frames 1–3 get pongs and 4–6 get
  `WS_1009_RATE_LIMITED`. Throttled messages are not routed. The window resets,
  so throttling is temporary. Limiter state is a counter and a window start —
  10,000 calls do not grow it.
- **Connection limits**: both global and per-identity caps refuse the upgrade,
  in-process and over real sockets. A rejected connection leaks no registry
  slot; capacity is reclaimed on unregister; unregister is idempotent.
- **Backpressure**: a connection with `max_pending_outbound=3` accepts exactly
  3 then returns `False`; delivery to a saturated recipient returns `False`,
  surfaced to the sender as `recipient_unavailable` rather than buffering.
- **Offline queue**: bounded per recipient and in recipient count. Under a
  flood of 50 recipients × 50 messages against limits of 5 and 10, the queue
  held exactly 5 recipients and 50 messages total.
- **Invalid configuration** (`"0"`, `"-5"`, `"not-a-number"`, `""`) falls back
  to the default rather than disabling the bound.

Tests: `test_websocket_limits.py` (25 tests).

---

## 10. Heartbeat, idle timeout, disconnect and reconnect

- `heartbeat.ping` → `heartbeat.pong` with the same `message_id`.
- `connection.ready` advertises `heartbeat_interval_seconds` (20) and
  `idle_timeout_seconds` (60); the interval is asserted to be strictly less
  than the timeout.
- An idle connection receives `WS_1013_IDLE_TIMEOUT`, is closed, and is removed
  from the registry (verified with a 0.3 s timeout).
- Activity resets the idle timer; a pinging client is not closed.
- Disconnect removes the connection unconditionally: `connection_count == 0`,
  `client_count == 0`, `is_connected() == False`.
- Reconnect produces a **new** `connection_id` and restores routing.
- 25 sequential connect/disconnect cycles leave no residue.
- A reconnected client is still `authenticated: false` /
  `TRANSPORT_TEST_IDENTITY`.

Tests: `test_websocket_lifecycle.py` (12 tests), `test_websocket_connection.py`
(17 tests).

---

## 11. Malformed-protocol testing

All of the following are rejected with a deterministic code, and the connection
remains usable afterwards:

non-JSON (`not json at all`, `{`, `[1,2,`, empty, `undefined`); valid JSON that
is not an object (string, array, number, boolean, null); empty object; missing
`message_id` / `type` / `sender` / `timestamp`; invalid UUID; naive timestamp
(no offset); malformed timestamp; `payload` as string/number/array/null/bool;
unexpected extra fields; oversized sender identifier; unsupported versions
(`"0"`, `"2"`, `1`, `null`, `"1.0"`, `""`); unknown types
(`message.destroy`, `MESSAGE.SEND`, `admin.exec`, `""`); server-only types.

Deeply nested payloads (25 levels) are accepted as **opaque data** — the
transport must not interpret payload contents, since Phase 6 replaces them with
ciphertext.

**Error hygiene**: a `protocol.error` contains exactly
`{version, type, code, detail, message_id}`; `detail` is a fixed string keyed by
`code`. Asserted to contain no `traceback`, `pydantic`, `validationerror`,
`line `, or `file `. A well-formed `message_id` is echoed for correlation; a
malformed one yields `null`, so a client cannot inject arbitrary text into an
error response.

Tests: `test_websocket_schema.py` (44 tests).

---

## 12. Multi-client test (real sockets)

Driven against a real `uvicorn` server on an ephemeral port using the
`websockets` client — real handshake, real framing.

| Test | Result |
|---|---|
| 20 clients connect, 10 pairs exchange messages | 20 distinct `connection_id`s, all `authenticated: false`; 10 delivered receipts, 10 `delivered` acks |
| 8 clients connect then all disconnect | `connection_count` 8 → 0 and `client_count` 0, asserted on the live server object |
| Unauthorized Origin | HTTP 403 on the upgrade |
| A→B with C connected | C's `recv()` times out; nothing leaked |
| Connection cap of 3 | Fourth upgrade refused |

```text
5 passed in 1.85s
```

**Scope caveat:** this is a correctness and cleanup signal on one machine. It is
**not** a benchmark and supports no scalability claim.

---

## 13. Logging and plaintext-persistence safety

**Logging.** Structured events are emitted under a `transport` extra:
`websocket_connected`, `websocket_disconnected`, `websocket_rejected`,
`websocket_idle_timeout`, `origin_rejected`, `message_routed`,
`message_queued`, `message_rejected`, `rate_limit_triggered`,
`oversized_message_rejected`, `protocol_validation_failed`,
`websocket_backpressure_close`.

A `message_routed` record contains exactly
`{event, connection_id, transport_client_id, message_id, status}` — correlation
identifiers, no content.

Tests plant a distinctive marker string in a payload and scan **every** captured
log record (message, args, and structured extra) for it across three paths:
routed, queued, and schema-rejected. The marker never appears. Pydantic
validation detail is deliberately not logged either, because it can echo payload
content.

**Persistence.** No durable plaintext message persistence exists:

- the offline queue is a `dict` of `deque` in process memory, fully discardable;
- guard tests assert the transport package imports none of `sqlite3`, `psycopg`,
  `sqlalchemy`, `shelve`, `pickle`, `aiofiles`;
- guard tests assert it performs no `open(`, `.write_text(`, or `.write_bytes(`.

These are regression guards: if a future change introduces message persistence
here, the suite fails rather than quietly contradicting the threat model.

Tests: `test_websocket_logging.py` (13 tests).

---

## 14. Defects found and fixed during Phase 2

| # | Defect | Root cause | Fix |
|---|---|---|---|
| 1 | A message to an identity with two live sessions reached only one of them; the second connection then hung until the 60 s idle timeout | `deliver_to_client` used `any(generator)`, which **short-circuits** on the first success and never evaluates the remaining connections | Materialize the results list before `any()`, so every session is offered the message. Comment added explaining why |
| 2 | `ruff` reported unused unpacked variables in the multi-client tests | `running_server` was changed to yield `(port, app)`; some tests do not use the app | Renamed to `_application` only in the tests that genuinely do not use it |
| 3 | `mypy` reported `conftest` found under two module names | `tests/` had no `__init__.py` while tests import `tests.conftest` | Added `server/tests/__init__.py` |
| 4 | `mypy` rejected `connect(origin=str)` | `websockets` types `origin` as the `Origin` NewType | Wrapped values in `Origin(...)` from `websockets.typing` |
| 5 | `mypy` rejected `client.app.state` and `record.transport` | `TestClient.app` is typed `ASGIApp`; `transport` is a dynamic logging extra, not a `LogRecord` attribute | Narrowed with `cast("FastAPI", ...)`; added a `_transport_extra()` helper that reads the attribute dynamically and type-checks it |
| 6 | `ruff` S105 flagged a test constant as a hardcoded password | The constant was named `SECRET_TEXT` | Renamed to `MARKER` — it is a log-scanning marker, not a credential |
| 7 | A multi-client test asserted nothing about server state | It closed sockets and slept, so it would have passed even if cleanup were broken | Rewrote it to hold the live app, assert `connection_count == 8`, then poll until it reaches 0 and assert that |

Defect 1 is the significant one: it was a real routing bug that the test suite
caught, and it would have silently dropped messages for any identity with more
than one session.

---

## 15. Validation results

```text
Ruff:            PASS   All checks passed!
Ruff Format:     PASS   22 files already formatted
mypy:            PASS   Success: no issues found in 22 source files
pytest:          PASS   153 passed in 3.38s
pip-audit:       PASS   No known vulnerabilities found
Pre-commit:      PASS   13/13 hooks
Gitleaks:        PASS   no leaks found
ESLint:          PASS
TypeScript:      PASS
Vitest:          PASS   Test Files 2 passed (2) / Tests 11 passed (11)
Frontend build:  PASS
npm audit:       PASS   found 0 vulnerabilities

scripts\check-all.ps1 -> ALL CHECKS PASSED. (exit 0)
```

### Backend test distribution (153 total)

| Suite | Tests |
|---|---|
| `test_websocket_schema.py` | 44 |
| `test_websocket_limits.py` | 25 |
| `test_websocket_connection.py` | 17 |
| `test_websocket_origin.py` | 14 |
| `test_websocket_routing.py` | 14 |
| `test_websocket_logging.py` | 13 |
| `test_websocket_lifecycle.py` | 12 |
| `test_websocket_multiclient.py` | 5 |
| `test_websocket_spoofing.py` | 5 |
| `test_smoke.py` (pre-existing) | 4 |

Frontend: `App.test.tsx` 3, `TransportTester.test.tsx` 8.

---

## 16. Security test assertions

| Assertion | Status | Evidence |
|---|---|---|
| **A** — A→B is not delivered to unrelated C | PASS | `test_private_message_is_not_delivered_to_third_party`; `test_no_broadcast_over_real_sockets` (real sockets) |
| **B** — Client cannot impersonate another sender | PASS | `test_websocket_spoofing.py` — rejected, not routed, not queued |
| **C** — Unauthorized Origin is rejected | PASS | `test_websocket_origin.py`; HTTP 403 on a real handshake |
| **D** — Malformed messages fail safely without crashing | PASS | 44 schema tests; `test_connection_survives_a_burst_of_malformed_input` routes correctly afterwards |
| **E** — Oversized messages rejected before uncontrolled processing | PASS | Size checked on the raw frame pre-parse; boundary test; not routed |
| **F** — Disconnected clients removed from active state | PASS | Registry drains to 0 in-process and over real sockets; idle timeout and 25-cycle tests |
| **G** — Resource/queue behaviour is bounded | PASS | Outbound queue, offline queue, rate limiter, and connection caps all asserted at their bounds |

---

## 17. Phase 2 test matrix

```text
[x] WebSocket endpoint works
[x] Multiple clients can connect
[x] Server tracks connections correctly
[x] Direct A->B routing works
[x] Private messages are never broadcast
[x] Unavailable-recipient behaviour is deterministic
[x] Delivery acknowledgements work
[x] Queue abstraction works
[x] Disconnect cleanup works
[x] Reconnect behaviour works
[x] Unknown message types rejected
[x] Invalid schemas rejected
[x] Sender spoofing rejected/prevented
[x] Invalid identifiers rejected
[x] Oversized payload rejected
[x] Maximum message size enforced
[x] Connection limits enforced
[x] Message flood/resource controls work
[x] Backpressure is bounded
[x] Heartbeat behaviour works
[x] Idle timeout works
[x] Allowed Origin accepted
[x] Unauthorized Origin rejected
[x] Message payloads not written to normal logs
[x] No durable plaintext message persistence introduced
[x] All Python tests pass
[x] Ruff passes
[x] Formatting passes
[x] mypy passes
[x] Existing Phase 1 security baseline remains intact
[x] Authentication NOT prematurely implemented
[x] E2EE NOT prematurely implemented
```

---

## 18. Phase 2 security limitations

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

Also **not** implemented and not claimed:

- **Replay protection.** `message_id` exists so Phase 7 can build
  replay/deduplication on it. No replay resistance exists today.
- **Message confidentiality.** Payloads are plaintext on the wire and in the
  queue. The relay can read them. This is exactly what Phase 6 fixes.
- **Identity assurance.** Anyone may claim any unused `client_id`.

---

## 19. Open items and known limitations

1. **`allow_missing_origin` defaults to `True`.** Non-browser clients send no
   Origin header, so development allows it. Deliberate and configurable, but
   Phase 10 must revisit it for production.
2. **Queue state is lost on restart.** Intentional for Phase 2; durable
   (ciphertext-only) storage is Phase 6/10 work.
3. **Rate limiting is per connection, in process.** A single actor opening
   several connections gets proportionally more throughput, bounded by the
   per-identity connection cap. Distributed rate limiting is Phase 10.
4. **No WSS in development.** `ws://` locally; `wss://` is required in
   production (WS-013, Phase 10).
5. **Frame-level size limits are the ASGI server's.** Phase 2 enforces the
   application-level cap; tuning uvicorn's own frame limit is Phase 10.
6. **CI has still not executed.** The workflow runs the same commands validated
   here locally, but the repository's first CI run has not happened.
7. **Carried over from Phase 1:** LICENSE unresolved; security reporting
   channel is a placeholder; WSL2 virtualization disabled.

---

## 20. Phase 2 exit gate

**Gate:** *"Reliable direct transport passes functional and abuse-oriented tests
before cryptographic code is introduced."*

```text
Does reliable direct WebSocket transport pass functional and
abuse-oriented testing before cryptography is introduced?

YES
```

Supporting evidence: 153 backend tests and 11 frontend tests pass; all seven
mandatory security assertions have automated evidence; every item of the Phase 2
test matrix is satisfied; connection lifecycle, direct-only routing, strict
protocol validation, transport-level spoofing resistance, Origin validation,
bounded resources, queue behaviour, acknowledgements, and disconnect/reconnect
correctness are each covered by tests that fail if the behaviour regresses. The
routing bug found in §14 demonstrates the suite catches real defects rather than
confirming intent.

```text
PHASE 2: COMPLETE
```

No Phase 3 implementation has been started. Awaiting explicit Phase 3
authorization.
