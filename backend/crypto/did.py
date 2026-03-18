"""
W3C Decentralized Identifier (DID) Document generation.

Standard: W3C DID Core 1.0 (https://www.w3.org/TR/did-core/)
Method: did:web (https://w3c-ccg.github.io/did-method-web/)
Key type: Ed25519VerificationKey2020

DID format: did:web:{domain}:agents:{uuid}
DID Document includes:
  - Ed25519VerificationKey2020 verification method
  - Authentication, assertionMethod, keyAgreement references
  - AgentForge custom service endpoint
"""

import json
import uuid as uuid_mod
from datetime import datetime, timezone
from .ed25519 import public_key_to_base64url


def generate_did(agent_uuid: str, domain: str = "agentforge.dev") -> str:
    """Generate a did:web DID URI for an agent."""
    return f"did:web:{domain}:agents:{agent_uuid}"


def create_did_document(
    agent_uuid: str,
    public_key: bytes,
    domain: str = "agentforge.dev",
    service_endpoint: str | None = None,
) -> dict:
    """
    Create a W3C DID Document for an agent.

    Args:
        agent_uuid: UUID of the agent (string)
        public_key: 32-byte Ed25519 public key
        domain: AgentForge domain (default: agentforge.dev)
        service_endpoint: Optional agent service endpoint URL

    Returns:
        DID Document as dict (serializable to JSON)
    """
    did = generate_did(agent_uuid, domain)
    key_id = f"{did}#key-1"
    pub_b64 = public_key_to_base64url(public_key)

    doc = {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": did,
        "controller": did,
        "verificationMethod": [
            {
                "id": key_id,
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyMultibase": "z" + _to_base58(public_key),  # multibase z = base58btc
            }
        ],
        "authentication": [key_id],
        "assertionMethod": [key_id],
        "keyAgreement": [key_id],
        "capabilityInvocation": [key_id],
        "capabilityDelegation": [key_id],
        "created": datetime.now(timezone.utc).isoformat(),
    }

    if service_endpoint:
        doc["service"] = [
            {
                "id": f"{did}#agent-service",
                "type": "AgentForgeService",
                "serviceEndpoint": service_endpoint,
            }
        ]

    return doc


def create_verifiable_credential(
    agent_uuid: str,
    did: str,
    issuer_did: str,
    display_name: str,
    agent_type: str,
    model_version: str,
    purpose: str,
    capabilities: list[str],
    public_key: bytes,
    signing_private_key: bytes,
) -> dict:
    """
    Create a W3C Verifiable Credential (birth certificate) for an agent.

    The VC is self-issued: issuer == subject == AgentForge platform DID.
    The proof uses Ed25519Signature2020.
    """
    import hashlib
    from .ed25519 import sign_message, public_key_to_base64url

    vc_id = f"https://{did.split(':')[2]}/credentials/{agent_uuid}"

    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
            "https://agentforge.dev/contexts/agent/v1",
        ],
        "type": ["VerifiableCredential", "AgentBirthCertificate"],
        "id": vc_id,
        "issuer": issuer_did,
        "issuanceDate": datetime.now(timezone.utc).isoformat(),
        "credentialSubject": {
            "id": did,
            "displayName": display_name,
            "agentType": agent_type,
            "modelVersion": model_version,
            "purpose": purpose,
            "capabilities": capabilities,
            "publicKeyMultibase": "z" + _to_base58(public_key),
        },
    }

    # Sign the credential
    credential_bytes = json.dumps(credential, sort_keys=True).encode()
    signature = sign_message(signing_private_key, credential_bytes)

    credential["proof"] = {
        "type": "Ed25519Signature2020",
        "created": datetime.now(timezone.utc).isoformat(),
        "verificationMethod": f"{issuer_did}#key-1",
        "proofPurpose": "assertionMethod",
        "proofValue": "z" + _to_base58(signature),
    }

    return credential


def verify_verifiable_credential(vc: dict, issuer_public_key: bytes) -> bool:
    """Verify the proof on a W3C Verifiable Credential."""
    from .ed25519 import verify_signature
    import copy

    vc_copy = copy.deepcopy(vc)
    proof = vc_copy.pop("proof", None)
    if not proof:
        return False

    proof_value_multibase = proof.get("proofValue", "")
    if not proof_value_multibase.startswith("z"):
        return False

    signature = _from_base58(proof_value_multibase[1:])
    credential_bytes = json.dumps(vc_copy, sort_keys=True).encode()
    return verify_signature(issuer_public_key, credential_bytes, signature)


# ── Base58 (Bitcoin alphabet) ─────────────────────────────────────────────────

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _to_base58(data: bytes) -> str:
    n = int.from_bytes(data, "big")
    result = ""
    while n > 0:
        n, r = divmod(n, 58)
        result = ALPHABET[r] + result
    # Add leading '1' chars for leading zero bytes
    for byte in data:
        if byte == 0:
            result = "1" + result
        else:
            break
    return result


def _from_base58(s: str) -> bytes:
    n = 0
    for char in s:
        n = n * 58 + ALPHABET.index(char)
    result = n.to_bytes((n.bit_length() + 7) // 8 or 1, "big")
    # Restore leading zero bytes
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + result
