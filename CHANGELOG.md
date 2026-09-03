# Changelog

All notable changes to this project are recorded here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is pre-release and does not yet follow semantic versioning; it is
versioned by development phase.

> **Note:** entries describe development and security *scaffolding*. No
> encrypted messaging functionality exists yet.

---

## [Unreleased]

### Phase 2 — WebSocket transport infrastructure (2026-09-03)

**Added**

- WebSocket transport endpoint at `/ws/v1` with a versioned protocol (v1).
- Connection manager owning all live transport state on `app.state`, with
  registration, direct recipient lookup, and unconditional cleanup on
  disconnect.
- Strict, versioned Pydantic message envelope (`version`, `message_id`, `type`,
  `sender`, `recipient`, `timestamp`, `payload`) that rejects unknown fields.
- Explicit message-type allowlist; unknown and server-only types are rejected
  rather than ignored.
- Direct recipient routing with a delivery-acknowledgement flow
  (`delivered` / `queued` / `recipient_unavailable` / `rejected`).
- Transport-level sender binding: the server derives sender identity from the
  connection and refuses envelopes whose `sender` does not match.
- Bounded in-memory offline queue abstraction, drained on reconnect. It never
  inspects payloads, so Phase 6 can substitute ciphertext without
  restructuring it.
- WebSocket Origin allowlist enforced before the upgrade is accepted; a
  wildcard allowlist is discarded rather than honoured.
- Resource controls: application message-size cap, global and per-identity
  connection limits, per-connection fixed-window message rate limit, bounded
  per-connection outbound queue with a dedicated writer task (backpressure),
  and bounded offline-queue growth.
- Application-level heartbeat (`heartbeat.ping`/`heartbeat.pong`) and idle
  timeout with registry cleanup.
- 15 deterministic, non-sensitive protocol error codes.
- Structured transport logging that records correlation identifiers and never
  message content.
- 149 backend transport tests covering connection lifecycle, routing,
  no-broadcast, sender spoofing, schema validation, Origin policy, resource
  limits, heartbeat/idle, logging hygiene, and a multi-client suite driving a
  real uvicorn server over real sockets.
- Frontend **Development Transport Test** panel (connect/disconnect, send a
  test message, view acknowledgements and received messages), explicitly
  labelled "Not Authenticated" and "Not End-to-End Encrypted", with 8 tests.
- `docs/WEBSOCKET_PROTOCOL.md` documenting the endpoint, envelope, message
  types, acknowledgement semantics, queue behaviour, limits, Origin policy,
  error codes, reconnect behaviour, and Phase 2 limitations.
- `docs/PHASE_2_EVIDENCE.md` recording actual command output and results.

**Changed**

- `app/main.py` refactored to a `create_app(limits)` factory so transport
  limits are injectable and each app instance owns isolated state.
- Health endpoint now reports `"phase": "2"`.
- Phase 2 implementation status appended to `docs/ASVS_MAPPING.md`; the
  Phase 0 requirement baseline table is unchanged.

**Dependencies**

- Added `websockets` 16.1.1 (standalone client for the multi-client test) and
  `pytest-asyncio` 1.4.0. Lock recompiled to 74 pinned packages.

**Security**

- Private messages are routed only to the intended recipient and are never
  broadcast; verified in-process and over real sockets.
- Client-supplied `sender` is never treated as authoritative.
- No durable plaintext message persistence was introduced. Guard tests assert
  the transport package imports no persistence library and writes no files.
- Message payloads are never written to logs; verified by scanning captured
  log records for a payload marker.

**Not implemented** (deliberately, per phase gating): authentication, sessions
or tokens, cryptographic identity, key agreement, end-to-end encryption,
ratcheting, cryptographic replay protection, encrypted local storage, and
production deployment hardening. Transport identities are
`TRANSPORT_TEST_IDENTITY` / `NOT_AUTHENTICATED` and payloads are plaintext.

---

### Phase 1 — Secure development environment & repository (2026-09-03)

**Added**

- Secure project structure (`client/`, `server/`, `protocol/`, `tests/`,
  `deploy/`, `scripts/`, `docs/`, `.github/workflows/`).
- Reproducible Python backend environment: virtual environment, `pip-tools`
  dependency locking (`requirements.in` → pinned `requirements.txt`, 73
  packages), and a minimal FastAPI scaffold exposing a single non-sensitive
  `GET /health` endpoint.
- React + TypeScript + Vite frontend scaffold with a committed
  `package-lock.json`, installed via `npm ci`.
- Backend quality tooling: Ruff (lint + format, with the `S`/flake8-bandit
  security ruleset enabled), mypy in `strict` mode, and pytest configured with
  warnings-as-errors.
- Frontend quality tooling: ESLint with type-aware `typescript-eslint` rules,
  `eslint-plugin-react-hooks`, TypeScript project type checking, and Vitest
  with jsdom + Testing Library.
- Baseline infrastructure tests: 4 backend smoke tests, 3 frontend tests.
- Pre-commit controls: file hygiene, YAML/JSON/TOML validation, large-file and
  private-key detection, Ruff lint/format, and Gitleaks.
- Secret scanning with Gitleaks (pre-commit hook and CI job).
- Dependency vulnerability auditing: `pip-audit` and `npm audit`.
- Baseline GitHub Actions CI: backend job (Ruff, mypy, pytest, pip-audit) and
  frontend job (ESLint, `tsc`, Vitest, production build, npm audit) both on
  `windows-latest` to match the documented developer platform, plus a
  full-history Gitleaks secret-scanning job.
- Security-aware `.gitignore` (environments, secrets, keys, certificates, local
  databases, logs, build and test output).
- `.env.example` containing placeholders only.
- Documentation: `README.md` (setup, commands, structure, current security
  status), `CONTRIBUTING.md` (including the ten-point development security
  baseline), `SECURITY.md` (vulnerability reporting placeholder, secrets
  policy, explicit scope limitations), and this changelog.
- `docs/PHASE_1_EVIDENCE.md` recording actual command output and validation
  results.

**Changed**

- Replaced the Vite template's default `oxlint` with ESLint +
  `typescript-eslint`, as specified for this phase, to avoid running two
  overlapping linters.
- Replaced the Vite marketing landing page with a minimal status placeholder
  that states no encrypted messaging is implemented.

**Security**

- No secrets, keys, environment files, or credentials are committed.
- `pip-audit`: no known vulnerabilities. `npm audit`: 0 vulnerabilities.
- Installing `cryptography` and `argon2-cffi` is environment preparation only —
  no cryptographic or authentication functionality is implemented.

**Not implemented** (deliberately, per phase gating): WebSocket transport,
authentication, identity verification, key agreement, end-to-end encryption,
ratcheting, encrypted local storage, production hardening.

---

### Phase 0 — Security requirements & threat model (2026-09-03)

**Added**

- `docs/THREAT_MODEL.md` — system overview, security objectives, architecture,
  10 trust boundaries, 30 assets across 5 categories, 10 threat actors, attack
  surfaces, STRIDE analysis, 20 threat scenarios (`TM-001`–`TM-020`) with a
  full threat register, metadata exposure analysis, out-of-scope statement,
  residual risks, verification strategy, and threat-to-requirement
  traceability.
- `docs/SECURITY_REQUIREMENTS.md` — 105 requirements with stable identifiers
  across 17 categories, using SHALL / SHALL NOT language.
- `docs/DATA_FLOW_DIAGRAM.md` — Mermaid data-flow, trust-boundary,
  key-agreement, and attacker-position diagrams.
- `docs/ASVS_MAPPING.md` — OWASP ASVS 5.0.0 mapping, target Level 2 baseline
  with elevated treatment for cryptography, authentication, session and key
  management.
- `docs/SECURITY_ASSUMPTIONS.md` — 9 security assumptions, 12 non-negotiable
  security invariants, and 5 formally recorded open decisions.
- `docs/PHASE_0_EVIDENCE.md` — Phase 0 evidence log and exit-gate decision.

**Security**

- No control is claimed as implemented. All requirements are recorded as
  `REQUIREMENT_DEFINED`, `PLANNED`, `BLOCKED`, `NOT_APPLICABLE`, or
  `OUT_OF_SCOPE`.
