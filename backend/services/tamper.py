"""
Tamper detection service — message signing, Merkle checkpoints, heartbeat, kill switch.

Chain integrity model:
  Each message is signed with the agent's Ed25519 key.
  Messages are chained: each includes prev_hash (SHA-256 of previous message).
  Periodic Merkle checkpoints hash all messages in a session into a tree.
  Server-initiated heartbeat: server sends challenge, agent signs it.
  Kill switch: deactivates agent and broadcasts revocation.
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models.agent_identity import AgentIdentity, AgentSession
from ..models.tamper import MessageSignature, MerkleCheckpoint, Heartbeat, KillSwitchEvent, HeartbeatStatus
from ..models.user import User
from ..crypto.ed25519 import sign_message, verify_signature
from ..crypto.merkle import MerkleTree


def start_session(db: Session, agent: AgentIdentity) -> AgentSession:
    """Start a new tamper-tracked session for an agent."""
    session = AgentSession(agent_id=agent.agent_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def end_session(db: Session, session: AgentSession) -> AgentSession:
    """End a session and save the final Merkle root."""
    session.ended_at = datetime.now(timezone.utc)
    db.flush()
    # Compute final Merkle root from all session signatures
    sigs = (
        db.query(MessageSignature)
        .filter(MessageSignature.session_id == session.session_id)
        .order_by(MessageSignature.sequence_num)
        .all()
    )
    if sigs:
        tree = MerkleTree()
        for sig in sigs:
            tree.add_leaf(sig.message_hash.encode())
        root = tree.root
        session.merkle_root = root.hex() if root else None
    db.commit()
    db.refresh(session)
    return session


def sign_message_entry(
    db: Session,
    agent: AgentIdentity,
    session: AgentSession,
    message: bytes,
    private_key_seed: bytes,
) -> MessageSignature:
    """
    Sign a message and add it to the tamper-evident chain.
    Each entry includes the hash of the previous entry (chain linkage).
    """
    msg_hash = hashlib.sha256(message).hexdigest()

    # Get previous entry for chaining
    prev = (
        db.query(MessageSignature)
        .filter(MessageSignature.session_id == session.session_id)
        .order_by(MessageSignature.sequence_num.desc())
        .first()
    )
    prev_hash = prev.message_hash if prev else None
    seq_num = (prev.sequence_num + 1) if prev else 0

    # Sign: hash + prev_hash + sequence for binding to chain
    sign_payload = f"{msg_hash}:{prev_hash or 'genesis'}:{seq_num}".encode()
    sig = sign_message(private_key_seed, sign_payload)

    entry = MessageSignature(
        agent_id=agent.agent_id,
        session_id=session.session_id,
        message_hash=msg_hash,
        signature=sig,
        sequence_num=seq_num,
        prev_hash=prev_hash,
    )
    db.add(entry)

    # Increment session interaction count
    session.interaction_count += 1
    db.flush()

    # Create checkpoint every 10 messages
    if session.interaction_count % 10 == 0:
        _create_checkpoint(db, agent, session)

    db.commit()
    db.refresh(entry)
    return entry


def verify_message_entry(
    db: Session,
    sig_id: uuid.UUID,
    agent: AgentIdentity,
) -> bool:
    """Verify a specific signed message entry."""
    entry = db.get(MessageSignature, sig_id)
    if not entry or entry.agent_id != agent.agent_id:
        return False

    sign_payload = f"{entry.message_hash}:{entry.prev_hash or 'genesis'}:{entry.sequence_num}".encode()
    return verify_signature(agent.public_key, sign_payload, entry.signature)


def get_session_chain(db: Session, agent_id: uuid.UUID, session_id: uuid.UUID) -> list[dict]:
    """Return the full signature chain for a session."""
    entries = (
        db.query(MessageSignature)
        .filter(
            MessageSignature.agent_id == agent_id,
            MessageSignature.session_id == session_id,
        )
        .order_by(MessageSignature.sequence_num)
        .all()
    )
    return [
        {
            "sig_id": str(e.sig_id),
            "sequence_num": e.sequence_num,
            "message_hash": e.message_hash,
            "prev_hash": e.prev_hash,
            "signature": e.signature.hex(),
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


def verify_full_chain(db: Session, agent: AgentIdentity, session_id: uuid.UUID) -> dict:
    """Verify the entire signature chain for a session. Returns per-entry results."""
    entries = (
        db.query(MessageSignature)
        .filter(
            MessageSignature.agent_id == agent.agent_id,
            MessageSignature.session_id == session_id,
        )
        .order_by(MessageSignature.sequence_num)
        .all()
    )

    results = []
    prev_hash = None
    all_valid = True

    for entry in entries:
        # Check chain linkage
        chain_ok = entry.prev_hash == prev_hash
        # Verify signature
        sign_payload = f"{entry.message_hash}:{entry.prev_hash or 'genesis'}:{entry.sequence_num}".encode()
        sig_ok = verify_signature(agent.public_key, sign_payload, entry.signature)
        valid = chain_ok and sig_ok
        if not valid:
            all_valid = False
        results.append({
            "seq": entry.sequence_num,
            "chain_ok": chain_ok,
            "sig_ok": sig_ok,
            "valid": valid,
        })
        prev_hash = entry.message_hash

    return {"all_valid": all_valid, "entry_count": len(entries), "entries": results}


def _create_checkpoint(db: Session, agent: AgentIdentity, session: AgentSession) -> MerkleCheckpoint:
    """Create a Merkle tree checkpoint of all session messages so far."""
    sigs = (
        db.query(MessageSignature)
        .filter(MessageSignature.session_id == session.session_id)
        .order_by(MessageSignature.sequence_num)
        .all()
    )
    tree = MerkleTree()
    for s in sigs:
        tree.add_leaf(s.message_hash.encode())

    cp = MerkleCheckpoint(
        agent_id=agent.agent_id,
        session_id=session.session_id,
        merkle_root=tree.root.hex() if tree.root else "",
        leaf_count=len(sigs),
    )
    db.add(cp)
    db.flush()
    return cp


# ── Heartbeat ──────────────────────────────────────────────────────────────────

def issue_challenge(db: Session, agent: AgentIdentity, session_id: uuid.UUID | None = None) -> Heartbeat:
    """
    Server issues a random 32-byte challenge to the agent.
    Agent must sign it with its private key and call submit_challenge_response.
    """
    challenge = os.urandom(32).hex()
    hb = Heartbeat(
        agent_id=agent.agent_id,
        session_id=session_id,
        status=HeartbeatStatus.alive,
        challenge=challenge,
        verified=False,
    )
    db.add(hb)
    db.commit()
    db.refresh(hb)
    return hb


def submit_challenge_response(
    db: Session,
    heartbeat: Heartbeat,
    agent: AgentIdentity,
    response_signature_hex: str,
) -> bool:
    """
    Agent submits its signature of the challenge.
    Returns True if valid (agent proved identity), False otherwise.
    """
    challenge_bytes = bytes.fromhex(heartbeat.challenge)
    signature_bytes = bytes.fromhex(response_signature_hex)
    valid = verify_signature(agent.public_key, challenge_bytes, signature_bytes)

    heartbeat.response = response_signature_hex
    heartbeat.verified = valid
    heartbeat.status = HeartbeatStatus.alive if valid else HeartbeatStatus.missed
    db.commit()
    return valid


# ── Kill Switch ────────────────────────────────────────────────────────────────

def trigger_kill_switch(
    db: Session,
    agent: AgentIdentity,
    triggered_by: User,
    reason: str,
) -> KillSwitchEvent:
    """
    Immediately deactivate an agent.
    1. Mark agent inactive
    2. Record kill switch event
    3. (Phase 2+) Broadcast CRL update via WebSocket
    """
    agent.is_active = False

    event = KillSwitchEvent(
        agent_id=agent.agent_id,
        triggered_by=triggered_by.id,
        reason=reason,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_heartbeat_status(db: Session, agent_id: uuid.UUID) -> dict:
    """Get the latest heartbeat status for an agent."""
    latest = (
        db.query(Heartbeat)
        .filter(Heartbeat.agent_id == agent_id)
        .order_by(Heartbeat.created_at.desc())
        .first()
    )
    if not latest:
        return {"status": "no_heartbeats", "verified": False}
    return {
        "status": latest.status.value,
        "verified": latest.verified,
        "challenge": latest.challenge,
        "created_at": latest.created_at.isoformat(),
    }
