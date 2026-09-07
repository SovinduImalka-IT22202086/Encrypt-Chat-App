# Phase 0 Evidence Log

**Phase:** 0 — Security Requirements & Threat Model
**Date:** 2026-09-03
**Scope:** Documentation, threat modeling, requirements engineering only. No
application code, no cryptography, no infrastructure was implemented.

---

## 1. Workspace State Inspected

Before any modification, the project directory was inspected recursively.

**Found:**
- `Encrypted_Chat_App_Windows_Execution_Guide.docx` — a pre-existing Windows-adapted
  execution guide covering Phase 0 through Phase 13 (converted from a Linux-based
  master plan). Validated as an intact, non-corrupted OOXML document (594
  extracted text lines, all Phase 0–13 section headers present, checkbox lists
  intact, no truncation at the end of the document).
- No `.git` directory (not yet a git repository).
- No `docs/` directory.
- No existing `THREAT_MODEL.md`, `SECURITY_REQUIREMENTS.md`, or any other Phase 0
  artifact.
- No existing application source code (no `backend/`, `frontend/`, `src/`, etc.).

**Conclusion:** This is a greenfield workspace for implementation purposes; only
the execution-guide document pre-existed. No prior work was at risk of being
overwritten. Nothing was deleted or replaced.

---

## 2. Prerequisite Checks

Commands run and results:

| Tool | Result | Status |
|---|---|---|
| `git --version` | git version 2.54.0.windows.1 | OK |
| `python --version` | Python 3.13.2 | OK |
| `node --version` | v22.18.0 | OK |
| `npm --version` | 11.6.0 | OK |
| `docker --version` | Docker version 29.4.1, build 055a478 | OK |
| `openssl version` | OpenSSL 3.5.6 7 Apr 2026 | OK |
| `wsl --status` | WSL2 installed (default distro: kali-linux) but **unable to start** — virtualization not enabled in firmware / "Virtual Machine Platform" optional component not enabled | MISSING (non-blocking) |

```text
PREREQUISITE: WSL2 virtualization
STATUS: MISSING (present but non-functional)
IMPACT: No impact on Phase 0 (documentation only). Will affect any later
        phase step that requires a Linux-only tool (e.g., certain Semgrep
        setups, systemd-style hardening steps referenced in Phase 10 of the
        execution guide) if not resolved before that phase.
RECOMMENDED ACTION: Before Phase 10/11, enable the "Virtual Machine Platform"
        Windows optional feature and enable virtualization in firmware, then
        re-run `wsl --install --no-distribution` per the guide's own
        instructions. Not required to unblock Phase 0.
```

All other prerequisites are present and were not reinstalled, per instruction not
to unnecessarily reinstall working tools.

---

## 3. Repository / Structure Bootstrap

Actions taken (minor bootstrap only, per the authorized exception in the master
prompt §3/§5):

- `git init` — initialized a new, empty git repository in the project root. No
  commit was created (commits are only made when the user explicitly requests
  one).
- `mkdir docs/` — created the documentation directory.

No application scaffolding, dependencies, or framework files were created.

---

## 4. Files Created

| File | Purpose |
|---|---|
| `docs/THREAT_MODEL.md` | Full threat model: system overview, security objectives, architecture, trust boundaries, asset inventory, threat actors, attack surfaces, STRIDE analysis, 20 threat scenarios (TM-001–TM-020) with full register, mitigations, metadata exposure, assumptions summary, out-of-scope, residual risks, verification strategy, traceability, change history. |
| `docs/SECURITY_REQUIREMENTS.md` | Normative security requirements across 22 sections and 105 stable-ID requirements (ARCH, AUTH, AUTHZ, IDENTITY, CRYPTO, STORAGE, E2EE, WS, INTEGRITY, CLIENT, SERVER, LOG, AVAIL, PRIVACY, DEPLOY, SUPPLY, TEST categories). |
| `docs/DATA_FLOW_DIAGRAM.md` | Mermaid-based data-flow and trust-boundary diagrams: system DFD, component/data-type detail, conceptual authenticated key-agreement sequence, attacker-position overlay. |
| `docs/ASVS_MAPPING.md` | Mapping of internal requirement IDs to OWASP ASVS 5.0.0 areas, target level, planned phase, and verification method, with explicit non-goals and unresolved mapping issues. |
| `docs/SECURITY_ASSUMPTIONS.md` | Explicit security assumptions (distinct from guarantees), the 12 non-negotiable security invariants, and 5 formally recorded open decisions requiring resolution before specific future phases. |
| `docs/PHASE_0_EVIDENCE.md` | This evidence log. |

## 5. Files Modified

None. All files listed above were newly created; no pre-existing file was
altered (the `.docx` execution guide was inspected/read only, not modified).

---

## 6. Threat Model Review Summary

- **Assets documented:** 30 individual assets across 5 categories (message,
  cryptographic, authentication, privacy, infrastructure), each with owner,
  location, C/I/A ratings, attackers, impact, and expected protection.
- **Threat actors modeled:** 10 (A through J) — passive network observer,
  active MITM, malicious authenticated client, compromised relay, compromised
  database, credential attacker, malicious web origin, dependency/supply-chain
  attacker, local-device attacker, denial-of-service actor.
- **Threat scenarios:** 20 (TM-001–TM-020), each with a full register entry
  (component, actor, attack, STRIDE category, affected assets, impact,
  mitigation, residual risk, responsible phase, verification approach,
  status).
- **Trust boundaries:** 10, enumerated and mapped to the plaintext-placement
  invariant.
- **STRIDE completeness check:** performed across 7 major components (auth
  endpoints, WebSocket connection, identity/prekey directory, message
  routing/relay, database, client/browser, CI/CD & dependencies) rather than
  forced uniformly onto every element.

---

## 7. Security Requirements Summary

- **Total requirements:** 105 individually identified requirements (see
  §1 count methodology below) plus §2 security principles (P1–P6) as
  overarching, non-ID'd guidance.
- **Requirement counts by category:**

  | Category | Count |
  |---|---|
  | ARCH | 4 |
  | AUTH | 10 |
  | AUTHZ | 3 |
  | AVAIL | 4 |
  | CLIENT | 9 |
  | CRYPTO | 11 |
  | DEPLOY | 4 |
  | E2EE | 4 |
  | IDENTITY | 4 |
  | INTEGRITY | 3 |
  | LOG | 3 |
  | PRIVACY | 3 |
  | SERVER | 8 |
  | STORAGE | 7 |
  | SUPPLY | 10 |
  | TEST | 5 |
  | WS | 13 |
  | **Total** | **105** |

  Counted by extracting all unique `CATEGORY-###` identifiers present in
  `docs/SECURITY_REQUIREMENTS.md` (verified via automated grep against the
  final file, not hand-counted).

- **Highest-priority security invariants:** the 12 non-negotiable invariants
  in `SECURITY_ASSUMPTIONS.md §2`, most critically: relay/database must never
  receive plaintext or private keys (invariants 1–3), cryptographic failures
  must fail closed with no plaintext fallback (invariants 5–6), and custom
  cryptography is prohibited (invariant 12).

---

## 8. ASVS Mapping Status

- Mapping created at `docs/ASVS_MAPPING.md` covering all requirement
  categories against OWASP ASVS 5.0.0, target Level 2 baseline with elevated
  (approaching L3) treatment for cryptography, authentication, session
  management, key management, secure communication, and stored cryptographic
  material.
- All mapped items use status `REQUIREMENT_DEFINED`, `PLANNED`,
  `NOT_APPLICABLE`, `OUT_OF_SCOPE`, or `BLOCKED` — **no item is marked
  `IMPLEMENTED`**, consistent with the rule against overclaiming.
- **Unresolved mapping issues (documented, not hidden):**
  1. Forward secrecy / ratchet guarantees do not map to one discrete ASVS
     control ID and are treated as a design property layered on V11 key-
     management controls; should be revisited against the final published
     ASVS 5.0.0 section numbering before Phase 12 verification.
  2. `AUTH-010` (account recovery) mapping is `BLOCKED` pending
     `DECISION-002`.
  3. `IDENTITY-004` (single vs multi-device) mapping is `BLOCKED` pending
     `DECISION-001`.

---

## 9. Unresolved Decisions / Blocked Items

Five decisions were explicitly recorded as unresolved rather than assumed away
(`docs/SECURITY_ASSUMPTIONS.md §3`):

1. `DECISION-001` — Single-device vs multi-device identity model (required
   before Phase 4).
2. `DECISION-002` — Account recovery inclusion/mechanism (required before
   Phase 3 if included, or explicit deferral sign-off).
3. `DECISION-003` — Message attachment support in v1 (required before Phase
   6).
4. `DECISION-004` — AES-256-GCM vs XChaCha20-Poly1305 + nonce construction
   (required before Phase 6).
5. `DECISION-005` — Specific Argon2id tuning parameters (required before
   Phase 3).

None of these block Phase 0 itself — they block specific *later* phases and
are recorded so those phases cannot silently proceed without addressing them.

---

## 10. Self-Review Against Mandatory Checklist (Master Plan §31)

| Item | Status |
|---|---|
| Assets identified | PASS |
| DFD created | PASS |
| Trust boundaries identified | PASS |
| Passive observer modeled | PASS |
| Active MITM modeled | PASS |
| Malicious client modeled | PASS |
| Compromised relay modeled | PASS |
| Compromised database modeled | PASS |
| Credential attacker modeled | PASS |
| Malicious web origin modeled | PASS |
| Dependency compromise modeled | PASS |
| Local-device attacker modeled | PASS |
| DoS actor modeled | PASS |
| Confidentiality requirements defined | PASS |
| Integrity requirements defined | PASS |
| Authenticity requirements defined | PASS |
| Forward-secrecy objective defined | PASS |
| Replay-resistance objective defined | PASS |
| Account-security requirements defined | PASS |
| Availability requirements defined | PASS |
| Metadata limitations documented | PASS |
| Explicit out-of-scope list written | PASS |
| THREAT_MODEL.md complete | PASS |
| SECURITY_REQUIREMENTS.md complete | PASS |
| ASVS 5.0.0 mapping created | PASS |
| Security invariants documented | PASS |
| Requirements use stable identifiers | PASS |
| Threat-to-requirement traceability exists | PASS |
| Future implementation phase mapping exists | PASS |
| Open decisions documented honestly | PASS |
| Phase 0 evidence recorded | PASS (this document) |

**No item is FAIL or BLOCKED.** The five open architectural decisions (§9
above) are separately tracked and gate specific *future* phases, not Phase 0
itself — Phase 0's job was to identify and record them, which it did.

---

## 11. Final Phase 0 Gate Decision

```text
PHASE 0: COMPLETE
```

Rationale: the threat model, trust boundaries, asset inventory, threat-actor
and threat-scenario registers, security requirements (with stable IDs and
SHALL/SHALL NOT language), ASVS 5.0.0 mapping, explicit out-of-scope
statement, non-negotiable invariants, and traceability chains are sufficient
in depth and specificity to constrain and review every architectural or
implementation decision in Phases 1–13. No application, cryptographic,
authentication, transport, storage, deployment, or CI/CD implementation was
performed. Open decisions were recorded honestly rather than resolved by
assumption.

**No Phase 1 implementation has been started. Awaiting explicit authorization
for Phase 1.**
