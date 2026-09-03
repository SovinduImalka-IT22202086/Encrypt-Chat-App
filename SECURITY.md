# Security Policy

## Project status — read this first

This project is **under active development and is not production-ready**.

```text
Independent security audit:  NOT PERFORMED
Formal cryptographic review: NOT PERFORMED
Penetration test:            NOT PERFORMED
Production deployment:       NOT SUPPORTED
```

As of Phase 1, the repository contains a development environment and scaffold
only. **No encrypted messaging, authentication, key agreement, or cryptography
is implemented.** Do not use this software to protect real, sensitive
communications. Any security property described in `docs/` is a *requirement*
or a *plan*, not a delivered, verified guarantee.

This notice will be updated as phases complete — and only with evidence behind
it. No claim of auditing or verification will be made unless it has actually
happened.

---

## Reporting a vulnerability

> **Placeholder — a permanent reporting channel has not yet been established.**
> A dedicated security contact and disclosure process will be published before
> any public release (Phase 13). Until then, report privately to the repository
> owner through the project's private channels.

When reporting, please include:

- affected component and version/commit;
- a description of the issue and its security impact;
- reproduction steps or a proof of concept;
- any suggested remediation.

**Do not**:

- open a public issue containing exploit details before the issue is addressed;
- include real credentials, private keys, or other live secrets in a report;
- test against infrastructure you do not own or have permission to test.

We will acknowledge reports and keep reporters informed of remediation
progress. A formal SLA will be defined alongside the permanent reporting
channel.

---

## Secrets policy

Publishing secrets is prohibited. Never commit, paste into an issue, or
otherwise publish:

- passwords or password hashes;
- API keys, tokens, or session credentials;
- JWT or other signing secrets;
- private cryptographic keys of any kind;
- TLS private keys;
- database credentials or connection strings containing credentials;
- production `.env` files.

The repository is protected by Gitleaks in pre-commit hooks and in CI. If a
secret is committed anyway, treat it as **compromised**: rotate or revoke it
immediately, then remove it from history. Removing the file in a later commit
is not sufficient — the value must be rotated.

---

## Scope and limitations

Even once implemented, the intended design explicitly does **not** protect
against certain threats. These are documented, not hidden — see
[docs/THREAT_MODEL.md §15](docs/THREAT_MODEL.md) for the full list. In summary,
the planned architecture does not provide:

- sender/recipient anonymity or traffic-analysis resistance;
- metadata privacy (the relay necessarily observes who talks to whom, and when);
- protection against a compromised endpoint;
- protection against a malicious recipient copying plaintext they legitimately
  received;
- defence against hardware side-channel attacks.

End-to-end encryption protects **message content**. It does not solve the items
above, and this project will not claim otherwise.

---

## Security documentation

| Document | Contents |
|---|---|
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Assets, threat actors, trust boundaries, threat scenarios, residual risks |
| [docs/SECURITY_REQUIREMENTS.md](docs/SECURITY_REQUIREMENTS.md) | Normative security requirements with stable IDs |
| [docs/SECURITY_ASSUMPTIONS.md](docs/SECURITY_ASSUMPTIONS.md) | Assumptions, non-negotiable invariants, open decisions |
| [docs/ASVS_MAPPING.md](docs/ASVS_MAPPING.md) | OWASP ASVS 5.0.0 mapping (target Level 2 baseline) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development security baseline for contributors |
