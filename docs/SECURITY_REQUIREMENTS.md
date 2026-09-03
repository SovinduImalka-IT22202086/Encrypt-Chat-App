# Security Requirements

**Project:** Encrypted Chat Application
**Phase:** 0 — Security Requirements & Threat Model
**Status:** REQUIREMENT_DEFINED (no implementation exists yet)

Requirements use SHALL / SHALL NOT language where the intent is a binding
constraint on later phases, and SHOULD where the intent is a strong default that
may be reviewed. Every requirement has a stable ID so it can be traced from
[THREAT_MODEL.md](THREAT_MODEL.md) and mapped in [ASVS_MAPPING.md](ASVS_MAPPING.md).
**No requirement in this document is implemented. All are planned.**

---

## 1. Purpose

Define the complete set of security requirements the Encrypted Chat Application
must satisfy across its implementation phases (1–13), so that every later design
and code decision can be checked against a fixed, traceable contract established
before implementation began.

---

## 2. Security Principles

- **P1 — Security-first:** security-relevant tests and controls are implemented in
  the same phase as the feature they protect, not deferred.
- **P2 — No custom cryptography:** only standard, reviewed primitives and
  constructions are used (see §7).
- **P3 — Least privilege:** every component (client, server, database role, CI
  credential) holds the minimum privilege needed for its function.
- **P4 — Fail closed:** any security-relevant failure (crypto, auth, validation)
  must block the operation, never silently degrade to a less-secure path.
- **P5 — Assume compromise is possible:** the relay and the database are treated
  as potentially compromised; the architecture must limit what such compromise
  exposes.
- **P6 — Honesty over completeness theater:** a requirement's status reflects
  reality (`PLANNED`, not `IMPLEMENTED`, until evidence exists).

---

## 3. Architecture Requirements

- **ARCH-001:** The system SHALL be composed of an untrusted-for-plaintext relay/
  application server, a client that performs all plaintext message
  encryption/decryption, and a database that SHALL NOT store private-message
  plaintext.
- **ARCH-002:** The relay SHALL mediate authentication, routing, public
  identity/prekey distribution, and offline ciphertext queuing, and SHALL NOT
  require plaintext access to perform any of these functions.
- **ARCH-003:** Trust boundaries defined in `THREAT_MODEL.md §5` SHALL be
  preserved by every subsequent architectural change; a change that crosses a
  boundary differently SHALL trigger a threat-model review before merge.
- **ARCH-004:** v1 architecture SHALL support direct (1:1) messaging only, on a
  single device per identity, unless a documented decision (§22 "Known
  Limitations" / decision log) changes this scope before the affected phase.

---

## 4. Authentication Requirements

- **AUTH-001:** Passwords SHALL be hashed using Argon2id with a unique,
  cryptographically random salt per credential.
- **AUTH-002:** Argon2id work parameters SHALL be selected and documented based
  on target hardware, and SHALL be revisited if hardware assumptions change.
- **AUTH-003:** The server SHALL NOT store passwords in plaintext or in any
  reversible form.
- **AUTH-004:** Access/session tokens SHALL be short-lived and SHALL be
  revocable server-side before natural expiry.
- **AUTH-005:** Logout SHALL invalidate the associated session/token
  server-side, not merely discard it client-side.
- **AUTH-006:** Authentication endpoints SHALL implement brute-force controls
  (rate limiting and/or lockout/backoff) bounding the cost of credential-guessing
  attacks.
- **AUTH-007:** Authentication error responses and timing SHALL NOT allow
  practical enumeration of valid usernames/accounts.
- **AUTH-008:** Tokens SHALL NOT be transmitted or logged as part of a URL
  (query string).
- **AUTH-009:** Sensitive, long-lived credential material SHALL NOT depend on
  browser `localStorage` as its primary protection mechanism; a more restrictive
  storage/handling approach SHALL be used (finalized in Phase 3/9 design).
- **AUTH-010:** Any future account-recovery mechanism SHALL undergo its own
  threat-model review before implementation, given its inherent tension with
  AUTH-level security guarantees (see open decision in
  [SECURITY_ASSUMPTIONS.md](SECURITY_ASSUMPTIONS.md)).

---

## 5. Authorization Requirements

- **AUTHZ-001:** A WebSocket connection SHALL be authorized only after
  successful authentication; unauthenticated connections SHALL NOT be able to
  send or receive user messages.
- **AUTHZ-002:** A user SHALL only be authorized to send messages as their own
  authenticated identity; the server SHALL derive the sender identity from the
  authenticated connection context, never from client-supplied payload fields
  (mitigates TM-005).
- **AUTHZ-003:** A user SHALL only be authorized to receive messages addressed
  to their own authenticated identity; the server SHALL NOT broadcast
  private-message content to unintended recipients.

---

## 6. Identity & Trust Requirements

- **IDENTITY-001:** A changed long-term identity key SHALL invalidate the
  previous verified trust state for that contact; the affected user(s) SHALL be
  warned before continuing to communicate under the new key (mitigates TM-014).
- **IDENTITY-002:** The client SHALL provide a mechanism for users to verify a
  contact's identity out-of-band (e.g., a displayed fingerprint/safety number),
  to reduce trust-on-first-use (TOFU) risk.
- **IDENTITY-003:** Published prekeys SHALL be signed by the owning identity's
  long-term key, and the signature SHALL be verified by the receiving client
  before use (mitigates TM-003).
- **IDENTITY-004:** The single-device-vs-multi-device identity model SHALL be
  formally decided before Phase 4 begins (see open decision log).

---

## 7. Cryptographic Requirements

- **CRYPTO-001:** No custom cryptographic primitive may be invented; only
  standard, reviewed primitives and constructions are permitted (Ed25519,
  X25519, HKDF-SHA-256, AES-256-GCM or XChaCha20-Poly1305, a reviewed ratchet
  construction such as the Double Ratchet).
- **CRYPTO-002:** Private identity keys SHALL NOT be transmitted to the relay
  under any circumstance.
- **CRYPTO-003:** Raw Diffie-Hellman shared secrets SHALL NOT be used directly
  as message encryption keys; they SHALL be passed through a KDF first.
- **CRYPTO-004:** Key derivation SHALL use a standard KDF (HKDF-SHA-256 or
  equivalent reviewed construction).
- **CRYPTO-005:** AEAD nonce-uniqueness requirements SHALL be formally defined
  (construction, counter/derivation scheme, and the conditions under which
  uniqueness is guaranteed) before any AEAD implementation is written.
- **CRYPTO-006:** Authentication-tag verification failures SHALL fail closed:
  the message SHALL be rejected, and SHALL NOT be partially processed or
  displayed.
- **CRYPTO-007:** Cryptographic errors SHALL NEVER trigger a plaintext fallback
  path (mitigates TM-015).
- **CRYPTO-008:** Cryptographic secrets (private keys, session keys, chain/root
  keys, message keys) SHALL NOT appear in logs at any log level.
- **CRYPTO-009:** Key-agreement material SHALL be authenticated (bound to a
  verified long-term identity), not accepted as bare unauthenticated
  Diffie-Hellman input.
- **CRYPTO-010:** Protocol context (e.g., protocol version, participant
  identities) SHALL be bound into key derivation and/or handshake transcripts to
  prevent cross-protocol and identity-confusion attacks.
- **CRYPTO-011:** All randomness used for key material, nonces, or salts SHALL
  come from a cryptographically secure random number generator (CSPRNG); no
  non-cryptographic RNG (e.g., `Math.random`) may be used for security-relevant
  values.

---

## 8. Key Management Requirements

- **STORAGE-001 (keys):** Long-term identity private keys SHALL be encrypted at
  rest on the client using a key derived from user-controlled secret material or
  an OS-provided secure keystore, never stored in plaintext (mitigates TM-009).
- **STORAGE-002 (keys):** Session/ratchet state SHALL be stored encrypted at
  rest when persisted locally.
- **STORAGE-003 (keys):** Used message keys SHALL be deleted immediately after
  use, consistent with the forward-secrecy objective.
- **STORAGE-004 (keys):** Skipped-message-key retention SHALL be bounded (count
  and/or time) to prevent unbounded resource growth (mitigates TM-018).

---

## 9. E2EE Requirements

- **E2EE-001:** Private-message plaintext SHALL be encrypted at the sender
  endpoint before transmission to the relay.
- **E2EE-002:** The relay SHALL NOT possess the cryptographic keys required to
  decrypt private-message content.
- **E2EE-003:** Decryption of private-message content SHALL occur only at the
  intended recipient endpoint(s).
- **E2EE-004:** The message envelope format SHALL distinguish ciphertext payload
  from any necessarily-plaintext routing metadata, and SHALL NOT include message
  plaintext in any field the relay processes.

---

## 10. WebSocket / Transport Requirements

- **WS-001:** WebSocket connections SHALL require authentication before any
  user-message traffic is accepted.
- **WS-002:** The server SHALL enforce an explicit Origin allowlist for
  WebSocket upgrade requests (mitigates TM-011 / CSWSH).
- **WS-003:** Incoming messages SHALL be validated against a strict schema;
  malformed messages SHALL be rejected with a deterministic protocol error.
- **WS-004:** The server SHALL enforce a maximum message size.
- **WS-005:** The server SHALL enforce per-connection and/or per-account
  connection limits.
- **WS-006:** The server SHALL enforce idle timeouts and a heartbeat/keepalive
  mechanism.
- **WS-007:** The server SHALL implement backpressure handling so a slow or
  malicious peer cannot exhaust server buffers.
- **WS-008:** The server SHALL enforce rate limits on message send frequency
  per connection/account.
- **WS-009:** Protocol errors SHALL be deterministic and SHALL NOT leak
  internal implementation details.
- **WS-010:** Messages SHALL be routed directly to the intended recipient(s)
  only; the server SHALL NOT broadcast private-message content.
- **WS-011:** Sender identity SHALL be bound to the authenticated connection,
  never trusted from message payload fields (restates AUTHZ-002 at the
  transport layer).
- **WS-012:** The offline-message queue SHALL contain ciphertext only, once
  E2EE is implemented (Phase 6+).
- **WS-013:** WSS (WebSocket Secure / TLS) SHALL be mandatory in production
  deployments; unencrypted WS SHALL NOT be used outside local development.

---

## 11. Message Integrity / Replay Requirements

- **INTEGRITY-001:** Message integrity SHALL be cryptographically verifiable by
  the recipient (AEAD authentication tag or equivalent).
- **INTEGRITY-002:** A previously delivered, valid message or handshake message
  SHALL NOT be independently replayable as a new valid protocol event
  (mitigates TM-004).
- **INTEGRITY-003:** Out-of-order message delivery SHALL be handled by a
  defined ordering/gap-handling mechanism rather than silently accepted or
  silently dropped.

---

## 12. Client Security Requirements

- **CLIENT-001:** The client SHALL NOT render untrusted message content as raw
  HTML.
- **CLIENT-002:** The client SHALL enforce a strict Content-Security-Policy
  (CSP).
- **CLIENT-003:** The client SHALL warn the user when a contact's identity key
  changes, rather than silently accepting it (restates IDENTITY-001 at the
  client layer).
- **CLIENT-004:** Local conversation history, when persisted, SHALL be encrypted
  at rest; it SHALL NOT be stored in plaintext as an implementation shortcut.
- **CLIENT-005:** Identity/private key material SHALL be handled using the
  most restrictive storage mechanism practical in the browser/runtime
  environment, avoiding unnecessary exposure to script-accessible storage.
- **CLIENT-006:** No secrets (API keys, server credentials) SHALL be embedded
  in frontend build artifacts.
- **CLIENT-007:** Cryptographic failure in the client SHALL produce a clear,
  safe user-facing error state; it SHALL NOT silently proceed or fall back to
  an insecure path (restates CRYPTO-007 at the client layer).
- **CLIENT-008:** Outgoing messages SHALL be encrypted client-side before any
  server-facing send operation is invoked.
- **CLIENT-009:** Incoming messages SHALL be decrypted only on the recipient's
  own endpoint; the client SHALL NOT request or accept server-side decryption.

---

## 13. Local Storage Requirements

- **STORAGE-005:** All security-sensitive local data (keys, ratchet state,
  cached plaintext history) SHALL be encrypted at rest.
- **STORAGE-006:** The key used to encrypt local storage SHALL NOT itself be
  stored in a reversible, unprotected form alongside the data it protects.
- **STORAGE-007:** Deletion of local data (e.g., "clear history") SHOULD make a
  best effort at secure removal, while acknowledging the out-of-scope limitation
  on guaranteed secure deletion from underlying storage media (see
  `THREAT_MODEL.md §15`).

---

## 14. Server Requirements

- **SERVER-001:** The relay SHALL NOT be capable of decrypting private-message
  content (restates E2EE-002 at the server layer).
- **SERVER-002:** The database SHALL NOT contain private-message plaintext.
- **SERVER-003:** Application and security logs SHALL NOT contain
  private-message plaintext (restates LOG-001 below).
- **SERVER-004:** All production server endpoints SHALL be served over
  TLS/WSS.
- **SERVER-005:** The server SHALL validate the Origin header on WebSocket
  upgrade requests against an explicit allowlist (restates WS-002).
- **SERVER-006:** Server processes and database roles SHALL operate under
  least-privilege credentials scoped to their function.
- **SERVER-007:** The server SHALL implement abuse controls (rate limiting,
  size limits, connection limits) sufficient to bound resource consumption per
  actor.
- **SERVER-008:** Health-check/status endpoints SHALL NOT expose sensitive
  configuration, secrets, or internal diagnostic detail.

---

## 15. Logging Requirements

- **LOG-001:** Server logs SHALL NOT contain plaintext private-message content.
- **LOG-002:** Logs SHALL NOT contain passwords, private keys, session/access
  tokens, or other credential/secret material in plaintext (restates
  CRYPTO-008 at the operational layer).
- **LOG-003:** Logs SHALL be structured and SHALL support automated review for
  accidental sensitive-data inclusion (supports LOG-001/LOG-002 verification).

---

## 16. Availability / Abuse Protection

- **AVAIL-001:** The server SHALL bound the resource cost of connection
  establishment (mitigates connection-flooding DoS).
- **AVAIL-002:** The server SHALL bound the resource cost of message
  processing per unit time per actor (mitigates message-flooding DoS).
- **AVAIL-003:** The server SHALL bound expensive cryptographic/verification
  operations that an unauthenticated or low-trust actor can trigger.
- **AVAIL-004:** The server SHALL bound storage growth attributable to a single
  actor (message queue depth, skipped-key cache, etc.).

---

## 17. Privacy / Metadata Requirements

- **PRIVACY-001:** The system SHALL minimize collection and retention of
  metadata not required for core functionality (e.g., avoid retaining IP
  history longer than operationally necessary).
- **PRIVACY-002:** The system's documentation and user-facing communication
  SHALL accurately state which metadata the relay observes (per
  `THREAT_MODEL.md §13`) and SHALL NOT imply metadata-level anonymity that is
  not actually provided.
- **PRIVACY-003:** Presence/online-status information SHALL be exposed only to
  the extent required for product functionality, not broadcast broadly by
  default.

---

## 18. Deployment Requirements

- **DEPLOY-001:** Production deployment configuration SHALL enforce TLS/WSS
  (restates SERVER-004).
- **DEPLOY-002:** Secrets SHALL be injected via a secure mechanism (secret
  manager / environment injection at deploy time), never committed to source
  control.
- **DEPLOY-003:** Container/deployment images SHALL be scanned for known
  vulnerabilities before release (Phase 10/11).
- **DEPLOY-004:** Deployment/container configuration SHALL follow least
  privilege (no unnecessary capabilities, minimal base image, non-root process
  where practical).

---

## 19. Supply Chain Requirements

- **SUPPLY-001:** Dependencies SHALL be pinned to specific versions.
- **SUPPLY-002:** Python dependencies SHALL be scanned for known
  vulnerabilities in CI.
- **SUPPLY-003:** Node dependencies SHALL be scanned for known vulnerabilities
  in CI.
- **SUPPLY-004:** Source control and CI SHALL be scanned for accidentally
  committed secrets (e.g., Gitleaks or equivalent) (mitigates TM-019).
- **SUPPLY-005:** Static Application Security Testing (SAST) SHALL run in CI.
- **SUPPLY-006:** Container images SHALL be scanned for known vulnerabilities
  in CI (restates DEPLOY-003).
- **SUPPLY-007:** A Software Bill of Materials (SBOM) SHALL be generated for
  release artifacts.
- **SUPPLY-008:** The release process SHALL be protected (restricted
  publishing rights, required review/approval).
- **SUPPLY-009:** Release artifacts SHALL be checksummed and/or signed.
- **SUPPLY-010:** CI/CD credentials SHALL be scoped to the minimum required
  permission and SHALL NOT be exposed in build logs.

---

## 20. Verification Requirements

- **TEST-001:** Every mandatory security control SHALL have an associated
  automated test or documented manual verification procedure before the owning
  phase is marked COMPLETE.
- **TEST-002:** Security-relevant tests SHALL be added in the same phase as the
  feature they verify, not deferred to Phase 12.
- **TEST-003:** Phase 12 (Adversarial Security Verification) SHALL exercise the
  threat scenarios in `THREAT_MODEL.md §11` against the actual implementation.
- **TEST-004:** Phase 12's adversarial verification SHALL be repeated against
  the final v1.0 release candidate, not only against development builds.
- **TEST-005:** No security property SHALL be reported as verified without
  corresponding test evidence recorded in the applicable phase's evidence log.

---

## 21. ASVS Mapping Reference

See [ASVS_MAPPING.md](ASVS_MAPPING.md) for the mapping of these requirements to
OWASP ASVS 5.0.0 (target: Level 2 baseline, with elevated consideration for
cryptography, authentication, session management, key management, secure
communication, and stored cryptographic material).

---

## 22. Known Limitations

- No implementation exists yet; every requirement above is `PLANNED`.
- The single-device-vs-multi-device identity model is unresolved
  (`IDENTITY-004`; see [SECURITY_ASSUMPTIONS.md](SECURITY_ASSUMPTIONS.md) for the
  full decision record).
- Account-recovery design is unresolved (`AUTH-010`).
- Metadata privacy is explicitly and permanently limited by the client-relay
  architecture (see `THREAT_MODEL.md §13`); no requirement in this document
  claims to eliminate that limitation.
- Attachment support is not committed for v1 and has no requirements defined
  yet; if approved, it SHALL inherit `E2EE-001` through `E2EE-004` before
  implementation.
