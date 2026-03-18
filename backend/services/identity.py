"""
Agent identity service: birth, verify, manage.

Each "born" agent gets:
  1. Fresh Ed25519 keypair
  2. W3C DID Document (did:web format)
  3. W3C Verifiable Credential (birth certificate)
  4. Behavioral signature scaffold (populated over time)

Private key is returned ONCE at birth — caller must encrypt + store in wallet.
"""

import uuid
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.agent_identity import AgentIdentity
from ..models.user import User
from ..schemas.agent import AgentCreate
from ..crypto.ed25519 import generate_keypair, sign_message, verify_signature, fingerprint
from ..crypto.did import generate_did, create_did_document, create_verifiable_credential

settings = get_settings()

# Platform DID (self-issued credentials)
PLATFORM_DID = f"did:web:{settings.agentforge_domain}"


def birth_agent(
    db: Session,
    owner: User,
    data: AgentCreate,
) -> tuple[AgentIdentity, bytes]:
    """
    Create a new agent identity.

    Returns:
        (AgentIdentity ORM object, private_key_seed bytes)

    IMPORTANT: The private_key_seed is returned ONCE. The caller is responsible
    for encrypting it and storing it in the wallet. It is NOT stored in the database.
    """
    agent_uuid = str(uuid.uuid4())

    # Generate keypair
    keypair = generate_keypair()
    pub_key = keypair.public_key
    priv_key = keypair.private_key
    key_fp = fingerprint(pub_key)
    did_uri = generate_did(agent_uuid, settings.agentforge_domain)

    # Create W3C DID Document
    did_doc = create_did_document(
        agent_uuid=agent_uuid,
        public_key=pub_key,
        domain=settings.agentforge_domain,
        service_endpoint=f"https://{settings.agentforge_domain}/api/v1/agents/{agent_uuid}",
    )

    # Create W3C Verifiable Credential (birth certificate)
    # Platform signs with a platform key — for Phase 1 we derive a platform key from settings
    platform_key = _get_platform_signing_key()
    vc = create_verifiable_credential(
        agent_uuid=agent_uuid,
        did=did_uri,
        issuer_did=PLATFORM_DID,
        display_name=data.display_name,
        agent_type=data.agent_type,
        model_version=data.model_version,
        purpose=data.purpose,
        capabilities=data.capabilities,
        public_key=pub_key,
        signing_private_key=platform_key,
    )

    # Sign the VC with agent's own key as well (double-signed)
    vc_bytes = json.dumps(vc, sort_keys=True).encode()
    vc_sig = sign_message(priv_key, vc_bytes)

    # Initial behavioral signature (scaffold — enriched over time)
    behavioral_signature = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "fingerprint_type": "scaffold",
        "patterns": {},
    }

    agent = AgentIdentity(
        agent_id=uuid.UUID(agent_uuid),
        owner_id=owner.id,
        did_uri=did_uri,
        display_name=data.display_name,
        agent_type=data.agent_type,
        model_version=data.model_version,
        purpose=data.purpose,
        capabilities=data.capabilities,
        public_key=pub_key,
        key_algorithm="ed25519",
        key_fingerprint=key_fp,
        did_document=did_doc,
        verifiable_credential=vc,
        vc_signature=vc_sig,
        behavioral_signature=behavioral_signature,
        preferred_runtime=data.preferred_runtime,
        routing_config={},
        is_active=True,
        is_public=data.is_public,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Auto-initialize trust profile for new agent
    try:
        from .trust import calculate_trust_score
        calculate_trust_score(db, agent)
    except Exception:
        pass  # Trust profile creation is best-effort at birth

    return agent, priv_key


def get_agent(db: Session, agent_id: uuid.UUID, owner: User | None = None) -> AgentIdentity | None:
    """Fetch agent by ID. If owner is provided, enforce ownership."""
    agent = db.get(AgentIdentity, agent_id)
    if agent is None:
        return None
    if owner is not None and agent.owner_id != owner.id:
        return None
    return agent


def list_agents(db: Session, owner: User) -> list[AgentIdentity]:
    return (
        db.query(AgentIdentity)
        .filter(AgentIdentity.owner_id == owner.id, AgentIdentity.is_active == True)
        .order_by(AgentIdentity.created_at.desc())
        .all()
    )


def verify_agent_challenge(
    agent: AgentIdentity,
    challenge_hex: str,
    signature_hex: str,
) -> bool:
    """
    Verify a challenge-response proof of agent identity.
    The agent must sign the challenge bytes with its private key.
    """
    challenge_bytes = bytes.fromhex(challenge_hex)
    signature_bytes = bytes.fromhex(signature_hex)
    return verify_signature(agent.public_key, challenge_bytes, signature_bytes)


def deactivate_agent(db: Session, agent: AgentIdentity) -> AgentIdentity:
    agent.is_active = False
    db.commit()
    db.refresh(agent)
    return agent


def _get_platform_signing_key() -> bytes:
    """
    Get the platform signing key (Ed25519 seed).

    Phase 1: Derived from JWT private key PEM.
    Phase 2+: Stored in YubiHSM 2 / TPM-sealed vault.
    """
    import hashlib
    # Derive a signing key from the JWT private key material
    # In production this should be a separate HSM-backed key
    key_material = settings.jwt_private_key_pem.encode() or b"agentforge-platform-key-placeholder"
    return hashlib.sha256(key_material).digest()
