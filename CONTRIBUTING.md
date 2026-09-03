# Contributing

This is a security-sensitive project. The rules below are not style
preferences — several of them exist to protect security properties defined in
[docs/SECURITY_REQUIREMENTS.md](docs/SECURITY_REQUIREMENTS.md) and
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

---

## Development security baseline

These ten rules apply to every change, in every phase:

1. **No secrets in source control.** Ever. Use `.env` (git-ignored) locally and
   a secret manager in deployment. `.env.example` holds placeholders only.
2. **Dependencies must be pinned/locked.** Backend via compiled
   `requirements.txt`; frontend via committed `package-lock.json`.
3. **Dependency changes require audit checks.** Run `pip-audit` / `npm audit`
   in the same change that alters dependencies, and report findings.
4. **Automated tests accompany features.** Security-relevant tests ship in the
   same phase as the feature they protect — never deferred to Phase 12.
5. **Static checks must pass before merge.** Ruff, mypy, ESLint, `tsc`, and
   both test suites.
6. **Cryptographic implementation must follow Phase 0 requirements**
   (`CRYPTO-001` … `CRYPTO-011`).
7. **No custom cryptography.** Standard, reviewed primitives and constructions
   only.
8. **Security requirements cannot be silently weakened.** Changing one requires
   updating the requirement document and saying why.
9. **Security-relevant deviations must be documented** in the phase evidence
   log, with the reason and the residual risk.
10. **Later phases cannot be marked complete without evidence.** "It looks
    done" is not evidence; command output and tests are.

---

## Setup

See [README.md](README.md#setup). Summary:

```powershell
cd server; python -m venv .venv; .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip; pip install -r requirements.txt
cd ..\client; npm ci
cd ..; pre-commit install
```

Development uses a **normal user account**. Do not normalize Administrator
PowerShell for ordinary development commands.

---

## Before you push

```powershell
# Backend (from server/, venv activated)
ruff check .
ruff format --check .
mypy .
pytest
pip-audit -r requirements.txt

# Frontend (from client/)
npm run lint
npm run typecheck
npm run test
npm run build
npm audit

# Repository
pre-commit run --all-files
gitleaks dir . --config .gitleaks.toml --verbose
git status
```

Confirm `git status` shows no `.env`, `.venv/`, `node_modules/`, private keys,
databases, build output, or test artifacts staged.

---

## Coding expectations

**Python**
- Ruff handles both linting and formatting — do not add Black, isort, or
  flake8 (overlapping tooling).
- mypy runs in `strict` mode. Annotate public functions; do not add blanket
  `# type: ignore`. If an ignore is genuinely required, use the specific error
  code and a comment explaining why.
- `print()` is linted out of server code (`T20`). Use structured logging, and
  never log secrets or message plaintext (`LOG-001`, `LOG-002`).

**TypeScript / React**
- ESLint runs with type-aware rules. `any` is an error.
- Do not render untrusted content as raw HTML (`CLIENT-001`). `eval` and
  equivalents are errors.
- Never place a secret behind a `VITE_` prefix — those are bundled into the
  public build (`CLIENT-006`).

**Suppressions**
Do not disable a lint rule, type check, or test to get a green result. If a
suppression is genuinely correct, scope it as narrowly as possible and comment
the justification. The same applies to `pytest` warning filters — scope them to
a specific third-party message, never blanket-ignore a category.

---

## Dependency changes

Backend:

```powershell
# 1. Edit requirements.in (direct dependencies only)
# 2. Recompile the lock
pip-compile requirements.in --output-file requirements.txt --strip-extras
# 3. Audit before committing
pip-audit -r requirements.txt
```

Frontend: use `npm install <pkg>` (which updates `package-lock.json`), then
`npm audit`. Do **not** run `npm audit fix --force` — it performs breaking
major upgrades without review.

Commit the updated lockfile in the same change as the dependency edit. Every
new dependency expands the supply-chain attack surface (threat actor H,
`TM-013`); prefer fewer, well-maintained packages.

---

## Branches, commits, and review

- Work on a branch; do not commit directly to the default branch.
- Keep commits scoped to one logical change.
- Reference the requirement or threat ID when a change implements or affects
  one (e.g. "implements `WS-002` Origin allowlist, mitigates `TM-011`").
- CI must be green before merge.

---

## Phase discipline

This project is phase-gated. Do not implement functionality belonging to a
later phase, even if it seems small or convenient. If you believe a phase
boundary is wrong, raise it and get the roadmap changed — do not route around
it in code.

Report a phase complete only when its exit gate is demonstrably satisfied, with
evidence recorded in `docs/PHASE_<n>_EVIDENCE.md`.

---

## Reporting a vulnerability

See [SECURITY.md](SECURITY.md). Do not open a public issue containing exploit
details or real secrets.
