# Threat Model

**Project:** Encrypted Chat Application
**Phase:** 0 — Security Requirements & Threat Model
**Status:** DRAFT — REQUIREMENT_DEFINED (no implementation exists yet)
**Applies to:** v1 architecture (single-device, direct 1:1 messaging)

---

## 1. Purpose

This document defines the threat model for the Encrypted Chat Application before any
application code is written. It identifies what the system protects, who it protects
against, what it does not protect against, and the trust boundaries that later
implementation phases (Phase 1–13) must respect. Every architectural or
implementation decision made in later phases must be reviewable against this
document. This is a living document — the "Review / Change History" section (§19)
must be updated whenever the model changes materially.

This document does not describe an implemented system. No cryptography,
authentication, transport, or storage code exists at the time of writing. All
controls described here are **planned**, not **verified**, unless explicitly marked
otherwise.

---

## 2. System Overview

The Encrypted Chat Application is an end-to-end encrypted (E2EE) direct-messaging
system. Two authenticated users exchange messages whose plaintext content is
readable only at the sending and receiving endpoints. A relay/application server
mediates connection, authentication, routing, and offline delivery, but is
architecturally intended to never possess the keys required to read private-message
plaintext.

v1 scope (subject to confirmation before Phase 4, see §15 "Decisions Required"):

- Direct (1:1) messaging only — no group messaging.
- Single device per identity — no multi-device key synchronization.
- Text messages — attachments are not committed to v1 unless separately approved.
- Web-based React client, FastAPI-based backend (per the execution guide), WebSocket
  transport for real-time delivery.

---

## 3. Security Objectives

See [SECURITY_REQUIREMENTS.md §2](SECURITY_REQUIREMENTS.md) for the normative
statement of each objective. Summary:

1. **Confidentiality** — relay and unauthorized parties must not obtain
   private-message plaintext.
2. **Integrity** — unauthorized modification of a message must be detectable by the
   recipient.
3. **Authenticity** — a user must be able to cryptographically verify which
   long-term identity they are communicating with.
4. **Forward Secrecy** — compromise of current key material should not
   retroactively expose historical plaintext, within the guarantees of the
   ratchet construction actually implemented in Phase 7.
5. **Replay Resistance** — a captured protocol message or handshake must not be
   independently replayable as a new valid event.
6. **Account Security** — authentication must resist credential stuffing,
   brute force, enumeration, and token theft/replay.
7. **Availability** — the system must bound the cost of abusive or malformed
   input so that a single actor cannot trivially deny service to others.
8. **Metadata Limitation** — the document explicitly enumerates what metadata the
   relay unavoidably observes (§13) rather than implying full metadata privacy.

---

## 4. Architecture (Conceptual — Not Yet Implemented)

```text
User A Client
     |
     | Authentication / WSS
     v
Relay / Application Server
     |
     +---- Authentication / account services
     |
     +---- Ciphertext message routing
     |
     +---- Public identity/prekey distribution
     |
     +---- Offline ciphertext queue
     |
     +---- Database / supporting infrastructure
     |
     v
User B Client
```

The server performs: authentication, connection routing, distribution of public
identity/prekey material, queuing of ciphertext for offline recipients, and abuse
prevention. The server is explicitly **not trusted with plaintext message
confidentiality** — this is a design invariant, not a claim about a currently
existing implementation. See [DATA_FLOW_DIAGRAM.md](DATA_FLOW_DIAGRAM.md) for the
full data-flow/trust-boundary diagram.

---

## 5. Trust Boundaries

| # | Boundary | Description |
|---|---|---|
| 1 | User/browser/client boundary | Between the human user and the client application running in their browser/device. |
| 2 | Client ↔ network boundary | Between the client process and the untrusted network (WSS/HTTPS transport). |
| 3 | Network ↔ relay/backend boundary | Between the network and the application server process. |
| 4 | Backend ↔ database boundary | Between the application server and its persistent storage. |
| 5 | Client ↔ local-storage boundary | Between the in-memory client state and on-disk/browser-storage persistence. |
| 6 | Authentication/session boundary | Between an anonymous connection and an authenticated, authorized session. |
| 7 | Cryptographic identity/key boundary | Between key material that may leave the endpoint (public keys) and key material that must never leave the endpoint (private keys). |
| 8 | Third-party dependency boundary | Between first-party code and third-party libraries/packages pulled into the build. |
| 9 | Deployment/container boundary | Between the running application and the host/container/orchestration layer. |
| 10 | CI/CD/software-supply-chain boundary | Between source control / CI pipeline and the released, deployed artifact. |

**Plaintext placement invariant:**

```text
Plaintext message:
  allowed only at authorized endpoints while required for user interaction.
Relay:
  ciphertext only.
Server database:
  ciphertext only for private message content.
Server logs:
  no plaintext private messages.
Network:
  encrypted transport + E2EE ciphertext.
Cryptographic private keys:
  must not be disclosed to relay/server.
```

This invariant is restated formally in §28 of the master plan and in
[SECURITY_REQUIREMENTS.md](SECURITY_REQUIREMENTS.md) as `E2EE-001`/`E2EE-002`.

---

## 6. Assets

For each asset: Owner, Location, Confidentiality (C) / Integrity (I) / Availability
(A) requirement (H = High, M = Medium, L = Low), primary attackers, impact if
compromised, expected protection.

### 6.1 Message assets

| Asset | Owner | Location | C | I | A | Primary Attackers | Impact if Compromised | Expected Protection |
|---|---|---|---|---|---|---|---|---|
| Plaintext messages | User | Endpoint memory/UI only | H | H | M | Local-device attacker, malicious recipient | Full disclosure of conversation content | Never persisted or transmitted in plaintext; endpoint-only |
| Stored ciphertext (in transit / queued) | User (content), Server (custody) | Server DB, offline queue | H | H | M | Compromised relay/DB, network attacker | Without keys: none directly; enables traffic/metadata analysis and future cryptanalysis | AEAD encryption, unique nonces, no plaintext ever stored |
| Message attachments (future) | User | Endpoint / server blob storage | H | H | M | Same as messages | Same as messages | Same E2EE guarantees as text, out of v1 unless approved |
| Authenticated message metadata (sender, timestamp, sequence) | User/Server | Message envelope | M | H | M | MITM, malicious client | Spoofed sender, reordered/dropped messages undetected | Cryptographic binding/authentication of envelope fields |

### 6.2 Cryptographic assets

| Asset | Owner | Location | C | I | A | Primary Attackers | Impact if Compromised | Expected Protection |
|---|---|---|---|---|---|---|---|---|
| Long-term identity private keys | User | Endpoint only | H | H | H | Local-device attacker, endpoint malware | Impersonation of user identity indefinitely | Never leaves endpoint; encrypted at rest (Phase 9) |
| Identity public keys | User (published) | Server directory, endpoints | L | H | M | MITM, malicious relay | Impersonation via key substitution if integrity fails | Integrity protection, user-verifiable fingerprints |
| Ephemeral / prekeys | User | Server (public), endpoint (private) | H (private) / L (public) | H | M | Compromised relay, MITM | Session compromise if private ephemeral leaked; substitution if public integrity fails | Standard X3DH/X25519-style handling, signed prekeys |
| X25519 key-agreement material | User | Endpoint (private), wire (public) | H | H | M | MITM, compromised relay | Session key compromise, impersonation | Authenticated key agreement (signed by identity key) |
| Session keys | User | Endpoint memory | H | H | M | Endpoint compromise | Decryption of current session traffic | Derived via KDF, never transmitted |
| Root keys / chain keys | User | Endpoint memory | H | H | M | Endpoint compromise | Enables derivation of future/adjacent message keys | Ratchet construction, memory-only |
| Message keys | User | Endpoint memory, ephemeral | H | H | M | Endpoint compromise (narrow window) | Decryption of single message | Deleted immediately after use |
| Ratchet state | User | Endpoint (encrypted local storage) | H | H | H | Local-device attacker, storage compromise | Forward-secrecy/replay guarantees undermined | Encrypted local storage, integrity checks |
| Local-storage encryption keys | User | Endpoint (derived from user secret / OS keystore) | H | H | H | Local-device attacker | Full compromise of local encrypted history | Not stored in reversible plaintext form |
| Nonces | Protocol | Message envelope | L | H | M | N/A (must be unique, not secret) | Nonce reuse can catastrophically break AEAD confidentiality | Deterministic/unique construction, enforced uniqueness |
| Cryptographic fingerprints / safety numbers | User | Displayed to user | L | H | L | MITM | Undetected identity substitution | User-facing out-of-band verification support |

### 6.3 Authentication assets

| Asset | Owner | Location | C | I | A | Primary Attackers | Impact if Compromised | Expected Protection |
|---|---|---|---|---|---|---|---|---|
| Passwords | User | Client memory (transiently), never stored server-side | H | M | L | Credential attacker | Account takeover | Never stored; only derived hash reaches server |
| Password hashes | Server | Database | H | H | L | Compromised DB | Offline cracking attempts | Argon2id, unique salts, tuned parameters |
| Authentication tokens (session/access) | User + Server | Client memory/secure storage, server session store | H | H | M | Credential attacker, XSS, endpoint compromise | Session hijack / impersonation | Short-lived, revocable, not in URLs |
| Refresh / session state | Server | Server-side store | H | H | M | Compromised DB/session store | Extended unauthorized access | Rotation, revocation, bounded lifetime |
| Account recovery material (if any) | User | TBD | H | H | M | Credential attacker | Account takeover via recovery path | Deferred design decision — see §15 open decisions |

### 6.4 Privacy assets

| Asset | Owner | Location | C | I | A | Primary Attackers | Impact if Compromised | Expected Protection |
|---|---|---|---|---|---|---|---|---|
| User identities (accounts) | User | Server DB | M | H | M | Compromised DB, passive observer | Real-world identity correlation | Least-privilege access, minimal collection |
| Contact relationships | User | Server DB (implied by messaging pairs) | M | H | L | Compromised DB/relay | Social-graph exposure | Not explicitly hideable from relay in v1 — documented in §13 |
| Conversation relationships | User | Server DB / routing metadata | M | H | L | Compromised relay | Who-talks-to-whom exposure | Same as above — documented limitation |
| Timestamps | User | Message envelope, logs | L | M | L | Compromised relay, passive observer | Traffic-pattern/timing analysis | Minimization where feasible; not eliminable in v1 |
| IP / network information | User | Server connection logs | M | M | L | Compromised relay, legal compulsion | Network-location correlation | Minimal retention, documented limitation |
| Presence information (online/offline) | User | Server runtime state | L | M | L | Compromised relay, malicious client | Availability/behavior pattern inference | Minimize exposure to non-contacts |
| Message routing metadata (who/when/how much) | Server | Server runtime + logs | M | H | L | Compromised relay | Traffic analysis | Documented as inherent v1 limitation (§13) |

### 6.5 Infrastructure assets

| Asset | Owner | Location | C | I | A | Primary Attackers | Impact if Compromised | Expected Protection |
|---|---|---|---|---|---|---|---|---|
| Server credentials | Operator | Secret store / environment | H | H | H | Supply-chain/insider attacker | Full server compromise | Secret injection, least privilege, rotation |
| Database credentials | Operator | Secret store / environment | H | H | H | Same as above | Full DB compromise | Same as above |
| TLS private keys | Operator | Server / cert store | H | H | H | Server compromise | MITM against all users until rotated/revoked | Restricted access, rotation, monitored issuance |
| Configuration secrets | Operator | Secret store | H | H | M | Supply-chain/insider attacker | Infrastructure compromise | Not committed to source control |
| CI/CD credentials | Operator | CI secret store | H | H | H | Supply-chain attacker | Malicious build/release | Scoped, short-lived, audited |
| Deployment secrets | Operator | Deployment pipeline | H | H | H | Supply-chain attacker | Unauthorized deployment | Protected release process (Phase 11) |
| Security logs | Operator | Log storage | M | H | M | Compromised relay/log store | Loss of forensic capability, or leakage if logs contain sensitive data | Sanitized structured logging, access control |

---

## 7. Threat Actors

### A. Passive Network Observer
**Capabilities:** observe network traffic, collect packets, inspect timing and size, perform later offline analysis.
**Concerns:** plaintext exposure if transport/E2EE fails; metadata leakage; traffic analysis (timing, size correlation).

### B. Active Man-in-the-Middle Attacker
**Capabilities:** intercept traffic, modify traffic, inject messages, substitute key material, replay communications.
**Concerns:** identity substitution, session compromise, handshake tampering, downgrade attacks.

### C. Malicious Authenticated Client
**Capabilities:** holds a legitimate account, sends malformed protocol messages, attempts sender spoofing, abuses WebSocket semantics, deliberately consumes server resources.

### D. Compromised Relay Server
**Assumption:** the application server can become compromised. Analysis target: whether compromise reveals plaintext, identity secrets, session keys, stored message history, metadata, or authentication information. The E2EE architecture must limit exposure from this scenario to ciphertext, metadata, and authentication data — never plaintext or private keys.

### E. Compromised Database
**Assumption:** an attacker obtains full database contents. Analysis target: what becomes available (ciphertext, password hashes, public keys, metadata) versus what must remain unavailable (plaintext, private keys, reversible passwords).

### F. Credential Attacker
**Includes:** brute-force attacks, credential stuffing, user enumeration, stolen-session-token abuse.

### G. Malicious Web Origin
**Includes:** Cross-Site WebSocket Hijacking (CSWSH), unauthorized WebSocket connections, Origin abuse, cross-site attacks.

### H. Dependency / Software-Supply-Chain Attacker
**Includes:** malicious package, compromised package, dependency confusion, compromised CI workflow, malicious build artifact.

### I. Local-Device Attacker
**Analysis target:** limitations when the user's own endpoint is compromised. E2EE does not protect plaintext once an attacker controls an unlocked, authenticated endpoint — this must be documented as an explicit limitation, not silently assumed away.

### J. Denial-of-Service Actor
**Includes:** connection flooding, oversized messages, message flooding, expensive cryptographic operations, storage exhaustion, skipped-key/ratchet-state abuse.

---

## 8. Attack Surfaces

| Surface | Exposed To | Notes |
|---|---|---|
| Public HTTP(S)/WSS endpoints | Actors A, B, C, F, G, J | Primary network-facing surface |
| Authentication endpoints | Actors B, F | Login, registration, token refresh |
| WebSocket message handling | Actors B, C, G, J | Real-time protocol surface |
| Public identity/prekey distribution | Actors B, D | Integrity of published key material |
| Client rendering of remote content (messages, metadata) | Actor C (via malicious peer) | XSS / injection surface in the UI |
| Local client storage | Actor I | Encrypted-at-rest requirement |
| Server database | Actors D, E | Ciphertext/metadata/credential exposure boundary |
| Dependency graph (npm, pip) | Actor H | Supply-chain surface |
| CI/CD pipeline | Actor H | Build/release integrity surface |
| Deployment/container configuration | Actors D, H | Infrastructure hardening surface |

---

## 9. Data Flows

See [DATA_FLOW_DIAGRAM.md](DATA_FLOW_DIAGRAM.md) for the full text-based (Mermaid)
data-flow and trust-boundary diagrams, including the client↔relay↔database flow,
plaintext/ciphertext boundaries, and the conceptual key-agreement flow.

---

## 10. STRIDE Analysis

STRIDE is used as a systematic completeness check against key components, not
forced onto every component uniformly.

| Component | Spoofing | Tampering | Repudiation | Info Disclosure | DoS | Elevation of Privilege |
|---|---|---|---|---|---|---|
| Auth endpoints | Credential stuffing, enumeration (F) | N/A | Missing audit trail on auth events | Enumeration via error/timing differences | Brute-force login flood (J) | Privilege escalation via broken authz logic |
| WebSocket connection | Origin/session spoofing (G), sender-field spoofing (C) | Message injection/modification in transit if transport integrity fails (B) | No server-side proof of message origin without envelope authentication | Metadata exposure to relay (D) | Connection/message flooding (J) | Unauthorized access to another user's channel |
| Identity/prekey directory | Key substitution (B, D) | Tampering with published public keys (D) | N/A | Public keys are non-secret by design | Flooding prekey requests (J) | N/A |
| Message routing/relay | Sender spoofing if identity not bound to authenticated connection (C) | Ciphertext tampering (detectable via AEAD tag) | No delivery/read receipts without design | Traffic/metadata analysis (A, D) | Resource exhaustion via routing abuse (J) | Relay reading plaintext it should never possess (D) |
| Database | N/A (not directly reachable by external actor) | Direct tampering if compromised (E) | Loss of audit data if compromised (E) | Full data exposure if compromised (E) — must not include plaintext/private keys | Data destruction (E) | Privilege escalation via DB credentials (D, E) |
| Client (browser) | Malicious peer impersonation if identity verification skipped (B) | Local storage tampering (I) | N/A (client-side) | XSS-driven plaintext/key exfiltration (I, malicious content) | Client-side resource exhaustion via crafted payloads (C, J) | Malicious script gaining access to key material via XSS |
| CI/CD & dependencies | N/A | Malicious build artifact (H) | Loss of build provenance | Secret leakage into build logs/artifacts (H) | Pipeline resource abuse (H) | Compromised CI credentials granting deploy access (H) |

---

## 11. Threat Scenarios

Each scenario should eventually receive full STRIDE/mitigation/traceability
treatment (§18); the table below is the master list.

| ID | Scenario |
|---|---|
| TM-001 | Passive interception of message traffic |
| TM-002 | MITM replaces recipient public identity key |
| TM-003 | Relay substitutes attacker-controlled prekey |
| TM-004 | Captured encrypted message is replayed |
| TM-005 | Malicious client spoofs sender identifier |
| TM-006 | Stolen authentication token opens unauthorized WebSocket |
| TM-007 | Database compromise exposes queued messages |
| TM-008 | Application logs accidentally store plaintext |
| TM-009 | Client stores private keys in insecure browser storage |
| TM-010 | Authentication endpoint is brute-forced |
| TM-011 | Malicious Origin initiates WebSocket session (CSWSH) |
| TM-012 | Oversized messages exhaust server resources |
| TM-013 | Dependency compromise steals cryptographic keys |
| TM-014 | Identity-key replacement silently retains trusted state |
| TM-015 | Encryption failure causes plaintext fallback |
| TM-016 | Nonce reuse compromises AEAD confidentiality |
| TM-017 | Old session key exposes historical communication |
| TM-018 | Ratchet skipped-key state is abused for resource exhaustion |
| TM-019 | CI/CD secret is leaked into repository/build artifact |
| TM-020 | Compromised endpoint reads decrypted conversation |

### Detailed threat register

| ID | Component | Threat Actor | Attack | STRIDE | Affected Assets | Security Impact | Existing/Planned Mitigation | Residual Risk | Responsible Phase | Verification Approach | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TM-001 | Network transport | A | Passive packet capture | Info Disclosure | Plaintext (if unencrypted), metadata | Confidentiality loss, traffic analysis | WSS/TLS + E2EE ciphertext on the wire | Metadata (size/timing) remains observable | Phase 2, 6 | Wireshark capture showing ciphertext only | PLANNED |
| TM-002 | Identity/prekey distribution | B | Substitute public identity key in transit or at rest | Spoofing, Tampering | Identity public keys, trust state | Undetected impersonation | Signed prekeys, identity-key authentication, fingerprint verification UX | Users who skip manual verification remain exposed (TOFU risk) | Phase 4, 5 | Protocol test forcing key substitution and asserting detection/warning | PLANNED |
| TM-003 | Relay / prekey store | D | Relay serves attacker-controlled prekey | Spoofing, Tampering | Ephemeral/prekeys, session keys | Session compromise (MITM-in-the-middle via relay) | Prekeys signed by long-term identity key; signature verified client-side | Relay could still withhold/delay legitimate prekeys (availability, not confidentiality) | Phase 5 | Signature verification unit test + adversarial relay simulation | PLANNED |
| TM-004 | Message envelope/session | B, C | Replay a previously captured ciphertext | Tampering, Repudiation | Message integrity, ratchet state | Duplicate/confusing delivery, potential state abuse | Ratchet message numbering + replay/duplicate detection | Detection depends on correct client-side state tracking | Phase 7 | Adversarial replay test asserting rejection | PLANNED |
| TM-005 | WebSocket message envelope | C | Malicious client sets a forged sender field | Spoofing | Message authenticity, routing | Impersonation within the authenticated session model | Sender identity bound server-side to authenticated connection, never trusted from payload | None identified beyond correct implementation | Phase 2, 3 | Protocol test asserting payload-provided sender fields are ignored/rejected | PLANNED |
| TM-006 | Session/token handling | F | Stolen token used to open unauthorized WebSocket | Spoofing, Elevation of Privilege | Auth tokens, session state | Full account impersonation for token lifetime | Short-lived tokens, revocation, WS-level authorization check | Token theft via XSS/endpoint compromise remains a residual risk (§16) | Phase 3 | Token replay/revocation test | PLANNED |
| TM-007 | Database | E | Attacker exfiltrates DB contents | Info Disclosure | Stored ciphertext, metadata, credentials | Metadata/credential exposure; plaintext must remain unavailable | Ciphertext-only storage of message content, Argon2id password hashing | Metadata exposure is inherent (§13), not eliminated | Phase 6, 9 | DB schema review + adversarial "assume DB dump" review | PLANNED |
| TM-008 | Server logging | D | Plaintext or secrets accidentally logged | Info Disclosure | Plaintext messages, secrets | Confidentiality loss via operational tooling rather than protocol failure | Structured, sanitized logging; log-content review; `LOG-001` | Human error in future logging code remains possible without ongoing review | Phase 10 | Log-content audit / automated secret-scanning of log output | PLANNED |
| TM-009 | Client local storage | I | Private keys stored in plaintext in browser storage | Info Disclosure | Identity/session private keys | Full identity compromise on device access | Encrypted local storage design (Phase 9), avoid raw localStorage for secrets | Device-level compromise (unlocked/malware) remains out of E2EE's protection (§14) | Phase 9 | Storage-content inspection test | PLANNED |
| TM-010 | Authentication endpoint | F | Automated credential brute-force | Elevation of Privilege | Passwords, accounts | Account takeover | Rate limiting, lockout/backoff, Argon2id | Distributed low-and-slow attacks partially mitigated only | Phase 3 | Load/abuse test simulating brute force | PLANNED |
| TM-011 | WebSocket handshake | G | Cross-site WebSocket hijacking via malicious origin | Spoofing | Session, auth context | Unauthorized actions in victim's authenticated context | Explicit Origin allowlist, CSRF-resistant WS auth | Misconfigured allowlist would reopen this; requires deployment-time verification | Phase 2, 10 | Adversarial test from disallowed Origin expecting rejection | PLANNED |
| TM-012 | WebSocket/message handling | J | Oversized or high-frequency messages | Denial of Service | Server availability | Resource exhaustion, degraded service for all users | Max message size, rate limits, connection limits, backpressure | Distributed abuse across many accounts partially mitigated only | Phase 2 | Load test asserting bounded resource use | PLANNED |
| TM-013 | Dependency supply chain | H | Malicious/compromised package exfiltrates key material | Info Disclosure, Tampering | All cryptographic assets, source integrity | Full compromise of endpoint or server | Dependency pinning, scanning, SBOM, minimal dependency surface | Zero-day supply-chain compromise remains a residual risk industry-wide | Phase 11 | Dependency scan + SBOM review in CI | PLANNED |
| TM-014 | Identity trust state | B | Identity key silently changes and old trust is retained | Spoofing | Identity binding, session confidentiality | Undetected MITM after key rotation/compromise | `IDENTITY-001`: key change invalidates prior trust state, user warned | Users may dismiss warnings without understanding implications (UX risk) | Phase 4 | Adversarial test: rotate identity key, assert trust invalidation + warning | PLANNED |
| TM-015 | Cryptographic error handling | Any | Encryption/decryption failure silently falls back to plaintext | Info Disclosure | All message confidentiality | Catastrophic, application-wide confidentiality failure | `CRYPTO-007`: fail closed, never fallback | None if correctly implemented and tested | Phase 6 | Fault-injection test asserting failure blocks send/receive rather than degrading | PLANNED |
| TM-016 | AEAD usage | Implementation defect | Nonce reused with same key | Info Disclosure | Message confidentiality (potentially catastrophic, cross-message) | Full or partial plaintext recovery for affected messages | `CRYPTO-005`: formally defined nonce-uniqueness scheme | Implementation bugs remain possible without dedicated testing | Phase 6, 12 | Property-based test asserting nonce uniqueness across session lifetime | PLANNED |
| TM-017 | Ratchet / key lifecycle | D, I | Old session key exposed, used to read historical messages | Info Disclosure | Forward secrecy guarantee | Historical plaintext exposure beyond intended guarantee | Ratchet construction deletes used keys; forward secrecy is a v1 objective | Guarantee is bounded by correct implementation and by the "current guarantees" caveat in §13 of the master plan | Phase 7 | Adversarial test: compromise current state, assert prior messages remain unrecoverable | PLANNED |
| TM-018 | Skipped-message-key cache | J | Attacker forces excessive skipped-key retention | Denial of Service | Server/client resource availability | Memory/storage exhaustion, possible correctness bugs | Bounded skipped-key cache with eviction policy | Requires careful tuning; not yet designed | Phase 7 | Load test forcing large out-of-order gaps | PLANNED |
| TM-019 | CI/CD pipeline | H | Secret leaked into repo history or build artifact | Info Disclosure | CI/CD credentials, deployment secrets | Infrastructure compromise, malicious release | Secret scanning (Gitleaks), scoped CI credentials | Historical leaks before scanning was in place would require separate remediation | Phase 11 | Automated secret scan in CI, blocking on detection | PLANNED |
| TM-020 | Client endpoint | I | Compromised/unlocked endpoint reads decrypted conversation | Info Disclosure | Plaintext, all local key material | Full local compromise; E2EE provides no protection here by design | None at the protocol level — explicitly out of scope (§14) | Always present; this is a documented limitation, not a bug | N/A | Documented as explicit out-of-scope item | OUT_OF_SCOPE |

---

## 12. Security Controls / Planned Mitigations

Mitigations referenced above are indexed here by control family; see
[SECURITY_REQUIREMENTS.md](SECURITY_REQUIREMENTS.md) for the normative requirement
text and IDs.

- **Transport:** WSS/TLS mandatory in production, Origin allowlisting, connection/message limits.
- **Cryptography:** standard reviewed primitives only (Ed25519, X25519, HKDF-SHA-256, AEAD), fail-closed error handling, formally defined nonce uniqueness.
- **Identity:** signed prekeys, identity-change trust invalidation, user-facing fingerprint verification.
- **Session/Auth:** Argon2id hashing, short-lived revocable tokens, rate limiting/lockout.
- **Storage:** ciphertext-only persistence of message content, encrypted local key storage.
- **Logging:** sanitized structured logs, no plaintext/secret logging.
- **Supply chain:** dependency pinning/scanning, SBOM, secret scanning, protected release process.
- **Availability:** rate limits, size limits, bounded skipped-key retention.

All of the above are **planned**, not implemented, as of Phase 0.

---

## 13. Metadata Exposure

The relay necessarily observes, and the v1 architecture does **not** hide:

- Which accounts are communicating with which other accounts (social graph).
- Approximate message timing and frequency.
- Approximate message size (unless explicit padding is later designed — not
  committed for v1).
- Client IP address / network origin, unless a separate anonymization layer is
  added (not in v1 scope).
- Account existence and online/offline presence, to the extent the protocol
  exposes it.

The v1 architecture does hide:

- Message plaintext content.
- Cryptographic private key material.

This distinction must be communicated honestly to end users — the system provides
**content confidentiality**, not **metadata privacy** or **anonymity**. See
out-of-scope §15 below.

---

## 14. Assumptions

See [SECURITY_ASSUMPTIONS.md](SECURITY_ASSUMPTIONS.md) for the full, authoritative
list. Summary of the most consequential assumptions:

- Endpoint cryptographic libraries behave correctly (no custom crypto is written).
- The OS/browser CSPRNG is secure.
- TLS certificate verification functions correctly on the client.
- Dependency integrity is maintained between review and deployment.
- The client endpoint is not already fully compromised at time of use.
- Users perform manual fingerprint verification when strong identity assurance is required.
- Server and database compromise are both treated as realistic, not hypothetical.
- Cryptographic private keys remain endpoint-controlled at all times.

---

## 15. Out of Scope

The following are explicitly **not** guaranteed by this system's v1 design:

- Full sender/recipient anonymity (Tor-like anonymity).
- Complete traffic-analysis resistance.
- Protection against a fully compromised endpoint (TM-020).
- Protection after an attacker controls an already-unlocked, authenticated endpoint.
- Prevention of screenshots or manual copying of plaintext by a legitimate recipient.
- Malicious recipient redistributing plaintext they legitimately received.
- Hardware side-channel attacks (e.g., power analysis, cache timing).
- Nation-state-level endpoint exploitation (0-day OS/browser compromise).
- Guaranteed secure deletion from SSD wear-leveled storage, cloud snapshots, or backups.
- Multi-device synchronization (not implemented in v1).
- Group messaging (not implemented in v1).
- Voice/video calling (not implemented in v1).
- Password recovery flows (excluded from v1 pending explicit design — see §16 open decision).

E2EE must never be marketed or documented as solving any of the above.

---

## 16. Residual Risks

Even with all planned mitigations correctly implemented, the following residual
risks remain and must be communicated to users and stakeholders:

- **Metadata exposure** (§13) is inherent to a client-server relay architecture
  without a dedicated anonymity network.
- **Endpoint compromise** (TM-020) fully defeats E2EE by design; no protocol can
  prevent this.
- **TOFU (trust-on-first-use) risk**: without mandatory out-of-band fingerprint
  verification, a MITM present at first contact could go undetected.
- **Implementation risk**: cryptographic guarantees are only as strong as their
  actual implementation; this must be verified in Phase 12 (adversarial
  verification) before any guarantee is claimed as delivered.
- **Supply-chain risk**: no dependency-scanning regime eliminates all
  supply-chain compromise risk, only reduces likelihood/detection time.
- **Account recovery vs. security tradeoff**: any future recovery mechanism
  inherently creates an alternate path to account/key access and must be
  designed with explicit threat-model review before implementation.

---

## 17. Verification Strategy

Security properties described here are **claims to be verified**, not
**implemented facts**, until the referenced phase completes and produces
evidence. Planned verification approaches, by property:

| Property | Verification Method | Phase |
|---|---|---|
| Transport confidentiality | Network capture (Wireshark) showing ciphertext only | 2, 6 |
| E2EE confidentiality | End-to-end test decrypting only at endpoints; relay-side inspection showing ciphertext only | 6 |
| Identity authenticity | Adversarial substitution test + fingerprint verification UX review | 4, 5 |
| Forward secrecy | Adversarial test compromising current state, asserting past messages unrecoverable | 7, 12 |
| Replay resistance | Adversarial replay test | 7, 12 |
| AEAD nonce uniqueness | Property-based / fuzz test across full session lifetime | 6, 12 |
| Fail-closed crypto errors | Fault-injection test | 6, 12 |
| Auth abuse resistance | Load/abuse simulation (brute force, enumeration) | 3, 12 |
| WS Origin/CSWSH protection | Adversarial cross-origin connection test | 2, 12 |
| DoS bounding | Load test with oversized/high-frequency input | 2, 12 |
| No plaintext in logs/DB | Static review + automated scan of log output and DB schema | 9, 10, 12 |
| Supply-chain integrity | Automated dependency/secret/container scanning in CI | 11 |

Formal adversarial verification against this entire model occurs in **Phase 12**,
and must be repeated against the final release candidate before v1.0 (not only
against development builds).

---

## 18. Threat-to-Requirement Traceability

Representative traceability chains (asset → threat → objective → requirement →
phase → verification). Full mapping lives in
[ASVS_MAPPING.md](ASVS_MAPPING.md) and the requirement documents.

```text
Plaintext messages
  -> TM-001 Passive interception
  -> Confidentiality
  -> E2EE-001
  -> Phase 6
  -> Wireshark capture + E2E test

Identity public keys
  -> TM-002 MITM replaces recipient identity key
  -> Authenticity
  -> IDENTITY-001, CRYPTO-009
  -> Phase 4, 5
  -> Adversarial substitution test

Ratchet state / session keys
  -> TM-017 Old session key exposes historical communication
  -> Forward Secrecy
  -> CRYPTO-003, CRYPTO-004 (ratchet-specific requirements defined in Phase 7 design)
  -> Phase 7
  -> Adversarial compromise-then-verify-past-messages test

Authentication tokens
  -> TM-006 Stolen token opens unauthorized WebSocket
  -> Account Security
  -> AUTH-xxx (defined in SECURITY_REQUIREMENTS.md §4)
  -> Phase 3
  -> Token replay/revocation test

CI/CD secrets
  -> TM-019 Secret leaked into repository/build artifact
  -> Supply-chain integrity
  -> SUPPLY-xxx (defined in SECURITY_REQUIREMENTS.md §19)
  -> Phase 11
  -> Automated secret scan in CI
```

---

## 19. Review / Change History

| Date | Change | Author |
|---|---|---|
| 2026-09-03 | Initial Phase 0 threat model created. No prior version existed. | Phase 0 security architecture pass |

This document must be revisited at the start of every subsequent phase (per the
Execution Rules) and whenever an architectural decision materially changes an
asset, boundary, or threat actor's capability.
