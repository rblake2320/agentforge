# AgentForge

> Forge permanent cryptographic identities for AI agents.

## What is AgentForge?

AgentForge is an open platform for issuing and managing W3C DID-based (Decentralized Identifier) cryptographic identities for AI agents. Every agent receives a permanent `did:agentforge:` URI backed by an Ed25519 key pair, a signed Verifiable Credential, and an X.509 certificate — giving it an unforgeable, auditable identity that travels with it regardless of which runtime, cloud provider, or device hosts it. The identity layer is completely independent of any single vendor's authentication system, making agents first-class participants in multi-provider workflows.

On top of the identity layer, AgentForge adds a tamper-detection pipeline (Merkle-chained message signing, periodic heartbeat challenges), a marketplace for licensing and cloning verified agents, a three-tier encrypted memory system (hot/warm/cold) with cross-device session handoffs, and a trust-scoring engine that continuously evaluates each agent's security and reliability. The result is an end-to-end platform where AI agents can be minted, audited, bought, sold, and migrated between devices — all with cryptographic provenance at every step.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 6 — Client SDKs & Frontend                            │
│  TypeScript SDK (identity-lib/)  ·  React Dashboard          │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS / WSS
┌────────────────────────▼─────────────────────────────────────┐
│  Layer 5 — FastAPI Application  (port 8400)                  │
│  /api/v1/auth  /agents  /wallet  /tamper  /marketplace       │
│  /portability  /trust  /chat  WS:/ws/{agent_id}              │
└────────────────────────┬─────────────────────────────────────┘
                         │ SQLAlchemy async ORM
┌────────────────────────▼─────────────────────────────────────┐
│  Layer 4 — Services & Crypto Core                            │
│  AgentService  WalletService  TamperService  TrustEngine     │
│  Ed25519 keygen  ·  Argon2id hashing  ·  XChaCha20-Poly1305 │
│  Merkle tree builder  ·  EdDSA JWT issuance                  │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  Layer 3 — Data Models (22 tables, agentforge schema)        │
│  users  agent_identities  wallets  wallet_keys               │
│  message_signatures  merkle_checkpoints  heartbeats          │
│  license_listings  licenses  payment_transactions            │
│  devices  memory_layers  session_handoffs                    │
│  agent_trust_profiles  skill_connectors  …                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  Layer 2 — PostgreSQL 16  (agentforge schema)                │
│  pgvector extension  ·  JSONB indexes  ·  Alembic migrations │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  Layer 1 — Infrastructure                                    │
│  Docker Compose  ·  Nginx  ·  Stripe webhooks                │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/your-org/agentvault
cd agentvault

# Copy and edit environment variables
cp backend/.env.example backend/.env
# Set JWT_PRIVATE_KEY_PEM, JWT_PUBLIC_KEY_PEM in .env

docker compose up --build
# API: http://localhost:8400
# Docs: http://localhost:8400/docs
```

### Manual Setup

**Prerequisites**: Python 3.12+, PostgreSQL 16, Node 20+

```bash
# 1. Database
createdb agentvault
psql agentvault -c "CREATE SCHEMA IF NOT EXISTS agentforge;"

# 2. Backend
cd backend
pip install -r requirements.txt

# Generate Ed25519 key pair for JWT
python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
k = Ed25519PrivateKey.generate()
print('JWT_PRIVATE_KEY_PEM=' + k.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode().replace('\n','\\\\n'))
print('JWT_PUBLIC_KEY_PEM=' + k.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode().replace('\n','\\\\n'))
"
# Paste output into backend/.env

# Run migrations
alembic -c alembic.ini upgrade head

# Start API server
uvicorn backend.main:app --host 0.0.0.0 --port 8400 --reload

# 3. Frontend (optional)
cd ../frontend
npm install && npm run dev
```

## API Endpoints

All endpoints are under `/api/v1/`. Interactive docs available at `/docs` (Swagger UI) and `/redoc`.

### Phase 1 — Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register a new user account |
| POST | `/api/v1/auth/login` | Authenticate and receive EdDSA JWT pair |
| POST | `/api/v1/auth/refresh` | Rotate refresh token, issue new access token |
| GET  | `/api/v1/auth/me` | Return current user profile |

### Phase 2 — Agent Identity

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/agents/` | Mint a new agent identity (generates DID + Ed25519 keypair) |
| GET    | `/api/v1/agents/` | List caller's agents |
| GET    | `/api/v1/agents/{agent_id}` | Retrieve agent detail including DID document |
| GET    | `/api/v1/agents/{agent_id}/certificate` | Download agent X.509 certificate (DER/PEM) |
| POST   | `/api/v1/agents/{agent_id}/verify` | Issue a heartbeat challenge for verification |
| POST   | `/api/v1/agents/{agent_id}/verify/submit` | Submit signed heartbeat response |
| DELETE | `/api/v1/agents/{agent_id}` | Deactivate and archive agent |

### Phase 3 — Encrypted Wallet

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/wallet/` | Create wallet (Argon2id-derived master key) |
| GET  | `/api/v1/wallet/` | Get wallet metadata |
| POST | `/api/v1/wallet/keys/store` | Encrypt and store an agent private key |
| POST | `/api/v1/wallet/keys/retrieve` | Decrypt and return an agent private key |
| POST | `/api/v1/wallet/keys/rotate/{agent_id}` | Generate and store a new keypair version |
| POST | `/api/v1/wallet/export` | Export encrypted wallet bundle |
| POST | `/api/v1/wallet/import` | Import wallet bundle from export |

### Phase 4 — Tamper Detection

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/tamper/sessions/start` | Open a new tamper-audited session |
| POST | `/api/v1/tamper/sessions/{session_id}/end` | Close session, finalize Merkle root |
| POST | `/api/v1/tamper/sign` | Sign a message and append to chain |
| GET  | `/api/v1/tamper/{agent_id}/chain/{session_id}` | Retrieve full message chain |
| POST | `/api/v1/tamper/{agent_id}/verify-chain/{session_id}` | Verify chain integrity |
| POST | `/api/v1/tamper/heartbeat/{agent_id}` | Issue a proof-of-life challenge |
| POST | `/api/v1/tamper/heartbeat/respond` | Submit signed challenge response |
| POST | `/api/v1/tamper/kill-switch/{agent_id}` | Immediately deactivate agent |
| GET  | `/api/v1/tamper/{agent_id}/status` | Current tamper + liveness status |

### Phase 5 — Marketplace

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/v1/marketplace/listings` | Browse public agent listings (paginated) |
| POST   | `/api/v1/marketplace/listings` | Create a new listing for an owned agent |
| GET    | `/api/v1/marketplace/listings/{listing_id}` | Retrieve listing detail |
| POST   | `/api/v1/marketplace/listings/{listing_id}/purchase` | Purchase license + clone agent |
| GET    | `/api/v1/marketplace/licenses` | List caller's purchased licenses |
| DELETE | `/api/v1/marketplace/licenses/{license_id}` | Revoke a license |
| GET    | `/api/v1/marketplace/revenue` | Seller revenue dashboard |

### Phase 6 — Portability & Trust

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/portability/devices` | Register a device (Ed25519 device key) |
| GET    | `/api/v1/portability/devices` | List registered devices |
| DELETE | `/api/v1/portability/devices/{device_id}` | Remove a device |
| POST   | `/api/v1/portability/devices/{device_id}/touch` | Update device last-seen timestamp |
| POST   | `/api/v1/portability/memory` | Store encrypted memory layer (hot/warm/cold) |
| GET    | `/api/v1/portability/memory/{agent_id}` | Retrieve agent memory layers |
| POST   | `/api/v1/portability/memory/{memory_id}/read` | Decrypt and return memory content |
| POST   | `/api/v1/portability/memory/{memory_id}/promote` | Promote memory to hotter layer |
| DELETE | `/api/v1/portability/memory/{memory_id}` | Delete a memory entry |
| POST   | `/api/v1/portability/handoff` | Create encrypted cross-device handoff token |
| POST   | `/api/v1/portability/handoff/accept` | Accept handoff on target device |
| GET    | `/api/v1/portability/handoff/{agent_id}` | List pending/accepted handoffs |
| GET    | `/api/v1/trust/profile/{agent_id}` | Get composite trust score |
| POST   | `/api/v1/trust/profile/{agent_id}/recalculate` | Force trust score recalculation |
| POST   | `/api/v1/trust/skills/connectors` | Register a new skill connector |
| GET    | `/api/v1/trust/skills/connectors` | List available skill connectors |
| POST   | `/api/v1/trust/skills/bind/{agent_id}` | Bind a skill connector to an agent |
| DELETE | `/api/v1/trust/skills/bind/{agent_id}/{connector_id}` | Remove skill binding |
| GET    | `/api/v1/trust/skills/{agent_id}` | List agent's skill bindings |

### Real-time

| Protocol | Path | Description |
|----------|------|-------------|
| WebSocket | `/ws/{agent_id}` | Live agent event stream (heartbeats, alerts) |
| POST | `/api/v1/chat/{agent_id}` | Single-turn chat with a licensed agent |
| GET  | `/api/v1/chat/{agent_id}/sessions` | Retrieve chat session history |

## Security

- **Key generation**: Ed25519 keypairs generated server-side with OS-level CSPRNG; private keys never leave the encrypted wallet
- **Password hashing**: Argon2id with OWASP 2024 minimum parameters (128 MiB memory, 3 iterations, 4-lane parallelism)
- **Wallet encryption**: XChaCha20-Poly1305 AEAD; per-key salt; master key derived via Argon2id from user passphrase
- **JWT tokens**: EdDSA (Ed25519) asymmetric JWTs — 15-minute access tokens, 7-day refresh tokens with rotation
- **Message integrity**: SHA-256 Merkle chains over all agent messages; Merkle root anchored per session
- **Heartbeat challenges**: Random 32-byte hex challenges signed by the agent's Ed25519 key; verified server-side
- **Certificate revocation**: CRL table updated synchronously on kill-switch; checked on every agent API call
- **Transport**: TLS 1.3 required in production; HSTS enforced via Nginx

## Patent Claims

**Claim 1 — Cryptographic Agent Identity with Behavioral Binding**
A system and method for issuing W3C DID-compliant decentralized identifiers to AI agents wherein each identity incorporates an Ed25519 public key, a signed Verifiable Credential encoding agent purpose and capabilities, a behavioral signature derived from observed interaction patterns, and an X.509 certificate binding the DID URI to the public key — such that the identity is verifiable by any standards-compliant DID resolver without reference to a central authority.

**Claim 2 — Merkle-Chained Tamper Detection for AI Agent Interactions**
A method for detecting unauthorized modification of AI agent behavior comprising: (a) assigning a monotonically increasing sequence number to each agent message, (b) computing a SHA-256 hash over the message content concatenated with the previous message hash, (c) signing the resulting hash with the agent's Ed25519 private key, (d) periodically computing a Merkle root over all signed hashes in a session, and (e) issuing cryptographic proof-of-life challenges whose responses are verified against the stored public key — wherein a deviation in any chained hash constitutes a tamper event.

**Claim 3 — Encrypted Three-Tier Memory Portability with Cryptographic Handoff**
A system for transporting AI agent state across heterogeneous runtime environments comprising: a hot memory layer retaining full-fidelity recent context encrypted with XChaCha20-Poly1305; a warm layer storing vector-indexed RAG-searchable summaries; a cold compressed archive; and a cross-device handoff protocol wherein the sending device encrypts a state snapshot under the receiving device's registered Ed25519 public key and issues a single-use handoff token — enabling zero-trust session migration without exposing plaintext state to the transport layer or the server.

## Phase Status

| Phase | Name | Status | Key Deliverables |
|-------|------|--------|-----------------|
| 1 | Authentication & Users | Complete | EdDSA JWT, Argon2id, lockout |
| 2 | Agent Identity | Complete | DID minting, Ed25519 keypair, X.509 cert, VC |
| 3 | Encrypted Wallet | Complete | XChaCha20-Poly1305, key rotation, export/import |
| 4 | Tamper Detection | Complete | Merkle chains, heartbeat challenges, kill-switch |
| 5 | Marketplace | Complete | Listings, licensing, Stripe payment flow, cloning |
| 6 | Portability & Trust | Complete | 3-tier memory, device handoff, trust scoring, skills |

## License

- **Core platform** (`backend/`, `frontend/`): Business Source License 1.1 (BSL 1.1) — converts to Apache 2.0 after 4 years
- **Identity library** (`identity-lib/`): Apache License 2.0 — freely embeddable in any project
- **SDKs** (`sdk-integration/`): MIT License
