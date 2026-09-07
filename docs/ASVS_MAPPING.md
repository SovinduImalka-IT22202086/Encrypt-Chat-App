# OWASP ASVS 5.0.0 Mapping

**Target:** Level 2 baseline, with elevated consideration for cryptography,
authentication, session management, key management, secure communication, and
stored cryptographic material (approaching Level 3 rigor in those specific
areas, without formally claiming Level 3 overall).

**Status legend:**
- `REQUIREMENT_DEFINED` — requirement exists in `SECURITY_REQUIREMENTS.md`, no implementation yet.
- `PLANNED` — control is planned for a specific future phase.
- `NOT_APPLICABLE` — ASVS item does not apply to this system's architecture.
- `OUT_OF_SCOPE` — explicitly excluded per `THREAT_MODEL.md §15`.
- `BLOCKED` — cannot be defined until an open decision (see `SECURITY_ASSUMPTIONS.md`) resolves.

The table below is the **Phase 0 requirement baseline**, recorded before any
code existed, and is kept unchanged as the original contract. No item in it is
marked implemented.

Implementation status as controls are actually built is tracked in the
per-phase sections appended at the end of this document — currently
[Phase 2 implementation status](#phase-2-implementation-status-websocket-transport).

| Internal Requirement | Security Objective | ASVS Area (5.0.0) | Target Level | Planned Phase | Verification | Status |
|---|---|---|---|---|---|---|
| AUTH-001, AUTH-002 | Password storage resists offline cracking | V6 Authentication — Credential Storage (Argon2id) | L2 | 3 | Hash format + parameter review; unit test | REQUIREMENT_DEFINED |
| AUTH-003 | No reversible password storage | V6 Authentication — Credential Storage | L2 | 3 | Schema/code review | REQUIREMENT_DEFINED |
| AUTH-004, AUTH-005 | Session/token lifecycle control | V8 Authorization / V6 Session Management — Token revocation & expiry | L2 | 3 | Token replay-after-logout test | REQUIREMENT_DEFINED |
| AUTH-006, AUTH-007 | Brute-force / enumeration resistance | V6 Authentication — Anti-automation, Anti-enumeration | L2 | 3 | Abuse-simulation load test | REQUIREMENT_DEFINED |
| AUTH-008 | Tokens never in URLs | V6 Session Management — Token Transport | L2 | 3 | Code/traffic review | REQUIREMENT_DEFINED |
| AUTH-009 | Restrictive credential storage in browser | V6 Session Management — Token Storage | L2 (approaching L3) | 3, 9 | Storage-content inspection | REQUIREMENT_DEFINED |
| AUTH-010 | Recovery mechanism threat-reviewed before build | V6 Authentication — Account Recovery | L2 | TBD | Dedicated threat-model addendum | BLOCKED (design undecided) |
| AUTHZ-001, AUTHZ-002, AUTHZ-003 | Authorization bound to authenticated identity | V8 Authorization | L2 | 2, 3 | Adversarial payload-spoofing test | REQUIREMENT_DEFINED |
| IDENTITY-001 | Identity-change trust invalidation | V6 Authentication — Identity Proofing / Trust | L2 (approaching L3) | 4 | Adversarial key-rotation test | REQUIREMENT_DEFINED |
| IDENTITY-002 | Out-of-band identity verification | V6 Authentication — Identity Proofing | L2 (approaching L3) | 4 | UX + manual verification review | REQUIREMENT_DEFINED |
| IDENTITY-003 | Signed prekey verification | V11 Cryptography — Key Management | L2 (approaching L3) | 4, 5 | Signature-verification unit test | REQUIREMENT_DEFINED |
| IDENTITY-004 | Single vs multi-device model | V6 Authentication — Identity Model | L2 | 4 | Architecture decision record | BLOCKED (decision required) |
| CRYPTO-001 | No custom cryptography | V11 Cryptography — Algorithms | L2/L3 | 5, 6, 7 | Code/dependency review | REQUIREMENT_DEFINED |
| CRYPTO-002 | Private identity keys never sent to relay | V11 Cryptography — Key Management | L3 | 4, 5, 6 | Network capture + code review | REQUIREMENT_DEFINED |
| CRYPTO-003, CRYPTO-004 | KDF used for key derivation, not raw DH output | V11 Cryptography — Key Derivation | L2/L3 | 5, 6 | Code review + test vectors | REQUIREMENT_DEFINED |
| CRYPTO-005 | AEAD nonce uniqueness formally defined | V11 Cryptography — Encryption/AEAD | L3 | 6 | Property-based test | REQUIREMENT_DEFINED |
| CRYPTO-006, CRYPTO-007 | Fail-closed crypto, no plaintext fallback | V11 Cryptography — Error Handling | L2/L3 | 6 | Fault-injection test | REQUIREMENT_DEFINED |
| CRYPTO-008 | No secrets in logs | V16 Security Logging — Log Content | L2 | 6, 10 | Log-content audit/scan | REQUIREMENT_DEFINED |
| CRYPTO-009, CRYPTO-010 | Authenticated key agreement, bound context | V11 Cryptography — Key Agreement | L3 | 5 | Adversarial substitution test | REQUIREMENT_DEFINED |
| CRYPTO-011 | CSPRNG for all security-relevant randomness | V11 Cryptography — Random Values | L2 | 5, 6 | Code review (RNG source) | REQUIREMENT_DEFINED |
| STORAGE-001..004 | Key material encrypted at rest, bounded skipped-key cache | V11 Cryptography — Key Storage / V8 Data Protection | L2/L3 | 7, 9 | Storage-content test, load test | REQUIREMENT_DEFINED |
| E2EE-001..004 | End-to-end confidentiality architecture | V11 Cryptography / V13 API & Web Service (message handling) | L3 | 6 | E2E test + relay-side inspection | REQUIREMENT_DEFINED |
| WS-001, WS-002, WS-011 | Authenticated, Origin-validated WebSocket | V13 API & Web Service — WebSocket Security | L2 | 2 | Adversarial CSWSH test | REQUIREMENT_DEFINED |
| WS-003, WS-004, WS-009 | Strict schema, size limits, deterministic errors | V13 API & Web Service — Input Validation | L2 | 2 | Fuzz/negative test | REQUIREMENT_DEFINED |
| WS-005..008 | Connection limits, timeouts, backpressure, rate limits | V11 Business Logic (Availability) / V13 | L2 | 2 | Load test | REQUIREMENT_DEFINED |
| WS-010, WS-012 | Direct routing, ciphertext-only queue | V13 API & Web Service — Data Handling | L2/L3 | 2, 6 | Server-side inspection | REQUIREMENT_DEFINED |
| WS-013 | WSS mandatory in production | V9 Communications — TLS | L2 | 2, 10 | Deployment config review | REQUIREMENT_DEFINED |
| INTEGRITY-001..003 | Message integrity, replay/order handling | V11 Cryptography — Integrity / V13 | L2/L3 | 6, 7 | Adversarial tamper/replay test | REQUIREMENT_DEFINED |
| CLIENT-001, CLIENT-002 | No raw HTML render, strict CSP | V5 Validation, Sanitization & Encoding / V14 Configuration | L2 | 8 | Automated XSS test, CSP header review | REQUIREMENT_DEFINED |
| CLIENT-003 | Identity-change UX warning | V6 Authentication — Identity Proofing (client) | L2 | 8 | Manual/automated UX test | REQUIREMENT_DEFINED |
| CLIENT-004, CLIENT-005 | Encrypted local history, restrictive key storage | V8 Data Protection / V11 Key Storage | L2/L3 | 9 | Storage-content inspection | REQUIREMENT_DEFINED |
| CLIENT-006 | No secrets in frontend build | V14 Configuration — Build | L2 | 8, 11 | Build-artifact scan | REQUIREMENT_DEFINED |
| CLIENT-007..009 | Fail-safe crypto UX, client-only enc/dec | V11 Cryptography (client) | L2/L3 | 6, 8 | Fault-injection + E2E test | REQUIREMENT_DEFINED |
| STORAGE-005..007 | Encrypted-at-rest local data, secure-delete best effort | V8 Data Protection | L2 | 9 | Storage-content inspection | REQUIREMENT_DEFINED |
| SERVER-001..003 | Relay/DB/log plaintext exclusion | V8 Data Protection / V16 Logging | L2/L3 | 6, 9, 10 | Schema + log review | REQUIREMENT_DEFINED |
| SERVER-004, SERVER-005 | TLS/WSS, Origin validation | V9 Communications | L2 | 10 | Deployment config review | REQUIREMENT_DEFINED |
| SERVER-006 | Least-privilege server/DB credentials | V14 Configuration — Least Privilege | L2 | 10 | IAM/role review | REQUIREMENT_DEFINED |
| SERVER-007 | Abuse/resource controls | V11 Business Logic (Availability) | L2 | 2, 10 | Load test | REQUIREMENT_DEFINED |
| SERVER-008 | Health endpoints leak no sensitive data | V14 Configuration — Information Leakage | L2 | 10 | Endpoint response review | REQUIREMENT_DEFINED |
| LOG-001..003 | Sanitized structured logging | V16 Security Logging and Error Handling | L2 | 10 | Log-content audit/scan | REQUIREMENT_DEFINED |
| AVAIL-001..004 | Bounded resource consumption | V11 Business Logic (Availability) | L2 | 2 | Load test | REQUIREMENT_DEFINED |
| PRIVACY-001..003 | Metadata minimization & honest disclosure | V8 Data Protection / V14 Configuration | L2 | 10, 13 | Documentation + data-retention review | REQUIREMENT_DEFINED |
| DEPLOY-001..004 | Hardened deployment/secret handling | V14 Configuration | L2 | 10 | Deployment config review | REQUIREMENT_DEFINED |
| SUPPLY-001..010 | Dependency/secret/container scanning, SBOM, signed releases | V14 Configuration — Supply Chain (ASVS 5.0 expanded coverage) | L2 | 11 | CI pipeline evidence | REQUIREMENT_DEFINED |
| TEST-001..005 | Verification discipline, adversarial testing | V1 Architecture, Design and Threat Modeling / process requirement | L2 | All, 12 | Phase evidence logs | REQUIREMENT_DEFINED |
| Forward secrecy (ratchet, no dedicated ASVS ID) | Confidentiality over time | V11 Cryptography — Key Management (forward secrecy is a design property layered on ASVS key-management controls) | L3 | 7 | Adversarial compromise-then-verify test | PLANNED |

**Explicit non-goals / not applicable:**

| Area | Status | Rationale |
|---|---|---|
| Full network anonymity (Tor-equivalent) | OUT_OF_SCOPE | Declared out of scope in `THREAT_MODEL.md §15` |
| Protection of plaintext after endpoint compromise | OUT_OF_SCOPE | No ASVS control can satisfy this; declared limitation |
| Multi-tenant / RBAC-heavy authorization model | NOT_APPLICABLE | v1 is a simple two-party direct-messaging model |

**Unresolved mapping issues:**

1. Forward secrecy and ratchet-specific guarantees do not map cleanly to a
   single ASVS 5.0.0 control ID; they are treated as a design property
   satisfied *through* V11 key-management controls rather than a discrete
   checklist item. This should be revisited once ASVS 5.0.0's final published
   section numbering is confirmed against the specific edition used for Phase
   12 verification.
2. Account-recovery mapping (`AUTH-010`) is `BLOCKED` pending the open decision
   in [SECURITY_ASSUMPTIONS.md](SECURITY_ASSUMPTIONS.md).
3. Single-vs-multi-device identity mapping (`IDENTITY-004`) is `BLOCKED` for
   the same reason.

---

## Phase 2 implementation status (WebSocket transport)

Added at the end of Phase 2. The Phase 0 table above records the *requirement*
baseline and is unchanged; this section records what has since been built and
verified. Statuses are evidence-based — see
[PHASE_2_EVIDENCE.md](PHASE_2_EVIDENCE.md) and the `server/tests/test_websocket_*`
suites.

| Requirement | Status | Evidence |
|---|---|---|
| WS-002 (Origin allowlist) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_origin.py` (14 tests), incl. a real-handshake HTTP 403 |
| WS-003 (strict schema validation) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_schema.py` (44 tests) |
| WS-004 (max message size) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_limits.py`, incl. an exact-boundary test |
| WS-005 (connection limits) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_connection.py`, `test_websocket_limits.py` |
| WS-006 (idle timeout, heartbeat) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_lifecycle.py` |
| WS-007 (backpressure) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Bounded outbound queue + writer task; `test_websocket_limits.py` |
| WS-008 (message rate limit) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Fixed-window limiter; `test_websocket_limits.py` |
| WS-009 (deterministic errors) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | 15 stable codes; leak-check test in `test_websocket_schema.py` |
| WS-010 (direct routing, no broadcast) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_routing.py`, plus a real-socket no-broadcast test |
| WS-011 (sender bound to connection) | `PARTIALLY_IMPLEMENTED` | Bound to the **transport** identity and tested (`test_websocket_spoofing.py`). Binding to an *authenticated* identity is `PLANNED_PHASE_3` |
| WS-001 (authenticated WebSocket) | `PLANNED_PHASE_3` | Not implemented. `ConnectionContext.authenticated` is a placeholder fixed at `False` |
| WS-012 (ciphertext-only queue) | `PLANNED_PHASE_6` | Queue abstraction exists and never inspects `payload`, so Phase 6 can substitute ciphertext without restructuring |
| WS-013 (WSS mandatory in production) | `PLANNED_PHASE_10` | Development uses `ws://`; deployment hardening is Phase 10 |
| AUTHZ-002 (sender not from payload) | `PARTIALLY_IMPLEMENTED` | Enforced at transport level; authenticated identity `PLANNED_PHASE_3` |
| AUTHZ-003 (no private-message broadcast) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Assertion A tested in-process and over real sockets |
| AVAIL-001 (bounded connection cost) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Global and per-identity connection caps |
| AVAIL-002 (bounded message cost) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Per-connection rate limiter |
| AVAIL-003 (bounded work for low-trust actors) | `PARTIALLY_IMPLEMENTED` | Size and rate checks run before parsing; no expensive crypto exists yet to bound |
| AVAIL-004 (bounded storage growth) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Offline queue bounded per recipient and in recipient count |
| LOG-001 (no plaintext in logs) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | `test_websocket_logging.py` scans captured records for a payload marker |
| LOG-003 (structured logs) | `IMPLEMENTED_PHASE_2` / `TESTED_PHASE_2` | Structured `transport` extra; field set asserted |
| SERVER-002 (no plaintext in database) | `IMPLEMENTED_PHASE_2` (vacuously) | No database exists. Guard tests assert the transport imports no persistence library and writes no files |
| INTEGRITY-002 (replay resistance) | `PLANNED_PHASE_7` | **Not implemented.** `message_id` exists so replay/deduplication can be built on it; no replay resistance exists today |
| CRYPTO-*, E2EE-*, IDENTITY-*, AUTH-* | `REQUIREMENT_DEFINED` (unchanged) | Phase 2 implements no cryptography, identity, or authentication |
