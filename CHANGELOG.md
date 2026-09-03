# Changelog

All notable changes to this project are recorded here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is pre-release and does not yet follow semantic versioning; it is
versioned by development phase.

> **Note:** entries describe development and security *scaffolding*. No
> encrypted messaging functionality exists yet.

---

## [Unreleased]

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
