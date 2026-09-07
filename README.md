# Encrypted Chat Application

A security-first, end-to-end encrypted direct-messaging application, built in
strict phase order so that every implementation decision can be reviewed
against a threat model written before any code existed.

**Release v0.1.0 — research prototype.**

> **⚠️ This project has NOT been independently audited, and is not for real use.**
>
> Phases 0–13 are complete: authentication, Ed25519 identity with manual
> verification, authenticated X25519 key agreement, AES-256-GCM end-to-end
> encryption, a Double Ratchet with replay protection, a secure frontend,
> encrypted local storage, a hardened containerised deployment, CI/CD and
> supply-chain controls, and an internal adversarial security campaign.
>
> **That campaign was run by the people who wrote the code. It is not an
> audit.** No independent party has reviewed this. Internal testing finds the
> problems its authors thought to look for — Phase 12 found two real defects,
> which is evidence both that the process works and that a fresh set of eyes
> would find more.
>
> Read [what this does not protect against](docs/SECURITY_LIMITATIONS.md)
> before doing anything with it.

---

## Current security status

```text
Phase 0 — COMPLETE
  Security requirements and threat model established.

Phase 1 — COMPLETE
  Secure repository and development environment.

Phase 2 — COMPLETE
  WebSocket transport infrastructure (routing/protocol only).

Phase 3 — COMPLETE
  Account authentication, sessions, and authorized WebSocket transport.

Phase 4 — COMPLETE
  Cryptographic identity, manual verification, identity-change detection.

Phase 5 — COMPLETE
  Authenticated X25519 key agreement, HKDF-SHA-256 session/root derivation.

Phase 6 — COMPLETE
  End-to-end AEAD message encryption (AES-256-GCM), ciphertext-only relay.

Phase 7 — COMPLETE
  Double Ratchet: per-message keys, X25519 DH ratchet, replay protection,
  bounded out-of-order delivery.

Phase 8 — COMPLETE
  Secure React frontend: authentication, contacts, conversations, fingerprint
  verification, accurate security-state display, strict CSP, XSS resistance.

Phase 9 — COMPLETE
  Encrypted local storage: AES-256-GCM at rest under a non-extractable,
  per-scope storage key; encrypted history, identity, session and ratchet
  state; cryptographic deletion; safe-by-default export.

Phase 10 — COMPLETE
  Server & deployment hardening. HTTPS/WSS behind an nginx reverse proxy,
  fail-closed production configuration, explicit Origin and CORS allowlists,
  security headers, bounded requests/connections/rates, non-root containers
  with dropped capabilities and read-only filesystems, segmented networks, a
  least-privileged database role, structured logging with redaction, and
  minimal health/readiness. Verified against the running stack: 66 deployment
  checks, 3 end-to-end browser tests through the proxy, 29 transport checks.

Phase 11 — COMPLETE (workflows not yet executed remotely)
  CI/CD & supply-chain security. Four workflows covering quality gates,
  secret scanning, SAST, dependency and container scanning, SBOM generation
  and release integrity. Every check verified locally; GitHub Actions has
  not run them. See docs/PHASE_11_EVIDENCE.md §2.

Phase 12 — COMPLETE
  Adversarial security verification. 58 relay-side attacks from an
  authenticated attacker account, 9 browser attacks against the deployed
  stack, database/log/network forensics, and client crypto and storage
  tampering. Found 2 Medium defects, both fixed, regression-tested and
  mutation-verified. 0 Critical, 0 High, 0 unresolved.
  INTERNAL ASSESSMENT — NOT AN INDEPENDENT AUDIT.

Phase 13 — COMPLETE
  Public release and disclosure. Versioned artifacts with SHA-256 checksums,
  CycloneDX SBOM, installation/upgrade/rollback documentation, vulnerability
  disclosure process, incident response, and security limitations.

WebSocket Transport        — IMPLEMENTED (authenticated, ciphertext payloads)
Account Authentication     — IMPLEMENTED (Argon2id, JWT sessions, revocation)
Cryptographic Identity     — IMPLEMENTED (Ed25519, client-held private keys)
Manual Identity Verification — IMPLEMENTED (fingerprint / safety code)
Identity-Change Detection  — IMPLEMENTED (fails closed, clears VERIFIED)
Authenticated Key Agreement — IMPLEMENTED (X25519, Ed25519-signed material)
HKDF Session/Root Derivation — IMPLEMENTED (HKDF-SHA-256, domain-separated)
Message E2EE               — IMPLEMENTED (AES-256-GCM, AAD-authenticated)
Per-Message Ratchet Keys   — IMPLEMENTED (Double Ratchet, HMAC-SHA-256 chains)
X25519 DH Ratchet          — IMPLEMENTED (fresh entropy on direction change)
Message Replay Protection  — IMPLEMENTED (ratchet position, not message id)
Bounded Out-of-Order Delivery — IMPLEMENTED (MAX_SKIP = 1000)
Forward Secrecy            — IMPLEMENTED, with stated limits (see below)
Post-Compromise Security   — LIMITED (see docs/RATCHET_AND_REPLAY.md)
Secure React Frontend      — IMPLEMENTED (accurate trust/E2EE display, CSP, XSS-tested)
Encrypted Local Storage    — IMPLEMENTED (AES-256-GCM, non-extractable keys)
Local Storage Passphrase   — NOT IMPLEMENTED (profile-bound key; see below)
Identity-Key Backup        — NOT IMPLEMENTED (no recovery of any kind)
HTTPS / WSS Transport      — IMPLEMENTED (verified over real TLS)
Origin / CORS Hardening    — IMPLEMENTED (explicit allowlists, no wildcard)
Fail-Closed Production Config — IMPLEMENTED (refuses to start when unsafe)
Secure Logging / Secrets   — IMPLEMENTED (redaction verified against real traffic)
Container Stack            — IMPLEMENTED (non-root, read-only, caps dropped)
Database Least Privilege   — IMPLEMENTED (DML-only runtime role, owns nothing)
Network Segmentation       — IMPLEMENTED (nginx cannot reach the database)
Ciphertext-Only Relay      — RE-VERIFIED after containerization
CI Quality Gates           — IMPLEMENTED (locally verified, not run remotely)
Secret Scanning            — IMPLEMENTED (Gitleaks, full history)
SAST                       — IMPLEMENTED (Semgrep, 348 rules)
Dependency Scanning        — IMPLEMENTED (pip-audit, npm audit, Trivy)
Container Scanning         — IMPLEMENTED (Trivy: image, config, filesystem)
SBOM                       — IMPLEMENTED (CycloneDX 1.6 via Syft)
Artifact Checksums         — IMPLEMENTED (SHA-256, verified incl. tamper case)
Artifact Signing           — NOT IMPLEMENTED (no protected signing identity)
Branch Protection          — MANUAL ACTION REQUIRED
Adversarial Verification   — COMPLETE (internal; 0 Critical, 0 High unresolved)
Release Integrity          — IMPLEMENTED (SHA-256 checksums, verified; SBOM)
Build Provenance           — NOT IMPLEMENTED (no attestation is generated)
Multi-Device               — NOT IMPLEMENTED (one identity per browser profile)
Anonymity / Metadata Privacy — NOT PROVIDED (the relay sees who talks to whom)
Independent Security Audit — NOT PERFORMED
```

Private message content is genuinely end-to-end encrypted: it is encrypted on
the sending device before it reaches the server, the relay routes and queues
ciphertext only, and it is decrypted at the recipient. The relay holds no
message key and has no decryption code path at all.

Since Phase 7 each message is encrypted under **its own** key, derived from an
evolving chain and discarded after use, so compromising one key no longer
exposes a session's history. Fresh X25519 material is mixed into the root key
every time the conversation changes direction.

The forward-secrecy claim is deliberately precise, and its limits are stated
rather than glossed:

* **Logical, not physical, deletion.** Dropping a reference makes key material
  unreachable; JavaScript offers no guarantee the runtime has not already
  copied the bytes. This project never claims memory erasure, and never uses
  the phrase "perfect forward secrecy".
* **Retained skipped keys are still usable.** Keys held for messages that have
  not arrived yet are, by design, readable by anyone who compromises the
  device now. Bounded and documented.
* **Post-compromise security is LIMITED**, not full — healing requires the
  conversation to change direction. See
  [docs/RATCHET_AND_REPLAY.md](docs/RATCHET_AND_REPLAY.md).

Since Phase 9 message history, identity keys, session and ratchet state are
stored **encrypted** on the device, so a reload keeps your identity and your
conversations instead of ending every session. Records are AES-256-GCM under a
per-scope, non-extractable `CryptoKey`; the storage key is generated
independently of every network and message key and never leaves the device.

Two things this deliberately does **not** do, stated here rather than buried:

* **There is no passphrase on local storage**, and no Windows DPAPI or
  Credential Manager involvement — this is a web client with no access to
  either. Anyone who can use the unlocked browser profile can read the history,
  because the application can. At-rest encryption protects the *files* — a
  copied profile, a stolen disk, another OS account, a backup — not an unlocked
  session.
* **There is no identity-key backup and no recovery.** Lose the browser
  profile and the stored history is gone, and a new identity is generated,
  which contacts will correctly see as an identity change.

Deletion removes the application's own records and destroys the key that opens
them, which makes anything left behind undecryptable. It **cannot** guarantee
erasure from the physical disk, from backups, or from snapshots, and this
project does not claim otherwise.

The project has not been independently security audited. Do not use it for
anything real. The complete boundary of what it does **not** protect against
is in [docs/SECURITY_LIMITATIONS.md](docs/SECURITY_LIMITATIONS.md).

---

## Security-first roadmap

| Phase | Scope                                           | Status                                     |
| ----- | ----------------------------------------------- | ------------------------------------------ |
| 0     | Security requirements & threat model            | COMPLETE                                   |
| 1     | Secure development environment & repository     | COMPLETE                                   |
| 2     | WebSocket transport infrastructure              | COMPLETE                                   |
| 3     | Authentication & account security               | COMPLETE                                   |
| 4     | Identity & trust                                | COMPLETE                                   |
| 5     | Authenticated X25519 key agreement              | COMPLETE                                   |
| 6     | End-to-end encryption layer                     | COMPLETE                                   |
| 7     | Forward secrecy, ratcheting & replay protection | COMPLETE                                   |
| 8     | Secure React frontend                           | COMPLETE                                   |
| 9     | Encrypted local storage & key protection        | COMPLETE                                   |
| 10    | Server & deployment hardening                   | COMPLETE                                   |
| 11    | Secure CI/CD & software supply chain            | COMPLETE (workflows not executed remotely) |
| 12    | Adversarial security verification               | COMPLETE (internal, not an audit)          |
| 13    | Public release & disclosure                     | COMPLETE (prepared; publication is manual) |

Phases run strictly in order. A phase is not complete until its checklist and
exit gate both pass, with evidence recorded in `docs/`.

---

## Prerequisites (Windows)

| Tool           | Minimum    | Install                                               |
| -------------- | ---------- | ----------------------------------------------------- |
| Git            | any recent | `winget install --id Git.Git -e`                    |
| Python         | 3.11+      | `winget install --id Python.Python.3.11 -e`         |
| Node.js        | LTS (20+)  | `winget install --id OpenJS.NodeJS.LTS -e`          |
| Gitleaks       | 8.x        | `winget install --id Gitleaks.Gitleaks -e`          |
| OpenSSL        | 3.x        | `winget install --id ShiningLight.OpenSSL.Light -e` |
| Docker Desktop | any recent | `winget install --id Docker.DockerDesktop -e`       |

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

| Purpose          | Backend                           | Frontend (`client/`) |
| ---------------- | --------------------------------- | ---------------------- |
| Lint             | `ruff check .`                  | `npm run lint`       |
| Format check     | `ruff format --check .`         | — (ESLint only)       |
| Type check       | `mypy .`                        | `npm run typecheck`  |
| Tests            | `pytest`                        | `npm run test`       |
| Build            | —                                | `npm run build`      |
| Dependency audit | `pip-audit -r requirements.txt` | `npm audit`          |

Repository-wide:

```powershell
pre-commit run --all-files
gitleaks dir . --config .gitleaks.toml --verbose
```

Run the development servers:

```powershell
cd server
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

```powershell
cd client
npm run dev
```

The backend serves `http://127.0.0.1:8000/health` and the WebSocket transport at
`ws://127.0.0.1:8000/ws/v1`. The frontend runs on `http://localhost:5173`.

---

## Authentication (Phase 3)

```text
Endpoint prefix:    /auth
Docs:               docs/AUTHENTICATION.md
```

Register, sign in, sign out, and delete an account from the frontend's
**Account** panel, or directly:

```powershell
curl -X POST http://127.0.0.1:8000/auth/register -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"correct horse battery staple\"}"
curl -X POST http://127.0.0.1:8000/auth/login    -H "Content-Type: application/json" -d "{\"username\":\"alice\",\"password\":\"correct horse battery staple\"}"
```

Login returns a short-lived access token (15 minutes by default) and sets an
HttpOnly refresh cookie. The access token is held in memory by the frontend —
never in `localStorage`. `POST /auth/logout` revokes the session server-side;
a revoked or expired token is rejected on every subsequent use.

Set `AUTH_SIGNING_SECRET` in `.env` for a stable signing key across restarts
(see `.env.example`); without it, a random per-process secret is generated and
every session is invalidated when the server restarts.

Run the authentication tests:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_auth_password.py tests/test_auth_accounts.py tests/test_auth_sessions.py tests/test_auth_rate_limit.py tests/test_websocket_authz.py
```

### Phase 3 security limitations

```text
Cryptographic identity:      NOT IMPLEMENTED — Phase 4
Identity verification:       NOT IMPLEMENTED — Phase 4
Authenticated key agreement: NOT IMPLEMENTED — Phase 5
End-to-end encryption:       NOT IMPLEMENTED — Phase 6
Forward-secrecy ratchet:     NOT IMPLEMENTED — Phase 7
Replay protection:           NOT IMPLEMENTED — Phase 7
Password reset/recovery:     OUT OF SCOPE FOR V1
```

An authenticated account is **not**, by itself, a cryptographically verified
conversation identity — see Identity & Trust below for what closes that gap,
and what still doesn't. Full authentication limitations, including why live
WebSocket connections are not force-closed on logout, are in
[docs/AUTHENTICATION.md](docs/AUTHENTICATION.md#known-limitations).

---

## Identity & trust (Phase 4)

```text
Endpoint prefix:    /identity
Docs:               docs/IDENTITY_AND_TRUST.md
```

Sign in, then open the **My Security Identity** panel and click
**Generate Identity** to create a local Ed25519 key pair and register its
public key. The private key lives in browser memory only — it is lost on
reload, and generating a new one for the same device is treated as a
legitimate key rotation, not an error.

Use the **Contact Security** panel to look up another account by username,
view its fingerprint and safety code, and — after comparing that code with
the contact out of band (in person, a trusted call, another already-verified
channel) — click **mark verified**. If that contact's key ever changes
afterward, the next lookup replaces the display with a non-dismissible
**Security identity changed** warning and clears the verified status; only a
fresh, explicit re-verification restores it. A never-before-seen contact
always starts `UNVERIFIED` — receiving a key from the server is never treated
as verification.

Trust is entirely local to the browser that recorded it: one user verifying a
contact has no effect on what any other user sees.

Run the identity/trust tests:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_identity_crypto.py tests/test_identity_api.py tests/test_cors.py
```

```powershell
cd client
npm run test -- crypto trustStore keyStore IdentityPanel ContactSecurity
```

### Phase 4 security limitations

```text
Authenticated key agreement (X25519): IMPLEMENTED — Phase 5, see below
End-to-end encryption:                NOT IMPLEMENTED — Phase 6
Forward-secrecy ratchet:               NOT IMPLEMENTED — Phase 7
Encrypted local key storage:           NOT IMPLEMENTED — Phase 9
QR-code verification:                  NOT IMPLEMENTED (optional, not built)
Multi-device management UI:            NOT IMPLEMENTED (data model allows it; v1 client manages one device)
First-contact substitution:            UNDEFENDED (inherent Trust-On-First-Use limitation)
```

A verified identity is **not** encryption. Full limitations, including the
Trust-On-First-Use exposure and why the private key does not survive a page
reload, are in
[docs/IDENTITY_AND_TRUST.md](docs/IDENTITY_AND_TRUST.md#known-limitations).

---

## Key agreement (Phase 5)

```text
Endpoint prefix:    /keyagreement
Docs:               docs/KEY_AGREEMENT.md
```

After generating an identity, click **Publish Key-Agreement Prekey** in the
**My Security Identity** panel — this creates a local X25519 key pair (the
private key stays in memory only, exactly like the identity key) and
publishes its signed public half.

To start a session, use the **Key Agreement** panel: enter a contact's
username and click **Establish Secure Session**. This fetches the contact's
identity and prekey, verifies the prekey's signature against that identity,
checks trust state (blocking a revoked or changed identity — re-verify via
**Contact Security** first), generates a fresh ephemeral X25519 key,
signs a handshake-initiate message with your identity key, and derives
initial session material via X25519 Diffie-Hellman + HKDF-SHA-256 — all
client-side. The contact then clicks **Check for Pending Key-Agreement
Requests** to fetch, verify, and complete the handshake on her side,
deriving the identical session material independently.

Run the key-agreement tests:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_keyagreement_crypto.py tests/test_keyagreement_api.py
```

```powershell
cd client
npm run test -- x25519 hkdf transcript prekeyStore sessionStore handshake KeyAgreementPanel
```

### Phase 5 security limitations

```text
End-to-end message encryption:  NOT IMPLEMENTED — Phase 6
Forward-secrecy ratchet:         NOT IMPLEMENTED — Phase 7
Explicit key confirmation:       NOT IMPLEMENTED (deliberate; see docs/KEY_AGREEMENT.md)
Automatic/real-time delivery:    NOT IMPLEMENTED (pending requests are checked manually)
Multi-use prekeys, not one-time: inherited from Phase 4, unchanged
```

Shared session/root material is **not** encryption — it is the seed a later
phase's message-key derivation will consume. Full limitations, including why
the initiator's local "established" state is provisional until the
responder completes her side, are in
[docs/KEY_AGREEMENT.md](docs/KEY_AGREEMENT.md#known-limitations).

---

## End-to-end encryption (Phase 6)

```text
Message type:   message.encrypted
AEAD:           AES-256-GCM via the Web Crypto API
Docs:           docs/E2EE.md
```

Once you have a key-agreement session with a contact (above), use the
**Encrypted Messaging** panel: click **Connect**, enter the contact's
username and your message, then **Send encrypted message**. The message is
encrypted on your device before it is transmitted; the relay receives
ciphertext, a nonce, and routing metadata, and nothing else. The recipient's
panel decrypts it locally and shows it under *Decrypted messages*.

Without a session, nothing is sent at all — the panel reports that a secure
session is required. There is no plaintext fallback anywhere in the send
path.

Run the encryption tests:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_websocket_e2ee.py tests/test_e2ee_plaintext_exposure.py
```

```powershell
cd client
npm run test -- e2ee
```

### Verifying plaintext never reaches the relay

`tests/test_e2ee_plaintext_exposure.py` is the controlled verification (§48):
it exchanges a real AEAD-encrypted message between two real WebSocket clients
through a real uvicorn server, captures every frame crossing the relay
boundary, and asserts a distinctive plaintext marker appears in none of the
captured traffic, the server database, or the server logs. Run it directly:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_e2ee_plaintext_exposure.py -v
```

### Phase 6 security limitations, as they stand after Phase 7

```text
Forward secrecy / ratchet:        IMPLEMENTED — Phase 7 (with stated limits)
Cryptographic replay protection:  IMPLEMENTED — Phase 7
Message-order authentication:     IMPLEMENTED — Phase 7 (counters in the AAD)
Encrypted local history:          NOT IMPLEMENTED — Phase 9
Metadata protection:              OUT OF SCOPE (who/when is visible to the relay)
Ratchet header privacy:           NOT IMPLEMENTED (counters/keys visible to relay)
Transport timestamp:              not authenticated (see docs/E2EE.md)
```

Full limitations are in [docs/E2EE.md](docs/E2EE.md#known-limitations).

---

## Ratcheting & replay protection (Phase 7)

```text
Design:      Double Ratchet (Perrin & Marlinspike, revision 1, 2016-11-20)
Root KDF:    HKDF-SHA-256, salt = root key, IKM = fresh X25519 DH output
Chain KDF:   HMAC-SHA-256(chain key, 0x01 / 0x02)
MAX_SKIP:    1000
Docs:        docs/RATCHET_AND_REPLAY.md
```

Every message now gets its own key, derived from an evolving chain and
discarded after use. Each time the conversation changes direction, a fresh
X25519 Diffie-Hellman result is mixed into the root key.

**What you will notice using it:**

* The side that **completed** a handshake as responder cannot send until the
  initiator's first message arrives. That is a property of the protocol, not a
  bug — the responder does not know the initiator's ratchet key until then,
  so there is no sending chain to derive. The panel says so, and the error is
  `RATCHET_NOT_READY_TO_SEND`.
* A message that is delivered twice is rejected the second time with
  `RATCHET_REPLAY_DETECTED`, and no plaintext is shown.
* Messages that arrive out of order still decrypt, as long as the gap is
  within `MAX_SKIP` (1000). Beyond that, `RATCHET_MAX_SKIP_EXCEEDED`.
* Reloading the page **ends every session**. Ratchet state is held in memory
  only; re-run key agreement to continue. Encrypted persistence is Phase 9.

Run the ratchet and replay tests:

```powershell
cd client
npm run test -- ratchet
```

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_websocket_ratchet.py -v
```

### Phase 7 security limitations

```text
Post-compromise security:     LIMITED — healing needs a direction change
Physical memory erasure:      NOT GUARANTEED — managed runtime, logical deletion only
Retained skipped keys:        readable by a present-time device compromise, by design
Header encryption:            NOT IMPLEMENTED — relay sees ratchet keys and counters
One-time prekeys:             NOT IMPLEMENTED — first message has weaker FS until the first DH ratchet
Persistent ratchet state:     NOT IMPLEMENTED — Phase 9
```

Each of these is explained, with the reasoning, in
[docs/RATCHET_AND_REPLAY.md](docs/RATCHET_AND_REPLAY.md#limitations).

---

## Secure frontend (Phase 8)

```text
Stack:  React 19 + TypeScript, Vite
Tests:  Vitest (component/unit) + Playwright (browser)
Docs:   docs/SECURE_FRONTEND.md
```

Run the client:

```powershell
cd client
npm install
npm run dev
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173). Use `127.0.0.1`, not `localhost` — the API
is served from `127.0.0.1:8000`, and browsers treat the two hostnames as
different sites, so a `localhost` page will not be sent the `SameSite` refresh
cookie and your session will not survive a reload.

Run the tests:

```powershell
cd client
npm run test
```

```powershell
cd client
npx playwright test
```

Playwright starts the backend, the dev server, and a production preview build
itself, so the browser suite runs from a clean checkout with one command.

### What the interface does and does not claim

The frontend reports **five separate security properties** rather than one
"secure" badge, because they are genuinely independent:

```text
Connection            Connected / Disconnected / Authentication required
Identity              Not verified / Verified / Identity changed / Revoked
Key agreement         None / Establishing / Established / Failed
End-to-end encryption Unavailable / Active (AES-256-GCM) / Failed
Message ratchet       Unavailable / Active (per-message keys) / Reset required
```

An encrypted conversation with someone whose fingerprint you have **not**
checked is shown as *"Not verified · encrypted"* — never as "Verified" and
never as "Secure". Encryption proves nobody in the middle can read the message;
it does not prove who is on the other end.

If a contact's identity key changes, a **persistent warning** appears in the
conversation, any previous verification is dropped, sending is blocked, and
there is a direct route to re-verification. There is deliberately no control
that re-trusts an identity without verifying it.

### Verifying a contact

Open a conversation, choose **Security details**, read the safety code to your
contact over a channel you already trust — in person, or a call where you
recognise their voice — then tick the confirmation and choose **Mark as
verified**. Do not compare the code inside the app: if this connection is
compromised, so is the comparison.

### Phase 8 security limitations

```text
Encrypted local storage:  IMPLEMENTED in Phase 9
Presence:                 NOT IMPLEMENTED — no backend support
Typing indicators:        NOT IMPLEMENTED — no backend support
Attachments:              OUT OF SCOPE
CSP frame-ancestors:      NOT ENFORCED from a <meta> policy — needs the HTTP
                          header, which is Phase 10
Read receipts:            do not exist; no message is ever labelled "read"
WCAG conformance:         NOT CLAIMED (no independent assessment)
```

Reloading the page used to lose every key, generating a new cryptographic
identity that contacts correctly read as an identity change. Phase 9 fixed
that: keys and history are now restored from encrypted local storage. Full
detail in [docs/SECURE_FRONTEND.md](docs/SECURE_FRONTEND.md#known-limitations).

---

## Encrypted local storage (Phase 9)

Everything persistent lives in one IndexedDB database, `ecapp.secure.v1`,
encrypted with AES-256-GCM.

```text
Storage key:        AES-256-GCM, non-extractable CryptoKey, one per scope
                    ('app', and 'conversation:<peer>')
Key separation:     structural — storage/keyring.ts imports no identity,
                    session, message or ratchet key module at all
Record format:      nonce + ciphertext + metadata. There is no plaintext
                    field on the type, optional or otherwise
AAD:                binds algorithm, scope, collection, record id,
                    conversation id, and both version numbers
Nonces:             fresh 12-byte CSPRNG per write, including on update
Search:             decrypted in memory only; no index is ever written
Deletion:           records removed, then the scope key destroyed
```

**Non-extractable keys are the core of it.** A `CryptoKey` created with
`extractable: false` can be stored in IndexedDB and used to encrypt and
decrypt, but its raw bytes cannot be read back — not by this application, not
by injected script, and not by anyone reading the database file off the disk.
Someone who copies the profile directory gets ciphertext and a key handle that
is useless anywhere else.

### Export

Encrypted export is the default and takes one step: a passphrase (12 characters
minimum), then download. The file uses PBKDF2-SHA-256 at 600,000 iterations
with a fresh salt, so it can be opened on another device — the browser's own
storage key is deliberately not used, since a file encrypted under a
profile-bound key could never be opened elsewhere.

Plaintext export takes three: a warning shown before the control, an explicit
checkbox, then the button. The acknowledgement is a required argument at the
API level too, so the unsafe path cannot be taken by an accidental call any
more than by an accidental click. Nothing silently converts an encrypted backup
to plaintext.

Import is deliberately not implemented — accepting files back into the
encrypted store needs its own threat model.

### Phase 9 security limitations

```text
Passphrase on local storage:  NOT IMPLEMENTED — the key is bound to the
                              browser profile, not to a passphrase
Windows DPAPI / Credential
  Manager:                    NOT USED — this is a web client with no access
Identity-key backup:          NOT IMPLEMENTED — no export, escrow or recovery
Local-key recovery:           NONE — a lost key means lost history, and the
                              server cannot help because it never had it
Import of exported files:     NOT IMPLEMENTED
Physical erasure:             NOT CLAIMED — SSD wear levelling, backups,
                              snapshots and browser-managed pages are all
                              outside what this layer can guarantee
Forward secrecy:              NARROWED — persisting ratchet state means a
                              compromised chain also exposes future messages
                              until the next DH ratchet step. Past messages
                              remain protected
```

Full detail, including the threat table and the reasoning behind each
trade-off, in
[docs/LOCAL_STORAGE_AND_KEY_PROTECTION.md](docs/LOCAL_STORAGE_AND_KEY_PROTECTION.md).

---

## Production-like deployment (Phase 10)

> Verified against the running stack: **66 deployment checks**
> (`deploy/scripts/verify-stack.sh`), **3 end-to-end browser tests** driving a
> real encrypted exchange through HTTPS/WSS and the reverse proxy, and **29
> transport checks** of the application without containers. Recorded output is
> in [docs/PHASE_10_EVIDENCE.md](docs/PHASE_10_EVIDENCE.md) and
> `docs/evidence/phase10-*`.

### Architecture

```text
Browser --HTTPS/WSS--> nginx (uid 101) --internal--> backend (uid 10001) --data--> postgres
                       80, 443 only          no published port        no published port
```

Three services and three networks. There is deliberately **no Redis**: it would
exist to share state between workers, and this build runs a single worker
because WebSocket connection state and the offline queue are per-process.
Adding it would introduce a service handling ciphertext and a credential to
protect, for no functional gain.

### Running it

Prerequisites: Docker Desktop with a working Linux engine.

```powershell
# 1. Development TLS certificate (self-signed; NOT for production)
.\deploy\scripts\generate-dev-certs.ps1

# 2. Secrets - copy the template and replace EVERY placeholder
Copy-Item deploy\.env.example deploy\.env
#    Generate each value with:
#    python -c "import secrets; print(secrets.token_urlsafe(64))"

# 3. Build and start
docker compose -f deploy/docker-compose.yml up --build -d

# 4. Create the schema (deliberate, separate, privileged step)
docker compose -f deploy/docker-compose.yml --profile migrate run --rm migrate
```

Then:

```powershell
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f
docker compose -f deploy/docker-compose.yml down
```

| URL                          | What                                                 |
| ---------------------------- | ---------------------------------------------------- |
| `https://localhost`        | The application                                      |
| `wss://localhost/ws/v1`    | Authenticated messaging                              |
| `https://localhost/health` | Liveness —`{"status":"ok"}`                       |
| `https://localhost/ready`  | Readiness — 503 until migrated                      |
| `http://localhost`         | 301 to HTTPS (`/ws` returns 426, never redirected) |

**Your browser will warn about the certificate.** That is correct: it is
self-signed, so nothing vouches for it. The encryption is real; only the trust
chain is absent. `curl` needs `-k`.

### Required environment

Every one of these must be set, and the application **refuses to start** if any
is missing, a placeholder, or unsafe:

| Variable                        | Notes                                                      |
| ------------------------------- | ---------------------------------------------------------- |
| `PUBLIC_ORIGIN`               | Must be`https://`. Baked into the frontend at build time |
| `AUTH_SIGNING_SECRET`         | ≥ 32 chars, not a placeholder                             |
| `POSTGRES_SUPERUSER_PASSWORD` | Init script only                                           |
| `POSTGRES_MIGRATE_PASSWORD`   | Migration job only                                         |
| `POSTGRES_APP_PASSWORD`       | The only one in the running backend's environment          |

**No real secret belongs in the repository.** `deploy/.env` is git-ignored;
only `deploy/.env.example`, which contains placeholders, is committed. TLS
private keys are git-ignored and this is verified with `git check-ignore`.

### Verifying the deployment

```powershell
# The running stack: container users, capabilities, network reachability,
# TLS versions, headers, database privileges, image contents, log contents,
# and the ciphertext-only guarantee. 66 checks.
bash deploy/scripts/verify-stack.sh

# A real encrypted exchange through HTTPS/WSS and the proxy. Run this BEFORE
# verify-stack.sh, which searches for the marker it puts through the relay.
cd client; npx playwright test --config playwright.deploy.config.ts

# The application over real TLS, without containers. 29 checks.
python deploy\scripts\verify-transport.py
```

### Phase 10 security limitations

```text
Production certificate:   NOT PROVIDED - the dev pair is self-signed
Secret management:        .env only; not a production architecture
HSTS:                     off by default (harmful on a localhost origin)
Backups:                  NOT IMPLEMENTED
Migration tool:           create_all only; no ALTER, no data migration
Horizontal scaling:       NOT SUPPORTED - single worker by design
WAF / IDS / DDoS:         NOT IMPLEMENTED
Independent audit:        NOT PERFORMED
```

Full detail in
[docs/DEPLOYMENT_HARDENING.md](docs/DEPLOYMENT_HARDENING.md).

---

## CI/CD and supply chain (Phase 11)

> **The workflows have never run on GitHub Actions.** Every check in them has
> been executed locally against this repository with recorded output, and the
> YAML is validated by actionlint — but no hosted runner has executed them.
> That distinction is kept explicit in
> [docs/PHASE_11_EVIDENCE.md](docs/PHASE_11_EVIDENCE.md) §2.

### Workflows

| File                       | Trigger              | Checks                                                                                                                                                         |
| -------------------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ci.yml`                 | push, PR             | Backend (Ruff, mypy, pytest, pip-audit) · Frontend (ESLint, tsc, Vitest, build, npm audit) · Playwright security journeys · pre-commit · deployment config |
| `security.yml`           | push, PR, weekly     | Gitleaks over full history · Semgrep SAST · dependency review                                                                                                |
| `container-security.yml` | push, PR, weekly     | Image build · non-root assertion · layer secret inspection · Trivy image/config/filesystem                                                                  |
| `release-security.yml`   | **tag `v*`** | Re-runs every mandatory gate, then SBOM, checksums, artifacts                                                                                                  |

All four declare `permissions: contents: read`. **No workflow requests any
write permission, and none references a repository secret.** The release
workflow cannot be triggered by a pull request at all — its trigger is a tag
push, which requires write access — so untrusted code cannot reach it.

### Running the same checks locally

Everything CI does, you can do. The security tools run as pinned containers,
so there is nothing to install beyond Docker:

```powershell
# Quality gates — see CONTRIBUTING.md for the full list
cd server;  ruff check .; mypy .; pytest; pip-audit -r requirements.txt
cd ..\client; npm run lint; npm run test; npm run build; npx playwright test

# Repository
pre-commit run --all-files
gitleaks dir . --config .gitleaks.toml
bash deploy/scripts/check-deployment-safety.sh

# SAST, workflow lint, container scan, SBOM (Docker)
docker run --rm -v "${PWD}:/src:ro" -w /src semgrep/semgrep:1.101.0 semgrep scan --config p/security-audit --error
docker run --rm -v "${PWD}:/repo:ro" -w /repo rhysd/actionlint:1.7.7
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.58.2 image --severity CRITICAL,HIGH --ignore-unfixed encrypted-chat-backend:latest
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock anchore/syft:v1.19.0 docker:encrypted-chat-backend:latest -o cyclonedx-json
```

### Dependencies

Backend dependencies are split so the container image does not ship the test
toolchain:

| File                            | Contents                            | In the image |
| ------------------------------- | ----------------------------------- | ------------ |
| `server/requirements.txt`     | Runtime only (33 packages)          | Yes          |
| `server/requirements-dev.txt` | pytest, mypy, ruff, pre-commit (83) | **No** |

That split removed `pytest`, `mypy`, `pre-commit`, `virtualenv` and `nodeenv`
from the runtime image — tools that would have restored the ability to fetch
and execute code inside a container from which `pip` was deliberately removed
in Phase 10.

### Release integrity

Release artifacts carry SHA-256 checksums, generated and verified in the same
job, plus a CycloneDX SBOM covering both images and the source tree.

**Checksums are integrity, not authenticity.** They detect corruption and
accidental substitution; they do not prove origin, because anyone who can
replace an artifact can replace the checksum file beside it. **Artifact signing
is not implemented** — there is no protected signing identity for this project,
and a signing step that has never run is not something this project will claim.

### Phase 11 security limitations

```text
Remote CI execution:      NOT PERFORMED - no hosted runner has run these
Branch protection:        MANUAL ACTION REQUIRED - see docs/CI_CD_AND_SUPPLY_CHAIN.md §11
Artifact signing:         NOT IMPLEMENTED - no protected signing identity
Build provenance:         NOT IMPLEMENTED
Action pinning:           tags, not commit digests
Reproducibility:          dependency-reproducible, NOT bit-for-bit
SAST scope:               syntactic patterns; NOT cryptographic protocol review
Scanner coverage:         known advisories only; a malicious package with no
                          advisory filed passes every scanner here
```

**Until branch protection is enabled, the gates report failures but nothing
prevents merging past them.**

Full detail in
[docs/CI_CD_AND_SUPPLY_CHAIN.md](docs/CI_CD_AND_SUPPLY_CHAIN.md).

---

## WebSocket transport (Phase 2, authenticated since Phase 3)

```text
Endpoint:          ws://127.0.0.1:8000/ws/v1
Protocol version:  1
Protocol document: docs/WEBSOCKET_PROTOCOL.md
```

The endpoint takes no query parameters. A connection starts unauthenticated
and must send an `auth.authenticate` message carrying a valid access token
(obtained from `/auth/login`) before it can send or receive anything else.

**Origin requirement.** The server enforces an Origin allowlist on the
WebSocket upgrade; a disallowed Origin is refused with HTTP 403. Development
defaults are `http://localhost:5173` and `http://127.0.0.1:5173`, so the Vite
dev server works out of the box. Override with `WS_ALLOWED_ORIGINS`
(comma-separated). A literal `*` is discarded, never honoured. Non-browser
clients that send no Origin header are allowed in development.

Sign in via the **Account** panel first, then use the **Development
Transport Test** panel below it to connect (it authenticates automatically
using the signed-in session), send a test message, and watch
acknowledgements. Sign in as two different accounts in two browser tabs to
see direct routing.

Run the transport tests:

```powershell
cd server
.venv\Scripts\Activate.ps1
pytest tests/test_websocket_connection.py tests/test_websocket_routing.py tests/test_websocket_schema.py tests/test_websocket_authz.py tests/test_websocket_origin.py tests/test_websocket_limits.py tests/test_websocket_lifecycle.py tests/test_websocket_logging.py tests/test_websocket_multiclient.py
```

Or simply `pytest` for the whole suite.

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
├── client/              React + TypeScript + Vite frontend
│   └── src/
│       ├── auth/         Account panel and authentication API client
│       ├── identity/     Ed25519 identity, trust store, verification UI
│       ├── keyAgreement/ X25519 key agreement, HKDF, session establishment
│       ├── e2ee/         AES-256-GCM message encryption/decryption
│       └── transport/    Development transport test client
├── server/              FastAPI backend
│   ├── app/             Application package
│   │   ├── auth/         Accounts, sessions, tokens, rate limiting
│   │   ├── identity/     Ed25519 identity, signed prekeys, revocation
│   │   ├── keyagreement/ X25519 handshake session bookkeeping (public data only)
│   │   └── websocket/    Transport layer (authenticated since Phase 3)
│   ├── tests/           Backend tests
│   ├── requirements.in  Direct dependencies (edit this)
│   ├── requirements.txt Compiled pinned lock (generated)
│   └── pyproject.toml   Ruff / mypy / pytest configuration
├── protocol/            Reserved: shared protocol definitions
├── tests/               Reserved: cross-cutting/integration tests (Phase 2+)
├── deploy/              Reserved: deployment configuration (Phase 10)
├── scripts/             Developer utility scripts
├── docs/                Security documentation and phase evidence
│   ├── THREAT_MODEL.md
│   ├── SECURITY_REQUIREMENTS.md
│   ├── DATA_FLOW_DIAGRAM.md
│   ├── ASVS_MAPPING.md
│   ├── SECURITY_ASSUMPTIONS.md
│   ├── WEBSOCKET_PROTOCOL.md
│   ├── AUTHENTICATION.md
│   ├── PHASE_0_EVIDENCE.md
│   ├── PHASE_1_EVIDENCE.md
│   ├── PHASE_2_EVIDENCE.md
│   ├── PHASE_3_EVIDENCE.md
│   ├── PHASE_4_EVIDENCE.md
│   ├── PHASE_5_EVIDENCE.md
│   ├── PHASE_6_EVIDENCE.md
│   ├── IDENTITY_AND_TRUST.md
│   ├── KEY_AGREEMENT.md
│   └── E2EE.md
└── .github/workflows/   CI
```

`protocol/`, `tests/`, and `deploy/` are intentionally empty placeholders —
populating them is the job of later phases. The protocol lives in
`server/app/websocket/` (documented in
[docs/WEBSOCKET_PROTOCOL.md](docs/WEBSOCKET_PROTOCOL.md)); authentication lives
in `server/app/auth/` (documented in
[docs/AUTHENTICATION.md](docs/AUTHENTICATION.md)); cryptographic identity and
trust live in `server/app/identity/` and `client/src/identity/` (documented in
[docs/IDENTITY_AND_TRUST.md](docs/IDENTITY_AND_TRUST.md)); authenticated key
agreement lives in `server/app/keyagreement/` and `client/src/keyAgreement/`
(documented in [docs/KEY_AGREEMENT.md](docs/KEY_AGREEMENT.md)).

---

## Security documentation

- [Threat model](docs/THREAT_MODEL.md) — assets, actors, trust boundaries, 20 threat scenarios
- [Security requirements](docs/SECURITY_REQUIREMENTS.md) — 105 requirements with stable IDs
- [Data flow diagram](docs/DATA_FLOW_DIAGRAM.md)
- [ASVS 5.0.0 mapping](docs/ASVS_MAPPING.md)
- [Security assumptions &amp; invariants](docs/SECURITY_ASSUMPTIONS.md)
- [WebSocket protocol](docs/WEBSOCKET_PROTOCOL.md) — envelope, error codes, limits, authentication, security limitations
- [Authentication](docs/AUTHENTICATION.md) — account model, Argon2id, sessions, revocation, brute-force controls
- [Identity &amp; trust](docs/IDENTITY_AND_TRUST.md) — Ed25519 identity, fingerprints, verification, identity-change detection, signed prekeys, revocation
- [Key agreement](docs/KEY_AGREEMENT.md) — authenticated X25519 handshake, canonical transcript, HKDF-SHA-256, replay/state protection
- [End-to-end encryption](docs/E2EE.md) — AES-256-GCM, AAD binding, nonce strategy, ciphertext-only relay, plaintext lifecycle
- [Ratcheting &amp; replay protection](docs/RATCHET_AND_REPLAY.md) — Double Ratchet, per-message keys, replay window, forward-secrecy limits
- [Secure frontend](docs/SECURE_FRONTEND.md) — CSP, XSS resistance, security-state model, storage table
- [Local storage &amp; key protection](docs/LOCAL_STORAGE_AND_KEY_PROTECTION.md) — at-rest encryption, non-extractable keys, key separation, deletion, export, recovery policy
- [Deployment hardening](docs/DEPLOYMENT_HARDENING.md) — architecture, TLS, Origin/CORS, resource limits, container and database least privilege, secrets, logging, and what is not verified
- [CI/CD and supply chain](docs/CI_CD_AND_SUPPLY_CHAIN.md) — pipeline, permissions, secret scanning, SAST, dependency and container scanning, SBOM, release integrity, branch protection, and known limitations
- [Security limitations](docs/SECURITY_LIMITATIONS.md) — **what this does not protect against**; read this one
- [Phase 12 findings](docs/PHASE_12_FINDINGS.md) · [Phase 12 evidence](docs/PHASE_12_EVIDENCE.md) — adversarial verification, including the tests that were themselves wrong
- [Incident response](docs/INCIDENT_RESPONSE.md) — triage, containment, per-key rotation procedures
- [Release process](docs/RELEASE_PROCESS.md) · [Release security checklist](docs/RELEASE_SECURITY_CHECKLIST.md)
- [Update and upgrade](docs/UPDATE_AND_UPGRADE.md) — migration, verification, and rollback limits
- [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

Phase 0 documentation is **authoritative** for all future design decisions.

---

## Verifying a release download

Release artifacts carry SHA-256 checksums. Check what you downloaded:

```powershell
Get-FileHash .\encrypted-chat-app-0.1.0-source.zip -Algorithm SHA256
# compare the hash against SHA256SUMS from the release
```

> **Checksums are integrity, not authenticity.** They detect corruption and
> accidental substitution. They do **not** prove where an artifact came from:
> anyone able to replace an artifact can replace the checksum file beside it.
> **Artifact signing is not implemented** — no protected signing identity
> exists for this project, and no throwaway key has been generated to make the
> release look signed.

Each release also ships a CycloneDX 1.6 SBOM listing every component in the
build. See [docs/RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md).

---

## Reporting a vulnerability

**Report privately — do not open a public issue for a security problem.**
Use GitHub private vulnerability reporting on this repository
(*Security → Report a vulnerability*).

Full policy, including scope, safe harbour, supported versions and what to put
in a report: [SECURITY.md](SECURITY.md).

Reports that a security *claim* in this documentation is stronger than the
evidence behind it are in scope and are genuinely welcome.

---

## License

```text
LICENSE DECISION: REQUIRED
STATUS: UNRESOLVED — MANUAL ACTION REQUIRED (project owner)
```

