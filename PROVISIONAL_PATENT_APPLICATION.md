# PROVISIONAL PATENT APPLICATION

**Title:** SYSTEM AND METHOD FOR CRYPTOGRAPHIC IDENTITY MANAGEMENT,
PORTABLE WALLET STORAGE, AND LICENSED CLONING OF AI AGENTS

**Inventors:** [TO BE COMPLETED BEFORE NON-PROVISIONAL FILING]
- Inventor 1: _______________________, Residence: _______________________
- Inventor 2 (if applicable): _______________________, Residence: _______________________

**Filing Date:** March 18, 2026

**Correspondence Address:**
[Attorney / Agent Name and Registration Number, or Applicant Address]

**Application Type:** Provisional Patent Application
**Small Entity / Micro Entity Status:** [TO BE DETERMINED]

---

> **PRACTITIONER NOTE**: This provisional application is filed to establish a
> priority date. A nonprovisional application must be filed within 12 months
> (by March 18, 2027) to claim the benefit of this filing date under 35 U.S.C.
> § 119(e). Claims are included here for clarity but are not required in a
> provisional. The specification satisfies 35 U.S.C. § 112(a) enablement and
> written description requirements.

---

## BACKGROUND OF THE INVENTION

### Field of the Invention

The present invention relates to cryptographic identity systems for artificial
intelligence agents, and more particularly to methods and systems for: (1)
generating and binding behavioral fingerprints to persistent cryptographic
identities for AI agents; (2) providing user-controlled portable encrypted
storage of AI agent private keys across computing devices; and (3) enabling a
licensed cloning marketplace for AI agents with cryptographic provenance
tracking and seller-controlled revocation.

### Background and Prior Art

**Problem 1: AI Agents Have No Persistent, Tamper-Evident Identity**

Artificial intelligence agents — software entities that execute tasks,
maintain conversational context, hold specialized capabilities, and interact
with external systems — have emerged as a critical category of software. Despite
their sophistication, AI agents in current practice have no persistent
cryptographic identity. When a user deploys an AI agent via a commercial
platform (e.g., OpenAI Assistants API, Anthropic Claude, LangChain agent
frameworks, CrewAI, AutoGen), the agent is instantiated as a stateless
processing unit. There is no mechanism to: (a) cryptographically prove that a
given agent response originated from a specific agent instance and has not been
tampered with in transit or at rest; (b) detect substitution of one agent for
another between sessions; (c) verify that the behavioral characteristics of an
agent at time T1 are the same agent operating at time T2; or (d) produce a
cryptographically-signed, auditable record of an agent's session activity for
compliance, legal, or forensic purposes.

Prior art in digital identity (PKI, X.509, OAuth 2.0, OIDC) addresses human
user authentication but does not address the binding of an AI agent's
behavioral attributes — its declared capabilities, model version, operational
purpose, and response-signing history — to a cryptographic key pair that
persists across session boundaries. The W3C Decentralized Identifiers (DID)
specification (W3C Recommendation, July 19, 2022) provides a general framework
for decentralized identifiers but does not specify: how AI agent behavioral
fingerprints are constructed or bound to a DID; how session-level tamper
detection using Merkle hash trees is integrated with agent identity; or how
signed Verifiable Credentials encode AI-specific attributes (capabilities,
model version, operational purpose) such that they can be verified by third
parties without contacting the issuing platform.

**Problem 2: AI Agent Private Keys Have No Secure, Portable, User-Controlled
Storage**

When an AI agent possesses a cryptographic identity (private/public key pair),
the private key must be stored securely. Existing approaches present
unacceptable tradeoffs. Cloud-custodied key storage (storing private keys on
the platform provider's servers) eliminates user ownership: the platform can
impersonate the agent, revoke the agent's identity without the user's consent,
or lose the keys in a breach. Local key storage in plaintext or weakly-encrypted
files (e.g., encrypted with AES-128-CBC using PBKDF2-HMAC-SHA256 key
derivation) is vulnerable to offline brute force attacks, particularly given
the availability of consumer GPU hardware (e.g., an NVIDIA RTX 4090 can
evaluate PBKDF2-HMAC-SHA256 at approximately 2.8 million guesses per second).

Furthermore, no existing system provides a mechanism whereby a user can:
(a) maintain possession of AI agent private keys independently of any platform
provider; (b) export those keys as a portable encrypted archive and import them
to a different device using a secure re-encryption protocol; (c) rotate keys
on demand without losing the agent's identity continuity; and (d) accomplish
all of the above with key derivation functions specifically designed to resist
GPU-accelerated brute force attacks (e.g., Argon2id with configurable memory
hardness), combined with authenticated encryption that provides both
confidentiality and tamper detection on the stored ciphertext (e.g.,
XChaCha20-Poly1305).

**Problem 3: There Is No Marketplace Mechanism for Licensing AI Agents with
Cryptographic Provenance and Revocability**

AI agents that have been trained, configured, and refined to perform specialized
tasks (legal research, medical triage, financial analysis, customer service)
represent significant intellectual and commercial value. No existing system
provides a mechanism whereby: (a) an AI agent's creator can offer the agent's
capabilities for licensing to third parties while retaining cryptographic proof
of the original agent's authorship; (b) each license issuance spawns a
cryptographically distinct clone agent — possessing its own unique key pair and
DID — that is nevertheless provably derived from the source agent via an
immutable, signed license record; (c) the clone's ongoing operation is
continuously metered and bounded by license terms encoded in the provenance
record; and (d) the licensor can cryptographically revoke an individual clone's
operational authority by updating a certificate revocation record that is
distributed to all network participants, without affecting other valid licensees.

Prior art in software licensing (license keys, activation servers, DRM systems)
addresses static software distribution but does not address the dynamic,
session-continuous nature of AI agent operation, where each agent conversation
generates signed outputs that must be attributable to a specific licensed
instance. Prior art in NFT-based ownership systems addresses asset ownership
on distributed ledgers but introduces blockchain dependencies (gas fees,
throughput limits, finality delays) that are incompatible with enterprise
deployment requirements. No prior art combines: fresh keypair generation per
clone, W3C Verifiable Credential issuance for the clone's birth certificate
signed by the platform's issuer DID, behavioral parameter inheritance from the
source agent, and a seller-controlled cryptographic revocation mechanism — all
in an off-chain, database-backed architecture.

---

## SUMMARY OF THE INVENTION

The present invention provides a unified platform — referred to herein as
"AgentForge" or "the system" — comprising three core technical innovations that
address the problems described above.

**First Innovation — Cryptographic Agent Identity Binding**: The invention
provides a computer-implemented method for generating a persistent
cryptographic identity for an AI agent by: generating an Ed25519 key pair
(private seed and 32-byte public key) using a cryptographically secure random
number generator; constructing a W3C DID Document in `did:web` format
incorporating the agent's Ed25519 public key as an `Ed25519VerificationKey2020`
verification method; computing a behavioral fingerprint as a structured JSON
object encoding the agent's declared capabilities, model version, operational
purpose, and key fingerprint (SHA-256 of the public key, hex-encoded); and
issuing a W3C Verifiable Credential (type: `AgentBirthCertificate`) signed
with the platform's Ed25519 private key that attests to the agent's identity
attributes. Session-level tamper detection is provided by a binary Merkle hash
tree constructed from SHA-256 hashes of the agent's signed message outputs,
with O(log n) inclusion proofs enabling selective verification of any
individual session message.

**Second Innovation — User-Controlled Portable Agent Wallet**: The invention
provides a system for user-controlled storage of AI agent private keys,
comprising: a wallet data structure storing, for each agent, the agent's
private key seed encrypted using XChaCha20-Poly1305 authenticated encryption
(via PyNaCl SecretBox, providing a 192-bit nonce space that eliminates nonce
collision risk) with a per-agent encryption key derived from a master wallet
key; the master wallet key derived from a user-supplied passphrase using
Argon2id key derivation (memory_cost=131,072 KiB, time_cost=3,
parallelism=4) over a cryptographically random 128-bit salt, providing
resistance to GPU-accelerated brute force attacks; and a cross-device
portability protocol wherein wallet contents are re-encrypted under a separate
export passphrase, wrapped in an additional XChaCha20-Poly1305 encryption
layer with an independent salt, and transmitted as a self-contained encrypted
binary blob that can be decrypted and imported on any target device.

**Third Innovation — Licensed Clone Marketplace with Cryptographic Provenance**:
The invention provides a computer-implemented method for licensing copies of
AI agents with cryptographic provenance, comprising: upon license purchase,
spawning a clone agent having a freshly-generated Ed25519 key pair (distinct
from the source agent's key pair) and a newly-issued W3C DID URI; copying the
source agent's behavioral parameters (capabilities list, model version,
operational purpose, runtime configuration) to the clone while encoding the
source agent's UUID in the clone's `behavioral_signature` field; issuing a
W3C Verifiable Credential for the clone, signed by the platform's issuer DID,
that encodes the source-clone relationship; generating a deterministic license
key by computing a SHA-256 hash over the concatenation of the listing UUID,
buyer UUID, clone UUID, and a cryptographically random 128-bit nonce; and
providing seller-controlled license revocation that deactivates the clone
agent's operational status and records the revocation timestamp in a
certificate revocation record.

---

## DETAILED DESCRIPTION OF THE PREFERRED EMBODIMENT

### Overview of System Architecture

The system comprises a backend server application implemented in Python using
the FastAPI framework, a PostgreSQL relational database for persistent storage,
a cryptographic library layer (the "crypto module"), and a web-based frontend.
The backend exposes a REST API and WebSocket endpoints. The crypto module
implements the primitives described herein using PyNaCl (libsodium Python
bindings) and argon2-cffi. All private key material is handled exclusively by
the backend; private keys are never transmitted to or stored on client devices
in plaintext.

The system maintains the following primary database tables (within the
`agentforge` schema) relevant to the claimed inventions:

- `agent_identities`: Stores agent public keys, DID URIs, DID Documents (JSONB),
  Verifiable Credentials (JSONB), behavioral signatures (JSONB), key
  fingerprints, and key algorithm identifiers.
- `wallets`: Stores encrypted master key material and key derivation salts.
- `wallet_keys`: Stores per-agent encrypted private key seeds, key version
  numbers, and revocation timestamps.
- `license_listings`: Stores marketplace listings with license terms,
  maximum clone counts, and pricing.
- `licenses`: Stores license records linking source agents, clone agents,
  buyers, license keys, usage limits, and expiration times.
- `license_usage_records`: Stores per-interaction usage records against
  active licenses.
- `merkle_checkpoints`: Stores periodic Merkle root snapshots for session
  tamper detection.
- `message_signatures`: Stores per-message Ed25519 signatures and sequence
  numbers for session integrity chains.

---

### Section 1: Cryptographic Agent Identity Binding

#### 1.1 Key Generation

When a user requests creation of a new AI agent, the system invokes the
`generate_keypair()` function. This function calls `nacl.signing.SigningKey.generate()`,
which internally invokes libsodium's `crypto_sign_keypair()` to generate
an Ed25519 key pair using a CSPRNG. The function returns a `KeyPair` named
tuple containing:

- `private_key`: A 32-byte private key seed (the Edwards-curve scalar).
- `public_key`: A 32-byte Ed25519 public key (a compressed Edwards-curve
  point on Curve25519's twisted Edwards form).

The private key seed is immediately passed to the wallet service for encrypted
storage (described in Section 2) and is zeroed from memory using
`nacl_utils.sodium_memzero` after storage. The raw seed is never written to
disk or logged.

#### 1.2 Key Fingerprint Computation

A key fingerprint is computed as `SHA-256(public_key_bytes)`, hex-encoded to
a 64-character lowercase string. This fingerprint serves as a unique, compact
identifier for the agent's current public key and is stored in the
`key_fingerprint` column of `agent_identities` with a `UNIQUE` constraint.
The fingerprint allows rapid identity lookup without parsing the full DID
Document.

#### 1.3 W3C DID Document Construction

The system constructs a W3C Decentralized Identifier Document (DID Document)
conforming to the W3C DID Core 1.0 specification (W3C Recommendation, July
2022) and the `did:web` DID Method specification. The DID URI takes the form:

```
did:web:{domain}:agents:{agent_uuid}
```

where `{domain}` is the platform's registered domain (e.g., `agentforge.dev`)
and `{agent_uuid}` is a RFC 4122 version 4 UUID generated at agent creation
time.

The DID Document is a JSON-LD object with the following structure:

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/ed25519-2020/v1"
  ],
  "id": "did:web:{domain}:agents:{uuid}",
  "controller": "did:web:{domain}:agents:{uuid}",
  "verificationMethod": [{
    "id": "did:web:{domain}:agents:{uuid}#key-1",
    "type": "Ed25519VerificationKey2020",
    "controller": "did:web:{domain}:agents:{uuid}",
    "publicKeyMultibase": "z{base58btc-encoded-public-key}"
  }],
  "authentication": ["did:web:{domain}:agents:{uuid}#key-1"],
  "assertionMethod": ["did:web:{domain}:agents:{uuid}#key-1"],
  "created": "{ISO-8601-timestamp}"
}
```

The public key is encoded using base58btc encoding with the multibase prefix
`z` as specified by the W3C Multibase draft specification and the
`Ed25519VerificationKey2020` suite specification. The DID Document is stored
as a JSONB column in the `agent_identities` table and is resolvable via a
standard HTTP GET request to `https://{domain}/.well-known/did/{uuid}/did.json`.

#### 1.4 Behavioral Fingerprint Construction

The behavioral fingerprint is a structured data object stored as a JSONB
column (`behavioral_signature`) in the `agent_identities` table. It encodes
the agent's declared identity attributes at creation time:

```json
{
  "capabilities": ["[capability_1]", "[capability_2]", "..."],
  "model_version": "[model_identifier]",
  "purpose": "[natural_language_purpose_description]",
  "key_fingerprint": "[64-char SHA-256 hex]",
  "created_at": "[ISO-8601-timestamp]"
}
```

The behavioral fingerprint binds the agent's functional identity to its
cryptographic identity: the `key_fingerprint` field links the functional
attributes to the specific Ed25519 public key, such that any change to the
agent's key (e.g., following key rotation) creates a new fingerprint version,
providing an auditable history of the agent's identity evolution.

For cloned agents, the behavioral fingerprint additionally includes:

```json
{
  "clone_of": "[source_agent_uuid]",
  "created_at": "[ISO-8601-timestamp]"
}
```

This field establishes the cryptographic lineage from clone to source without
requiring the clone to share the source agent's key material.

#### 1.5 Verifiable Credential Issuance

The system issues a W3C Verifiable Credential (VC) of type
`AgentBirthCertificate` for each newly created agent. The VC is signed by the
platform's designated issuer DID (the platform's own Ed25519 key pair, whose
private key is held in secure hardware on the platform backend). The VC
credentialSubject encodes:

- The agent's DID URI
- Display name, agent type, model version, and operational purpose
- The agent's capabilities list
- The agent's Ed25519 public key (base58btc multibase encoded)

The proof section of the VC uses `Ed25519Signature2020` proof type:

```json
{
  "proof": {
    "type": "Ed25519Signature2020",
    "created": "[ISO-8601-timestamp]",
    "verificationMethod": "[issuer_did]#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "z{base58btc-encoded-Ed25519-signature}"
  }
}
```

The signature is computed over the canonical JSON serialization of the VC
body (excluding the proof object) using the platform's Ed25519 private key.
Any third party holding the platform's Ed25519 public key can independently
verify the VC without contacting the platform.

#### 1.6 Session-Level Tamper Detection via Merkle Hash Tree

The system maintains session-level tamper evidence using a binary Merkle hash
tree. For each agent session, every agent message output is:

1. Signed with the agent's Ed25519 private key (retrieved from the wallet for
   the duration of the session and held in process memory).
2. Hashed using SHA-256: `leaf_hash = SHA-256(0x00 || message_bytes)` (the
   `0x00` prefix prevents second-preimage attacks).
3. Appended to a `MerkleTree` object that maintains the binary tree
   structure.

Internal nodes are computed as: `parent = SHA-256(0x01 || left_child || right_child)`.
Odd-length layers are handled by duplicating the last leaf node (standard
Bitcoin Merkle tree convention). The Merkle root is stored as a
`merkle_checkpoint` record at configurable intervals (default: every 100
messages or every session boundary).

Inclusion proofs are O(log n) in the number of messages. A proof for message
at index `i` in a tree of `n` leaves consists of `⌈log₂(n)⌉` sibling hashes
with position indicators ("left" or "right"), sufficient to reconstruct the
root from any single leaf.

The `key_algorithm` field in the `MerkleTree` data structure (default:
`"sha256"`) is reserved for future hybrid post-quantum signatures (e.g.,
`"sha256+ml-dsa-65"`) to provide upgrade path compatibility without schema
changes.

---

### Section 2: User-Controlled Portable Agent Wallet

#### 2.1 Wallet Architecture

The system provides each user with exactly one wallet (a one-to-one mapping
enforced by a `UNIQUE` constraint on `wallets.owner_id`). The wallet stores
per-agent encrypted private key entries (in `wallet_keys`) rather than storing
private keys in any centralized location under platform control.

The wallet employs a two-layer encryption architecture:

**Layer 1 — Master Key Derivation**: A master 256-bit symmetric key is derived
from the user's passphrase using Argon2id key derivation:

```
master_key = Argon2id(
    secret   = passphrase_bytes,
    salt     = random_128_bit_salt,
    t_cost   = 3,         # 3 iterations
    m_cost   = 131072,    # 128 MiB memory
    p_cost   = 4,         # 4 parallel lanes
    hash_len = 32         # 256-bit output
)
```

The parameters conform to OWASP 2024 recommendations for offline attack
resistance. The memory cost of 128 MiB ensures that parallel GPU attacks
are bounded by GPU memory bandwidth rather than compute throughput. At these
parameters, an NVIDIA RTX 5090 (32 GB VRAM) can evaluate no more than
approximately 100-200 Argon2id derivations per second per GPU, compared to
approximately 2.8 billion SHA-256 operations per second — a factor of
approximately 14 million in attack cost increase over PBKDF2-SHA256.

**Layer 2 — Per-Agent Key Encryption**: Each agent's 32-byte private key
seed is encrypted using XChaCha20-Poly1305 authenticated encryption:

```
(ciphertext || tag) = XChaCha20-Poly1305-Encrypt(
    key   = derive_key(master_key || per_agent_salt),
    nonce = random_192_bit_nonce,  # auto-generated by PyNaCl SecretBox
    msg   = private_key_seed_32_bytes
)
```

XChaCha20-Poly1305 is implemented via `nacl.secret.SecretBox` (PyNaCl),
which uses libsodium's `crypto_secretbox_xchacha20poly1305` primitive.
The 192-bit nonce space (vs. 96-bit for standard ChaCha20-Poly1305) eliminates
the risk of nonce collision under random nonce generation even for wallets
storing large numbers of keys. The 128-bit Poly1305 authentication tag
ensures that any modification to the ciphertext (bit-flip attack, truncation,
extension) is detected with overwhelming probability (2^-128 false positive
rate) before decryption.

The encrypted private key (`private_key_enc`) and per-agent salt (`key_salt`)
are stored in the `wallet_keys` table. The salt is stored in plaintext
alongside the ciphertext (standard practice; the salt is not secret). The
master key is never stored; it is re-derived on each wallet unlock operation.

#### 2.2 Key Versioning and Rotation

The `wallet_keys` table maintains key version numbers. On key rotation
(triggered by a `POST /api/v1/wallet/keys/rotate/{agent_id}` request):

1. The active `WalletKey` record for the agent is marked as revoked by
   setting `revoked_at` to the current UTC timestamp.
2. A fresh Ed25519 key pair is generated for the agent.
3. The agent's `public_key`, `key_fingerprint`, and `did_document` fields
   in `agent_identities` are updated to reflect the new key pair.
4. A new `WalletKey` record is created with `key_version` incremented by 1
   and the new private key seed encrypted under the current master key.

This rotation protocol provides forward secrecy at the session level:
compromise of a private key at time T does not compromise sessions signed
before the most recent rotation.

#### 2.3 Cross-Device Portability Protocol

The wallet export protocol provides cross-device portability without
requiring platform intermediation:

**Export**:
1. The user supplies their current wallet passphrase and a separate export
   passphrase.
2. The system derives the master key from the wallet passphrase and decrypts
   each active agent private key seed.
3. Each seed is re-encrypted under a key derived from the export passphrase
   (Argon2id with a fresh salt per key).
4. The resulting JSON structure (wallet metadata + per-key encrypted seeds)
   is serialized to bytes.
5. The entire serialized structure is wrapped in an additional
   XChaCha20-Poly1305 encryption layer using a key derived from the export
   passphrase over a new 16-byte random salt: `export_blob = salt || Encrypt(export_key, json_bytes)`.
6. The encrypted blob is transmitted to the user as a binary download.

**Import**:
1. On the target device, the user provides the export passphrase and a new
   local wallet passphrase.
2. The system decrypts the outer XChaCha20-Poly1305 layer using the export
   passphrase.
3. Each per-key encrypted seed is decrypted and re-encrypted under the new
   local wallet passphrase.
4. Agent identity records are re-associated with the imported wallet.

This protocol ensures that the platform backend never has access to plaintext
private key seeds during the export/import process (re-encryption occurs
server-side but with keys that the server cannot retain without the user's
passphrase, which is never transmitted to the server).

---

### Section 3: Licensed Clone Marketplace with Cryptographic Provenance

#### 3.1 Marketplace Listing

An agent owner (seller) creates a `LicenseListing` record specifying: the
source `agent_id`, price in integer cents, license type (enumeration:
`perpetual`, `subscription`, `per_use`), maximum number of clones (`max_clones`),
and optional structured license terms (JSONB). The listing is active while
`is_active = TRUE` and `total_sales < max_clones`.

#### 3.2 Clone Spawning Protocol

Upon license purchase (invoked at `POST /api/v1/marketplace/listings/{id}/purchase`),
the system executes the following cryptographic provenance protocol within a
single database transaction:

**Step 1 — Fresh Keypair Generation**: The system invokes `generate_keypair()`
to produce a new Ed25519 key pair for the clone agent. This keypair is
cryptographically independent of the source agent's keypair (generated from
independent randomness). The clone agent's DID URI is:
```
did:web:{domain}:agents:{clone_uuid}
```
where `{clone_uuid}` is a newly generated RFC 4122 v4 UUID, distinct from
the source agent's UUID.

**Step 2 — Capability Inheritance**: The clone agent's `capabilities`,
`agent_type`, `model_version`, `purpose`, `preferred_runtime`, and
`routing_config` fields are copied from the source agent's corresponding
fields. This constitutes a functional copy of the source agent's behavioral
specification without copying any cryptographic material.

**Step 3 — Provenance Credential Issuance**: A W3C Verifiable Credential
of type `AgentBirthCertificate` is issued for the clone agent, signed by
the platform's Ed25519 issuer key. The `credentialSubject` encodes the
clone agent's DID, public key, and inherited capabilities. The clone's
`behavioral_signature` JSONB field is set to:
```json
{
  "clone_of": "{source_agent_uuid}",
  "created_at": "{ISO-8601-timestamp}"
}
```
This `clone_of` field constitutes the cryptographic lineage record, creating
an immutable reference from the clone's identity to the source agent's UUID.

**Step 4 — License Key Generation**: A license key is generated as:
```
license_key = "AFORGE-" || uppercase(hex(SHA-256(
    "{listing_uuid}:{buyer_uuid}:{clone_uuid}:{random_128_bit_nonce}"
))[0:32])
```
The 128-bit random nonce prevents pre-computation of license keys by any
party who knows the listing and buyer UUIDs.

**Step 5 — License Record Creation**: A `License` record is created linking:
the `listing_id`, `buyer_id`, `clone_agent_id`, `license_key`, `status`
(`active`), `starts_at`, `expires_at` (for subscription licenses: 30 days;
null for perpetual), and `usage_limit` (for per-use licenses: configurable
integer; null for perpetual and subscription).

**Step 6 — Payment Recording**: A `PaymentTransaction` record is created
capturing the gross amount, the platform fee (20% of gross), and net seller
revenue, with cryptographic integrity ensured by the database transaction
atomicity guarantees.

#### 3.3 Usage Metering

Each interaction with a clone agent triggers a `track_usage()` call that:
1. Validates the license has not expired (`expires_at` check).
2. Validates the license has not exceeded its usage limit (`usage_count < usage_limit`).
3. Validates the license status is `active`.
4. Atomically increments `license.usage_count`.
5. Creates a `LicenseUsageRecord` with action type, token consumption count,
   and timestamp.

This metering is enforced server-side and cannot be bypassed by the clone
agent or the licensee.

#### 3.4 Cryptographic License Revocation

The seller may revoke any license at any time via
`DELETE /api/v1/marketplace/licenses/{license_id}`. Revocation:
1. Sets `license.status = 'revoked'` in the database.
2. Sets `clone_agent.is_active = FALSE` in `agent_identities`, preventing
   any further authenticated operations by the clone agent.
3. The revocation is reflected immediately in subsequent identity verification
   attempts against the clone's DID.

This revocation mechanism is seller-controlled and per-license, allowing
surgical revocation of individual bad actors without affecting other valid
licensees of the same source agent.

---

## CLAIMS

> **Note**: Claims are optional in a provisional application but are provided
> here to assist the drafter of the nonprovisional application and to clarify
> the scope of the inventive concepts.

### Claim 1

A computer-implemented method for binding a behavioral fingerprint to a
cryptographic identity for an artificial intelligence agent, the method
comprising:

1.1. generating, by one or more processors, an Ed25519 cryptographic key pair
comprising a 32-byte private key seed and a 32-byte public key, wherein the
private key seed is generated using a cryptographically secure pseudorandom
number generator;

1.2. computing a key fingerprint by applying a SHA-256 hash function to the
32-byte public key to produce a 64-character hexadecimal key fingerprint that
uniquely identifies the public key;

1.3. constructing a W3C Decentralized Identifier Document in `did:web` format
that incorporates the 32-byte public key as an `Ed25519VerificationKey2020`
verification method encoded in base58btc multibase format, wherein the DID
Document encodes the agent as both the DID subject and DID controller;

1.4. constructing a behavioral fingerprint data structure comprising a
capabilities list encoding the agent's declared functional capabilities, a
model version identifier encoding the underlying language model version, an
operational purpose string, and the key fingerprint computed in step 1.2,
wherein the behavioral fingerprint binds the agent's functional identity
attributes to its cryptographic key pair;

1.5. issuing a W3C Verifiable Credential of type `AgentBirthCertificate`
by: (a) constructing a credential document encoding the agent's DID URI,
display name, agent type, model version, purpose, capabilities list, and
base58btc-encoded public key as credential subject attributes; (b) computing
an Ed25519 digital signature over the canonical JSON serialization of the
credential document using the platform's designated issuer Ed25519 private
key; and (c) appending a proof object of type `Ed25519Signature2020` to the
credential document encoding the signature, the issuer's verification method
reference, and the proof purpose as `assertionMethod`; and

1.6. storing the DID Document and Verifiable Credential in a relational
database indexed by a universally unique identifier assigned to the agent at
creation time, wherein the stored records constitute a persistent, verifiable,
cryptographic identity for the artificial intelligence agent across session
boundaries.

### Claim 2

The method of Claim 1, further comprising:

2.1. for each message output produced by the artificial intelligence agent
during a session, computing a leaf hash as `SHA-256(0x00 || message_bytes)`,
wherein the `0x00` prefix prevents second-preimage attacks;

2.2. constructing a binary Merkle hash tree from the sequence of leaf hashes,
wherein internal node hashes are computed as `SHA-256(0x01 || left_child_hash || right_child_hash)`;

2.3. computing a Merkle root from the binary Merkle hash tree; and

2.4. storing the Merkle root in a database record associating the Merkle
root with the agent's unique identifier and the session identifier, wherein
the stored Merkle root enables O(log n) verification of the inclusion of any
individual agent message in the session's tamper-evident record.

### Claim 3

A system for user-controlled portable storage of artificial intelligence
agent private keys, the system comprising:

3.1. one or more processors executing a wallet service that: (a) for each
user, maintains a wallet data record storing a random 128-bit salt and an
encrypted master key validation marker; (b) derives a 256-bit master key
from a user-supplied passphrase and the stored salt using Argon2id key
derivation with memory_cost of at least 131,072 KiB, time_cost of at least
3 iterations, and parallelism of at least 4 parallel lanes, wherein the
Argon2id algorithm's memory hardness makes the derived key resistant to
GPU-accelerated brute force attack; and (c) for each artificial intelligence
agent controlled by the user, stores the agent's Ed25519 32-byte private key
seed encrypted using XChaCha20-Poly1305 authenticated encryption with a key
derived from the master key and a per-agent random salt;

3.2. a database storing, for each stored private key: the XChaCha20-Poly1305
ciphertext of the private key seed; the per-agent random salt; a key version
number; and a revocation timestamp, wherein a null revocation timestamp
indicates the key is currently active;

3.3. a key rotation procedure that, upon invocation: (a) marks the currently
active wallet key record for the agent as revoked by recording a revocation
timestamp; (b) generates a new Ed25519 key pair for the agent; (c) updates
the agent's stored public key, key fingerprint, and DID Document to reflect
the new key pair; and (d) stores the new private key seed encrypted under the
current master key with an incremented key version number; and

3.4. a portability protocol that exports wallet contents as a self-contained
encrypted binary blob comprising: (a) individual agent private key seeds,
each re-encrypted under a key derived from an export passphrase distinct from
the wallet passphrase using Argon2id over a per-key random salt; (b) the
collection of re-encrypted key records serialized to a JSON structure; and
(c) the JSON structure encrypted under an additional XChaCha20-Poly1305 layer
using a key derived from the export passphrase over an independent random
salt, wherein the encrypted binary blob can be imported on a target computing
device by providing the export passphrase and a new local wallet passphrase.

### Claim 4

The system of Claim 3, wherein the XChaCha20-Poly1305 authenticated
encryption uses a 192-bit random nonce generated by a cryptographically
secure pseudorandom number generator, wherein the 192-bit nonce space
provides a probability of nonce collision no greater than 2^-96 over the
lifetime of the wallet regardless of the number of encryption operations
performed.

### Claim 5

A computer-implemented method for licensing copies of artificial intelligence
agents with cryptographic provenance tracking, the method comprising:

5.1. receiving, by one or more processors, a license purchase request
identifying a source artificial intelligence agent having a first Ed25519
public key, a first W3C DID URI, a capabilities list, a model version
identifier, and an operational purpose string;

5.2. generating a second Ed25519 key pair comprising a second private key
seed and a second 32-byte public key, wherein the second key pair is generated
independently from new randomness and is cryptographically distinct from the
first Ed25519 key pair;

5.3. assigning a second universally unique identifier and constructing a
second W3C DID URI for a clone agent based on the second universally unique
identifier, wherein the second DID URI is distinct from the first DID URI;

5.4. copying the capabilities list, model version identifier, and operational
purpose string from the source artificial intelligence agent to the clone
agent, wherein the clone agent inherits the functional behavioral parameters
of the source agent without copying any cryptographic material from the source
agent;

5.5. recording a cryptographic provenance field in the clone agent's identity
record by setting a clone_of field to the universally unique identifier of
the source artificial intelligence agent, thereby establishing an immutable
cryptographic lineage from the clone agent to the source agent;

5.6. issuing a second W3C Verifiable Credential for the clone agent, signed
by the platform's Ed25519 issuer private key, encoding the clone agent's
DID URI, second public key, and inherited capability attributes as credential
subject fields; and

5.7. generating a license key by computing SHA-256 over a concatenation of
the listing identifier, buyer identifier, clone agent identifier, and a
randomly generated nonce, and storing a license record in a relational database
associating the license key with the source agent identifier, clone agent
identifier, buyer identifier, license terms including any expiration date
and usage limit, and a current usage count initialized to zero.

### Claim 6

The method of Claim 5, further comprising:

6.1. for each interaction with the clone artificial intelligence agent,
validating that a license record associated with the clone agent has a
status of active, that the current timestamp does not exceed any stored
expiration date, and that the current usage count does not exceed any
stored usage limit;

6.2. upon successful validation, atomically incrementing the usage count
in the license record and recording a usage event comprising an action
type identifier and a token consumption count; and

6.3. upon a revocation request received from the seller associated with
the source artificial intelligence agent: (a) setting the license record
status to revoked; and (b) setting an operational status field of the clone
agent's identity record to inactive, wherein the inactive status prevents
subsequent authenticated operations by the clone agent.

### Claim 7

The method of Claim 5, wherein the license terms specify one of a plurality
of license types comprising: a perpetual license type having no expiration
date and no usage limit; a subscription license type having an expiration
date set to a fixed interval from the license creation date; and a per-use
license type having an integer usage limit, wherein the license key generation
procedure and clone spawning procedure are identical regardless of the license
type, and the license type affects only the validation logic applied during
usage metering.

### Claim 8

A computer-implemented method for verifying the cryptographic provenance of
a licensed artificial intelligence agent clone, the method comprising:

8.1. receiving a clone agent's DID URI and W3C Verifiable Credential;

8.2. resolving the issuer DID from the Verifiable Credential's issuer field
and retrieving the issuer's Ed25519 public key from the issuer's DID Document;

8.3. verifying the Ed25519 digital signature in the Verifiable Credential's
proof object by: (a) removing the proof object from the Verifiable Credential
to produce a credential document; (b) computing the canonical JSON
serialization of the credential document; and (c) verifying the
Ed25519Signature2020 proof value against the canonical serialization using
the issuer's Ed25519 public key;

8.4. extracting the clone_of field from the clone agent's behavioral signature
record and retrieving the source agent's identity record using the extracted
source agent identifier; and

8.5. confirming that the source agent's identity record is associated with
a valid license listing, thereby establishing a complete and independently
verifiable cryptographic provenance chain from the clone agent to the source
agent.

---

## ABSTRACT

A system and method for providing persistent cryptographic identity,
user-controlled encrypted storage, and licensed cloning for artificial
intelligence agents. A cryptographic identity is established by generating
an Ed25519 key pair, constructing a W3C DID Document in `did:web` format
incorporating the public key as an `Ed25519VerificationKey2020` verification
method, computing a behavioral fingerprint binding the agent's functional
attributes to its key fingerprint, and issuing a W3C Verifiable Credential
signed with the platform's Ed25519 issuer key. Session tamper detection uses
a binary Merkle hash tree with O(log n) inclusion proofs. Private keys are
stored in a two-layer wallet: an Argon2id-derived (128 MiB, 3 iterations)
master key encrypts per-agent XChaCha20-Poly1305 ciphertexts, enabling
cross-device portability via a double-encrypted export blob. Licensed agent
clones are spawned with fresh Ed25519 key pairs, inherited behavioral
parameters, cryptographic lineage recorded in a `clone_of` provenance field,
and deterministic SHA-256 license keys. Seller-controlled revocation
deactivates individual clone agents without affecting co-licensees.

*(Word count: ~148)*

---

## PRIOR ART ANALYSIS AND DIFFERENTIATION

### Known Prior Art

The following prior art was identified during preparation of this application.
The claims are drafted to avoid the prior art as described below.

**1. W3C DID Core 1.0 (W3C Recommendation, July 2022)**
- *What it covers*: The general framework for decentralized identifiers,
  DID Document format, DID resolution, and abstract data model.
- *What it does not cover*: AI agent behavioral fingerprints, session-level
  Merkle tamper detection tied to an agent identity, wallet storage of agent
  private keys, or agent licensing/cloning mechanisms. The DID standard is
  a component used by the present invention, not prior art that anticipates it.
- *Differentiation*: Claims 1 and 5 use `did:web` as a component but add the
  novel behavioral fingerprint binding, Verifiable Credential issuance with
  AI-specific attributes, and the clone provenance protocol.

**2. W3C Verifiable Credentials Data Model 1.1 (W3C Recommendation, March 2022)**
- *What it covers*: The data model for verifiable credentials, proof formats
  including Ed25519Signature2020.
- *Differentiation*: The present invention applies VCs to AI agent birth
  certificates with AI-specific credential subject attributes
  (`agentType`, `capabilities`, `modelVersion`, `purpose`), which is
  not taught or suggested by the VC data model specification.

**3. Coinbase AgentKit / CDP Wallet (Coinbase Developer Platform, 2024)**
- *What it covers*: Cryptocurrency wallet management for AI agents; ability
  for AI agents to hold and spend cryptocurrency using Coinbase's custodied
  wallet infrastructure.
- *Differentiation*: AgentKit provides custodied wallets for AI agents to
  transact on blockchain networks. It does not provide: (a) user-controlled
  non-custodial wallet storage with Argon2id+XChaCha20-Poly1305 encryption
  for Ed25519 identity keys; (b) behavioral fingerprint binding; (c) session
  Merkle tamper detection; or (d) an off-chain agent licensing marketplace
  with cryptographic clone provenance. The present invention does not require
  blockchain infrastructure.

**4. World AgentKit / World ID (Tools for Humanity / World Foundation, 2024)**
- *What it covers*: Biometric proof-of-humanity verification system (iris
  scanning via Orb hardware) providing a "human" credential that can be
  delegated to AI agents via a `World ID Agent` mechanism.
- *Differentiation*: World AgentKit anchors agent identity to a biometrically-
  verified human principal and issues ZK-proof credentials. It does not
  address: persistent AI agent cryptographic identity independent of any
  human principal; agent wallet storage with memory-hard key derivation;
  session tamper detection; or an agent licensing marketplace. The
  authentication mechanism (biometric ZK-proof) is fundamentally different
  from the present invention's Ed25519 behavioral fingerprint approach.

**5. TalaoDAO Wallet4Agent (2024)**
- *What it covers*: A W3C DID-based digital wallet for AI agents, providing
  W3C Verifiable Credential storage for AI agents.
- *Differentiation*: Wallet4Agent focuses on credential presentation and
  storage for W3C VC compliance. It does not teach: Argon2id+XChaCha20-Poly1305
  encrypted private key storage with cross-device portability; behavioral
  fingerprint binding; Merkle session tamper detection; or a licensed
  cloning marketplace. The present invention adds tamper detection,
  memory-hard key storage, and the novel clone provenance protocol.

**6. ERC-8004 (Ethereum Request for Comments, 2024)**
- *What it covers*: An Ethereum blockchain standard for on-chain AI agent
  identity using smart contracts and NFT-like ownership tokens.
- *Differentiation*: ERC-8004 requires blockchain infrastructure (gas fees,
  transaction finality, Ethereum node operation). The present invention
  operates entirely off-chain using a conventional relational database, is
  free of gas fees, achieves sub-millisecond identity operations (vs.
  12-second Ethereum block time), and is deployable in enterprise network
  environments that prohibit external blockchain connectivity. The clone
  licensing mechanism in Claim 5 has no equivalent in ERC-8004.

**7. HashiCorp Vault (Secret Management, 2015-present)**
- *What it covers*: Enterprise secret management: secure storage and access
  control for API keys, passwords, certificates, and encryption keys.
- *Differentiation*: HashiCorp Vault provides generic secret storage and
  does not teach: behavioral fingerprint binding of secrets to AI agent
  identity; W3C DID Document construction; W3C Verifiable Credential
  issuance for agents; Merkle session tamper detection; or agent licensing
  with cryptographic clone provenance. The present invention's wallet
  (Claim 3) is specifically designed for AI agent Ed25519 private key
  storage with user-controlled portability, not generic enterprise secret
  management.

**8. Software License Key Systems (various prior art)**
- *What it covers*: Static license key generation (challenge-response,
  RSA-signed license files, activation servers) for traditional software.
- *Differentiation*: Existing software licensing addresses static software
  distribution and activation. The present invention's licensing mechanism
  (Claims 5-7) addresses dynamic, session-continuous AI agent operation where
  each clone agent: (a) possesses its own cryptographic identity (fresh
  Ed25519 key pair and DID URI); (b) produces signed session outputs
  attributable to the specific clone instance; (c) has usage metered per
  interaction in real time; and (d) can be cryptographically revoked by the
  licensor at any time, deactivating the clone's identity. No prior art
  licensing system teaches the combination of fresh-keypair clone spawning
  with W3C Verifiable Credential-based provenance.

### Alice/Mayo § 101 Eligibility Analysis

Software patent claims must satisfy the two-step Alice/Mayo test for patent
eligibility under 35 U.S.C. § 101. The claims are designed to satisfy both
steps as follows:

**Step 1 — Abstract Idea Analysis**: The claims are directed to specific
cryptographic operations implemented by specific algorithms (Ed25519 key
generation, SHA-256 Merkle hashing, Argon2id key derivation, XChaCha20-Poly1305
authenticated encryption) on specific data structures (W3C DID Documents,
W3C Verifiable Credentials with AI-specific fields, binary Merkle trees,
Argon2id-protected wallet records). The claims specify concrete technical
mechanisms rather than abstract goals.

**Step 2 — Inventive Concept**: The specific combination of elements in each
claim is inventive:

- *Claim 1*: The binding of AI agent behavioral attributes (capabilities,
  model version, purpose) to an Ed25519 key fingerprint within a W3C
  Verifiable Credential signed by a platform issuer DID is not a well-known,
  routine, or conventional combination. No prior art teaches this specific
  integration.

- *Claims 3-4*: The specific combination of Argon2id (128 MiB, 3 iterations)
  as KDF with XChaCha20-Poly1305 (192-bit nonce) as the encryption primitive
  for AI agent private key seeds, with a two-layer architecture (per-agent key
  derived from master key) and cross-device export via double-layer encryption,
  is not a conventional, well-understood, routine practice in the field.

- *Claims 5-7*: The fresh-keypair clone spawning protocol combined with
  W3C Verifiable Credential issuance for clone provenance and SHA-256-based
  deterministic license key generation is not a generic implementation of
  abstract licensing concepts — it is a specific technical method for which
  there is no prior art combination.

The claims recite specific algorithmic steps with concrete cryptographic
primitives, specific data structures, and specific technical outcomes
(tamper detection, cross-device portability, cryptographic provenance) that
improve the technical functioning of AI agent systems. This is analogous to
the Federal Circuit's treatment of cryptographic security claims in
*Enfish v. Microsoft* (Fed. Cir. 2016) and *McRO v. Bandai Namco* (Fed.
Cir. 2016), where claims directed to specific technical improvements to
computer systems (as opposed to abstract goals) were held patent-eligible.

---

## DRAWINGS (To Be Provided with Nonprovisional Application)

The following figures are described for the purpose of enabling the disclosure
and will be provided as formal drawings in the nonprovisional application:

**FIG. 1**: System architecture diagram showing the backend server, crypto
module, PostgreSQL database, wallet service, marketplace service, and their
interactions.

**FIG. 2**: Flow diagram for agent identity creation (Claim 1): CSPRNG →
Ed25519 KeyPair → Key Fingerprint → DID Document → Behavioral Fingerprint →
Verifiable Credential → Database storage.

**FIG. 3**: Merkle hash tree diagram (Claim 2): message sequence → leaf hash
computation (0x00 prefix) → binary tree construction → root → inclusion proof
path (O(log n)).

**FIG. 4**: Wallet architecture diagram (Claim 3): passphrase → Argon2id →
master key → per-agent XChaCha20-Poly1305 encryption → wallet_keys table →
export/import protocol.

**FIG. 5**: Clone marketplace flow diagram (Claims 5-7): listing creation →
purchase request → fresh keypair generation → capability copy → provenance
recording → VC issuance → license key generation → license record → usage
metering → revocation.

**FIG. 6**: Cryptographic provenance chain diagram: source agent DID → clone
agent DID → clone_of linkage → license record → listing record, with
verification path.

---

## SEQUENCE LISTING

Not applicable. The present application does not contain sequence listings
for nucleotide or amino acid sequences.

---

## CERTIFICATION

I hereby certify that the foregoing provisional patent application discloses
the subject matter of the invention in sufficient detail to enable a person
having ordinary skill in the art to make and use the invention as claimed.

Prepared by: [Inventor / Attorney / Agent]
Date: March 18, 2026

---

*END OF PROVISIONAL PATENT APPLICATION*

---

## FILING CHECKLIST (Pre-Submission)

- [ ] Complete inventor name(s) and residence(s)
- [ ] Determine small entity / micro entity status (fee reduction)
- [ ] File via USPTO EFS-Web / Patent Center
- [ ] Pay basic filing fee ($320 large / $160 small / $80 micro entity, 2024 rates)
- [ ] Receive filing receipt with Application Number and Filing Date
- [ ] Calendar nonprovisional deadline: **March 18, 2027**
- [ ] Retain copy of as-filed application with time-stamped receipt
- [ ] Consider PCT filing within 12 months for international coverage
  (PCT fee ~$4,500 + national phase fees in each target country)
- [ ] Engage registered patent attorney / agent for nonprovisional drafting
  and prosecution (recommended within 6 months of this filing)
- [ ] Conduct formal prior art search (USPTO, Espacenet, Google Patents)
  for behavioral fingerprint binding + AI agent identity + clone licensing
- [ ] Add formal drawings (FIGS. 1-6) per USPTO drawing requirements (37 CFR 1.84)
  before nonprovisional filing
