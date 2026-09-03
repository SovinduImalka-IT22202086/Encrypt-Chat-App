# Encrypted Chat Application

A security-first, end-to-end encrypted direct-messaging application, built in
strict phase order so that every implementation decision can be reviewed
against a threat model written before any code existed.

> **⚠️ This project does not yet implement encrypted messaging.**
> Phase 1 establishes the development environment and repository only. There is
> no working chat, no authentication, and no cryptography. See
> [Current security status](#current-security-status).

---

## Current security status

```text
Phase 0 — COMPLETE
  Security requirements and threat model established.

Phase 1 — COMPLETE
  Secure repository and development environment.

WebSocket Transport        — NOT IMPLEMENTED
Authentication             — NOT IMPLEMENTED
Identity Verification      — NOT IMPLEMENTED
Key Agreement              — NOT IMPLEMENTED
End-to-End Encryption      — NOT IMPLEMENTED
Ratcheting                 — NOT IMPLEMENTED
Encrypted Local Storage    — NOT IMPLEMENTED
Production Hardening       — NOT IMPLEMENTED
Independent Security Audit — NOT PERFORMED
```

The `cryptography` and `argon2-cffi` packages are installed as environment
preparation. **Their presence does not mean any cryptography is implemented.**

---

## Security-first roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Security requirements & threat model | COMPLETE |
| 1 | Secure development environment & repository | COMPLETE |
| 2 | WebSocket transport infrastructure | Not started |
| 3 | Authentication & account security | Not started |
| 4 | Identity & trust | Not started |
| 5 | Authenticated X25519 key agreement | Not started |
| 6 | End-to-end encryption layer | Not started |
| 7 | Forward secrecy, ratcheting & replay protection | Not started |
| 8 | Secure React frontend | Not started |
| 9 | Encrypted local storage & key protection | Not started |
| 10 | Server & deployment hardening | Not started |
| 11 | Secure CI/CD & software supply chain | Not started |
| 12 | Adversarial security verification | Not started |
| 13 | Public release & post-release security | Not started |

Phases run strictly in order. A phase is not complete until its checklist and
exit gate both pass, with evidence recorded in `docs/`.

---

## Prerequisites (Windows)

| Tool | Minimum | Install |
|---|---|---|
| Git | any recent | `winget install --id Git.Git -e` |
| Python | 3.11+ | `winget install --id Python.Python.3.11 -e` |
| Node.js | LTS (20+) | `winget install --id OpenJS.NodeJS.LTS -e` |
| Gitleaks | 8.x | `winget install --id Gitleaks.Gitleaks -e` |
| OpenSSL | 3.x | `winget install --id ShiningLight.OpenSSL.Light -e` |
| Docker Desktop | any recent | `winget install --id Docker.DockerDesktop -e` |

Docker and OpenSSL are not used by Phase 1 checks; they are listed because
later phases (10–11) require them.

Verify:

```powershell
git --version; python --version; node --version; npm --version; gitleaks version
```

If PowerShell blocks virtual-environment activation, set the minimum required
scope (current user only — do not weaken machine-wide policy):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

All Phase 1 commands run as a **normal user**. Administrator PowerShell is not
required for development; only package installers may prompt for elevation.

---

## Setup

Clone, then set up each side of the project.

### Backend

```powershell
cd server
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend

```powershell
cd client
npm ci
```

`npm ci` (not `npm install`) is used so `package-lock.json` is authoritative.

### Pre-commit hooks (once per clone)

```powershell
cd server
.venv\Scripts\Activate.ps1
cd ..
pre-commit install
```

---

## Commands

Run backend commands from `server/` with the virtual environment activated.

| Purpose | Backend | Frontend (`client/`) |
|---|---|---|
| Lint | `ruff check .` | `npm run lint` |
| Format check | `ruff format --check .` | — (ESLint only) |
| Type check | `mypy .` | `npm run typecheck` |
| Tests | `pytest` | `npm run test` |
| Build | — | `npm run build` |
| Dependency audit | `pip-audit -r requirements.txt` | `npm audit` |

Repository-wide:

```powershell
pre-commit run --all-files
gitleaks dir . --config .gitleaks.toml --verbose
```

Run the development servers (optional, Phase 1 scaffold only):

```powershell
cd server; .venv\Scripts\Activate.ps1; uvicorn app.main:app --reload   # http://127.0.0.1:8000/health
cd client; npm run dev                                                 # http://127.0.0.1:5173
```

---

## Dependency management

**Backend** uses `pip-tools`. `server/requirements.in` holds direct
dependencies; `server/requirements.txt` is the compiled, fully pinned lock
covering all transitive dependencies. Never edit `requirements.txt` by hand:

```powershell
pip-compile requirements.in --output-file requirements.txt --strip-extras
pip-audit -r requirements.txt
```

**Frontend** uses `package-lock.json`, which is committed and installed with
`npm ci`.

---

## Repository structure

```text
.
├── client/              React + TypeScript + Vite frontend (scaffold only)
├── server/              FastAPI backend (scaffold only)
│   ├── app/             Application package
│   ├── tests/           Backend tests
│   ├── requirements.in  Direct dependencies (edit this)
│   ├── requirements.txt Compiled pinned lock (generated)
│   └── pyproject.toml   Ruff / mypy / pytest configuration
├── protocol/            Reserved: shared protocol definitions (Phase 2+)
├── tests/               Reserved: cross-cutting/integration tests (Phase 2+)
├── deploy/              Reserved: deployment configuration (Phase 10)
├── scripts/             Developer utility scripts
├── docs/                Security documentation and phase evidence
│   ├── THREAT_MODEL.md
│   ├── SECURITY_REQUIREMENTS.md
│   ├── DATA_FLOW_DIAGRAM.md
│   ├── ASVS_MAPPING.md
│   ├── SECURITY_ASSUMPTIONS.md
│   ├── PHASE_0_EVIDENCE.md
│   └── PHASE_1_EVIDENCE.md
└── .github/workflows/   CI
```

`protocol/`, `tests/`, and `deploy/` are intentionally empty placeholders —
populating them is the job of later phases.

---

## Security documentation

- [Threat model](docs/THREAT_MODEL.md) — assets, actors, trust boundaries, 20 threat scenarios
- [Security requirements](docs/SECURITY_REQUIREMENTS.md) — 105 requirements with stable IDs
- [Data flow diagram](docs/DATA_FLOW_DIAGRAM.md)
- [ASVS 5.0.0 mapping](docs/ASVS_MAPPING.md)
- [Security assumptions & invariants](docs/SECURITY_ASSUMPTIONS.md)
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

Phase 0 documentation is **authoritative** for all future design decisions.

---

## License

Not yet decided.

```text
LICENSE DECISION: REQUIRED
STATUS: BLOCKED / UNRESOLVED
```

No license file has been added because the licensing choice belongs to the
project owner. Until a license is chosen, default copyright applies and the
code carries no grant of reuse rights.
