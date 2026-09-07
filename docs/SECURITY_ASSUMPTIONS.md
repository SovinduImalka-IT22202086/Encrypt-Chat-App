# Security Assumptions, Invariants & Open Decisions

**Status:** Phase 0 draft. Assumptions are distinct from guarantees — an
assumption is something later phases are permitted to rely on without
re-proving; it is not itself a security property the system provides to its
adversaries.

---

## 1. Security Assumptions

These are conditions the design relies on but does not itself verify or
enforce. If any assumption is false, the corresponding security objective in
[SECURITY_REQUIREMENTS.md](SECURITY_REQUIREMENTS.md) may not hold, even if all
requirements are correctly implemented.

1. **Endpoint cryptographic libraries behave correctly.** The design does not
   re-implement or independently verify the correctness of the underlying
   crypto library (e.g., libsodium/pynacl/WebCrypto bindings); it assumes the
   library correctly implements the primitives it claims to (Ed25519, X25519,
   AEAD, HKDF).
2. **The operating system / browser CSPRNG is secure.** `CRYPTO-011` depends
   on this; the application does not implement its own entropy source.
3. **TLS certificate verification functions correctly on the client.** The
   design does not implement custom certificate pinning or validation logic in
   v1; it relies on the platform TLS stack.
4. **Dependency integrity is maintained between review and deployment.**
   Scanning (Phase 11) reduces but does not eliminate the risk of a dependency
   changing maliciously between audit and use; reproducible builds and
   checksums (`SUPPLY-009`) partially address this.
5. **The client endpoint is not already fully compromised at the time of
   use.** E2EE protects data in transit and at rest against network and
   server-side attackers; it assumes the endpoint itself is not already under
   attacker control at the moment the user interacts with it (see out-of-scope
   TM-020).
6. **Users correctly perform manual fingerprint/safety-number verification
   when strong identity assurance is required.** `IDENTITY-002` provides the
   mechanism; it does not force its use. Without it, first-contact MITM
   (TOFU risk) is not fully mitigated.
7. **Server compromise is considered possible, not hypothetical.** All server-
   side design decisions must be made as though an attacker may eventually
   read server memory/disk; this is documented as an assumption specifically
   because it is stronger than many systems assume, and later phases must not
   quietly weaken it.
8. **Database compromise is considered possible, not hypothetical.** Same
   posture as above, applied specifically to persisted data.
9. **Cryptographic private keys must remain endpoint-controlled at all
   times.** No later phase may introduce a code path, debug feature, or
   "convenience" export that transmits private key material off-device,
   even temporarily.

---

## 2. Non-Negotiable Security Invariants

These invariants override convenience, schedule pressure, or implementation
difficulty in every later phase. A design or PR that violates one of these
must not be merged without an explicit, documented, reviewed exception.

1. The relay must not receive plaintext private-message content once E2EE is
   implemented.
2. The relay must not possess client identity private keys.
3. The relay must not possess message decryption keys.
4. Authentication identity must not be inferred from untrusted WebSocket
   payload fields.
5. Cryptographic failures must fail closed.
6. There must be no plaintext fallback.
7. Identity changes must not silently retain verified trust.
8. Replayed messages must eventually be detected/rejected.
9. AEAD nonce/key combinations must never be reused.
10. Sensitive secrets and plaintext messages must never be intentionally
    written to server logs.
11. Security claims must eventually be backed by test evidence.
12. Custom cryptographic primitives are prohibited.

---

## 3. Open Decisions (Recorded Honestly — Not Assumed Away)

### DECISION-001

```text
DECISION REQUIRED:
  Single-device versus multi-device identity model.
CURRENT STATUS:
  UNRESOLVED
SECURITY IMPACT:
  Changes identity-key storage, key revocation, and session establishment
  design. Multi-device support significantly increases the complexity of key
  distribution and trust management (each device needs its own identity or a
  synchronization scheme, either of which has distinct threat implications).
REQUIRED BEFORE:
  Phase 4.
```

### DECISION-002

```text
DECISION REQUIRED:
  Whether account recovery (e.g., "forgot password" / lost-device recovery)
  is included in v1, and if so, its exact mechanism.
CURRENT STATUS:
  UNRESOLVED — currently assumed EXCLUDED from v1 (see
  SECURITY_REQUIREMENTS.md AUTH-010 and out-of-scope list), pending explicit
  product confirmation.
SECURITY IMPACT:
  Any recovery mechanism is inherently an alternate path to account/key
  access and can undermine forward secrecy and identity-authenticity
  guarantees if not carefully designed. Excluding it simplifies the v1 threat
  model; including it later requires a dedicated threat-model addendum before
  implementation.
REQUIRED BEFORE:
  Phase 3 (if included in v1) or explicit product sign-off that it is
  deferred post-v1.
```

### DECISION-003

```text
DECISION REQUIRED:
  Whether message attachments are in scope for v1.
CURRENT STATUS:
  UNRESOLVED — currently assumed EXCLUDED from v1.
SECURITY IMPACT:
  If included, attachments must inherit the full E2EE-001..E2EE-004
  requirement set and introduce additional considerations (size limits,
  storage location, content-type handling, potential malware surface).
REQUIRED BEFORE:
  Phase 6.
```

### DECISION-004

```text
DECISION REQUIRED:
  Exact AEAD cipher choice — AES-256-GCM versus XChaCha20-Poly1305 — and the
  specific nonce-construction scheme satisfying CRYPTO-005.
CURRENT STATUS:
  UNRESOLVED — both are acceptable per CRYPTO-001's "standard reviewed
  primitive" requirement; the final choice depends on target runtime
  (native AES-NI availability, library support parity between client and
  server stacks).
SECURITY IMPACT:
  Low, provided nonce-uniqueness is correctly designed for whichever cipher
  is chosen; the wrong choice mainly affects performance, not security,
  assuming CRYPTO-005 is satisfied either way.
REQUIRED BEFORE:
  Phase 6.
```

### DECISION-005

```text
DECISION REQUIRED:
  Specific Argon2id parameters (memory, iterations, parallelism) for AUTH-002,
  tuned to actual target deployment hardware.
CURRENT STATUS:
  UNRESOLVED — deferred until target server hardware/hosting is finalized.
SECURITY IMPACT:
  Under-tuned parameters weaken brute-force resistance; over-tuned parameters
  create a denial-of-service amplification risk on the login endpoint. Must
  be balanced against AUTH-006 rate limiting.
REQUIRED BEFORE:
  Phase 3.
```

---

## 4. Distinguishing Assumptions, Guarantees, and Planned Properties

To avoid overclaiming (per Core Operating Principles, master plan §35):

- An **assumption** (§1 above) is a precondition the system relies on but does
  not itself enforce or verify.
- A **guarantee** is a property the system actively enforces through
  implemented, tested controls. **No guarantees exist yet** — Phase 0 defines
  target guarantees as requirements (`SECURITY_REQUIREMENTS.md`), not delivered
  guarantees.
- A **planned property** is a requirement scheduled for a specific future
  phase, marked `PLANNED`/`REQUIREMENT_DEFINED` in
  [ASVS_MAPPING.md](ASVS_MAPPING.md), that becomes a guarantee only after
  implementation and verification evidence exists (Phase 12 and per-phase
  evidence logs).

This document, `THREAT_MODEL.md`, `SECURITY_REQUIREMENTS.md`, and
`ASVS_MAPPING.md` must be read together, not in isolation, when reviewing any
later implementation decision against Phase 0.
