# Data Flow Diagram — Encrypted Chat Application

**Status:** Conceptual / Phase 0 documentation only. No implementation exists.
These diagrams describe the intended v1 architecture referenced by
[THREAT_MODEL.md](THREAT_MODEL.md) and [SECURITY_REQUIREMENTS.md](SECURITY_REQUIREMENTS.md).

---

## 1. System Data Flow with Trust Boundaries

```mermaid
flowchart TB
    subgraph ClientA["User A Client (trusted endpoint)"]
        A_PT["Plaintext message"]
        A_ID["Identity private key"]
        A_SESS["Session / ratchet key state"]
    end

    subgraph NetBoundary[" "]
        direction TB
        NB["NETWORK TRUST BOUNDARY<br/>(WSS/TLS transport, E2EE ciphertext)"]
    end

    subgraph Relay["Relay / Backend (untrusted for plaintext)"]
        R_AUTH["Authentication service"]
        R_ROUTE["WebSocket routing"]
        R_KEYS["Public identity / prekey distribution"]
        R_QUEUE["Offline ciphertext queue"]
        R_ABUSE["Abuse / rate-limit controls"]
        R_NOTE["MUST NOT decrypt private messages"]
    end

    subgraph DB["Database (untrusted for plaintext)"]
        D_ACC["Accounts"]
        D_PUB["Public keys"]
        D_CT["Ciphertext"]
        D_META["Delivery metadata"]
    end

    subgraph ClientB["User B Client (trusted endpoint)"]
        B_DEC["Decryption endpoint"]
        B_ID["Identity private key"]
        B_SESS["Session / ratchet key state"]
    end

    A_PT -->|"encrypt locally (E2EE-001)"| NB
    A_ID -.->|"never transmitted (CRYPTO-002)"| NB
    NB -->|"ciphertext + auth metadata"| Relay
    Relay --> DB
    Relay -->|"ciphertext delivery"| NB2["NETWORK TRUST BOUNDARY"]
    NB2 --> ClientB
    B_DEC -->|"decrypt locally (E2EE-003)"| B_DEC

    style NB fill:#4a1a1a,stroke:#c0392b,color:#fff
    style NB2 fill:#4a1a1a,stroke:#c0392b,color:#fff
    style R_NOTE fill:#4a1a1a,stroke:#c0392b,color:#fff
    style A_ID fill:#1a3a1a,stroke:#27ae60,color:#fff
    style B_ID fill:#1a3a1a,stroke:#27ae60,color:#fff
```

**Legend:**
- Red boundary = untrusted network / relay trust boundary (ciphertext only crosses here).
- Green nodes = private key material that must never leave the endpoint.
- Dotted arrow = data flow that is explicitly forbidden (private key transmission).

---

## 2. Component / Data-Type Detail

```mermaid
flowchart LR
    subgraph Client["Client Endpoint"]
        direction TB
        PT[Plaintext]:::plain
        IDK[Identity Private Key]:::secret
        EPK[Ephemeral Private Keys]:::secret
        RK[Root/Chain/Message Keys]:::secret
        PUBID[Identity Public Key]:::pub
        PUBPRE[Signed Prekeys - public]:::pub
    end

    subgraph Wire["Wire / Transport"]
        direction TB
        CT[AEAD Ciphertext + Auth Tag]:::cipher
        ENV[Envelope Metadata<br/>sender-bound, timestamp, sequence]:::meta
        PUBFLOW[Public keys in transit]:::pub
    end

    subgraph Server["Relay + Database"]
        direction TB
        SRV_CT[Stored Ciphertext]:::cipher
        SRV_META[Routing / Delivery Metadata]:::meta
        SRV_PUB[Public Key Directory]:::pub
        SRV_AUTH[Password Hashes / Tokens]:::authdata
    end

    PT -->|encrypt, never leaves endpoint as plaintext| CT
    IDK -.->|NEVER transmitted| Wire
    EPK -.->|NEVER transmitted| Wire
    RK -.->|NEVER transmitted| Wire
    PUBID --> PUBFLOW --> SRV_PUB
    PUBPRE --> PUBFLOW
    CT --> SRV_CT
    ENV --> SRV_META

    classDef plain fill:#4a1a1a,stroke:#c0392b,color:#fff
    classDef secret fill:#1a3a1a,stroke:#27ae60,color:#fff
    classDef cipher fill:#1a2a4a,stroke:#2980b9,color:#fff
    classDef pub fill:#3a3a1a,stroke:#f1c40f,color:#fff
    classDef meta fill:#3a2a1a,stroke:#e67e22,color:#fff
    classDef authdata fill:#3a1a3a,stroke:#8e44ad,color:#fff
```

**Legend:** red = plaintext (endpoint-only), green = private key material
(endpoint-only, never transmitted), blue = ciphertext, yellow = public key
material (safe to distribute), orange = metadata (unavoidably visible to relay,
see `THREAT_MODEL.md §13`), purple = authentication data at rest (hashed/derived,
never reversible plaintext).

---

## 3. Conceptual Authenticated Key-Agreement Flow (documentation only)

This sequence illustrates *what* must eventually be authenticated and *where*
trust is established — it is not an implementation and defines no wire format.
Actual design occurs in Phase 5.

```mermaid
sequenceDiagram
    participant A as User A Client
    participant S as Relay (untrusted for plaintext)
    participant B as User B Client

    Note over A,B: Long-term identity keys (Ed25519) established at registration (Phase 3/4)

    B->>S: Publish signed prekey bundle (public only)
    A->>S: Request B's prekey bundle
    S->>A: Deliver B's signed prekey bundle
    Note over A: Verify prekey signature against B's known identity key (IDENTITY-003)
    A->>A: Perform X25519 key agreement, derive session key via HKDF (CRYPTO-003, CRYPTO-004)
    A->>S: Send initial authenticated ciphertext message
    S->>B: Relay ciphertext (S cannot decrypt, E2EE-002)
    B->>B: Verify + derive matching session key, decrypt (E2EE-003)
    Note over A,B: Ratchet state advances per message (Phase 7)
```

---

## 4. Attacker Positions (overlay)

```mermaid
flowchart TB
    A["User A Client"] --> NET1["Network segment 1"]
    NET1 --> R["Relay / Backend"]
    R --> DBX["Database"]
    R --> NET2["Network segment 2"]
    NET2 --> B["User B Client"]

    ATT_A["Threat Actor I<br/>Local-device attacker"] -.-> A
    ATT_B["Threat Actor A/B<br/>Passive observer / MITM"] -.-> NET1
    ATT_C["Threat Actor G<br/>Malicious web origin"] -.-> R
    ATT_D["Threat Actor D<br/>Compromised relay"] -.-> R
    ATT_E["Threat Actor E<br/>Compromised database"] -.-> DBX
    ATT_F["Threat Actor A/B<br/>Passive observer / MITM"] -.-> NET2
    ATT_G["Threat Actor I<br/>Local-device attacker"] -.-> B
    ATT_H["Threat Actor H<br/>Supply-chain attacker"] -.-> A
    ATT_H2["Threat Actor H<br/>Supply-chain attacker"] -.-> R

    style ATT_A fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_B fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_C fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_D fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_E fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_F fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_G fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_H fill:#4a1a1a,stroke:#c0392b,color:#fff
    style ATT_H2 fill:#4a1a1a,stroke:#c0392b,color:#fff
```

Threat actor letters correspond to `THREAT_MODEL.md §7`.

---

## 5. Notes

- These diagrams are Mermaid (text-based, version-controlled) as required by the
  master plan. A draw.io-compatible export was not produced in Phase 0 — the
  Mermaid source above is the authoritative, reviewable artifact; a draw.io
  export can be generated later if a specific reviewer requires it, without
  changing this document's authority.
- No diagram here should be read as describing an implemented system. They
  describe the target architecture that later phases must build toward and
  that Phase 12 must verify against.
