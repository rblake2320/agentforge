"""
Portability service — device registration, memory sync, session handoff.

Memory tiers:
  hot  — PostgreSQL, last 48h, full fidelity, sync every 30s
  warm — Vector-indexed, RAG searchable (pgvector placeholder)
  cold — Compressed archive

Session handoff protocol:
  1. Source device calls POST /portability/handoff → gets handoff_token
  2. Target device calls POST /portability/handoff/{id}/accept
  3. Encrypted state snapshot transferred
  4. Agent resumes on target with full context
"""

import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.portability import Device, AgentMemoryLayer, SessionHandoff, MemoryLayer, HandoffStatus
from ..models.agent_identity import AgentIdentity
from ..models.user import User
from ..crypto.vault import encrypt_key, decrypt_key


HANDOFF_TTL_MINUTES = 10


# ── Device Management ──────────────────────────────────────────────────────────

def register_device(
    db: Session,
    owner: User,
    device_name: str,
    device_type: str,
    device_fingerprint: str,
    public_key: bytes,
) -> Device:
    """Register a new device for a user."""
    existing = db.query(Device).filter_by(device_fingerprint=device_fingerprint).first()
    if existing:
        if existing.owner_id != owner.id:
            raise ValueError("Device fingerprint already registered to another user")
        # Update last_seen + public_key (re-registration)
        existing.last_seen = datetime.now(timezone.utc)
        existing.public_key = public_key
        existing.device_name = device_name
        db.commit()
        db.refresh(existing)
        return existing

    device = Device(
        owner_id=owner.id,
        device_name=device_name,
        device_type=device_type,
        device_fingerprint=device_fingerprint,
        public_key=public_key,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_devices(db: Session, owner: User) -> list[Device]:
    return db.query(Device).filter_by(owner_id=owner.id).order_by(Device.last_seen.desc()).all()


def get_device(db: Session, device_id: uuid.UUID, owner: User) -> Device:
    device = db.get(Device, device_id)
    if not device or device.owner_id != owner.id:
        raise ValueError("Device not found")
    return device


def touch_device(db: Session, device: Device) -> Device:
    """Update last_seen timestamp."""
    device.last_seen = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)
    return device


def deregister_device(db: Session, device: Device, owner: User) -> None:
    if device.owner_id != owner.id:
        raise ValueError("Not your device")
    db.delete(device)
    db.commit()


# ── Memory Layer CRUD ──────────────────────────────────────────────────────────

def write_memory(
    db: Session,
    agent: AgentIdentity,
    layer: str,
    content: bytes,
    passphrase: str,
    summary: str = "",
    priority: int = 5,
) -> AgentMemoryLayer:
    """Write an encrypted memory chunk to the specified layer."""
    mem_layer = MemoryLayer(layer)
    content_hash = hashlib.sha256(content).hexdigest()
    ciphertext, salt = encrypt_key(content, passphrase)

    mem = AgentMemoryLayer(
        agent_id=agent.agent_id,
        layer=mem_layer,
        content_enc=ciphertext + b"||" + salt,   # pack salt with ciphertext
        content_hash=content_hash,
        summary=summary,
        priority=priority,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return mem


def read_memory(
    db: Session,
    memory: AgentMemoryLayer,
    passphrase: str,
) -> bytes:
    """Decrypt and return memory content. Updates accessed_at."""
    raw = memory.content_enc
    sep = raw.find(b"||")
    if sep == -1:
        raise ValueError("Invalid memory encoding")
    ciphertext, salt = raw[:sep], raw[sep + 2:]
    content = decrypt_key(ciphertext, salt, passphrase)

    memory.accessed_at = datetime.now(timezone.utc)
    db.commit()
    return content


def list_memories(
    db: Session,
    agent: AgentIdentity,
    layer: str | None = None,
    limit: int = 50,
) -> list[AgentMemoryLayer]:
    q = db.query(AgentMemoryLayer).filter_by(agent_id=agent.agent_id)
    if layer:
        q = q.filter(AgentMemoryLayer.layer == MemoryLayer(layer))
    return q.order_by(AgentMemoryLayer.priority.desc(), AgentMemoryLayer.accessed_at.desc()).limit(limit).all()


def promote_memory(db: Session, memory: AgentMemoryLayer, new_layer: str) -> AgentMemoryLayer:
    """Promote memory to a hotter layer (cold → warm → hot)."""
    order = [MemoryLayer.cold, MemoryLayer.warm, MemoryLayer.hot]
    current_idx = order.index(memory.layer)
    target = MemoryLayer(new_layer)
    target_idx = order.index(target)
    if target_idx <= current_idx:
        raise ValueError(f"Can only promote to a hotter layer (current={memory.layer.value})")
    memory.layer = target
    memory.accessed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(memory)
    return memory


def evict_cold_memories(db: Session, agent: AgentIdentity, before_hours: int = 48) -> int:
    """Move hot memories older than threshold to warm layer."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=before_hours)
    stale = (
        db.query(AgentMemoryLayer)
        .filter(
            AgentMemoryLayer.agent_id == agent.agent_id,
            AgentMemoryLayer.layer == MemoryLayer.hot,
            AgentMemoryLayer.accessed_at < cutoff,
        )
        .all()
    )
    for mem in stale:
        mem.layer = MemoryLayer.warm
    db.commit()
    return len(stale)


def delete_memory(db: Session, memory: AgentMemoryLayer, owner: User) -> None:
    """Delete a memory entry."""
    agent = db.get(AgentIdentity, memory.agent_id)
    if not agent or agent.owner_id != owner.id:
        raise ValueError("Not your memory")
    db.delete(memory)
    db.commit()


# ── Session Handoff ────────────────────────────────────────────────────────────

def create_handoff(
    db: Session,
    agent: AgentIdentity,
    from_session_id: uuid.UUID | None,
    from_device_id: uuid.UUID | None,
    state_snapshot: bytes,
    passphrase: str,
) -> SessionHandoff:
    """
    Source device creates a handoff package.
    Returns handoff with one-time token — share with target device out-of-band.
    """
    token = "HO-" + secrets.token_urlsafe(32)
    encrypted_snapshot, salt = encrypt_key(state_snapshot, passphrase)
    packed = encrypted_snapshot + b"||" + salt

    handoff = SessionHandoff(
        agent_id=agent.agent_id,
        from_session_id=from_session_id,
        from_device_id=from_device_id,
        state_snapshot_enc=packed,
        handoff_token=token,
        status=HandoffStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=HANDOFF_TTL_MINUTES),
    )
    db.add(handoff)
    db.commit()
    db.refresh(handoff)
    return handoff


def accept_handoff(
    db: Session,
    token: str,
    to_device: Device,
    to_session_id: uuid.UUID | None,
    passphrase: str,
) -> tuple[SessionHandoff, bytes]:
    """
    Target device accepts handoff using one-time token.
    Returns (handoff record, decrypted state snapshot).
    """
    handoff = db.query(SessionHandoff).filter_by(handoff_token=token).first()
    if not handoff:
        raise ValueError("Handoff token not found")
    if handoff.status != HandoffStatus.pending:
        raise ValueError(f"Handoff is {handoff.status.value}")
    if datetime.now(timezone.utc) > handoff.expires_at:
        handoff.status = HandoffStatus.expired
        db.commit()
        raise ValueError("Handoff token has expired")

    # Decrypt snapshot
    raw = handoff.state_snapshot_enc
    sep = raw.find(b"||")
    if sep == -1:
        raise ValueError("Invalid handoff encoding")
    ciphertext, salt = raw[:sep], raw[sep + 2:]
    state_snapshot = decrypt_key(ciphertext, salt, passphrase)

    # Mark accepted
    handoff.status = HandoffStatus.accepted
    handoff.to_device_id = to_device.device_id
    handoff.to_session_id = to_session_id
    db.commit()
    db.refresh(handoff)

    return handoff, state_snapshot


def expire_stale_handoffs(db: Session) -> int:
    """Background task: expire handoffs past their TTL."""
    now = datetime.now(timezone.utc)
    stale = (
        db.query(SessionHandoff)
        .filter(
            SessionHandoff.status == HandoffStatus.pending,
            SessionHandoff.expires_at < now,
        )
        .all()
    )
    for h in stale:
        h.status = HandoffStatus.expired
    db.commit()
    return len(stale)


def list_handoffs(db: Session, agent: AgentIdentity, status: str | None = None) -> list[SessionHandoff]:
    q = db.query(SessionHandoff).filter_by(agent_id=agent.agent_id)
    if status:
        q = q.filter(SessionHandoff.status == HandoffStatus(status))
    return q.order_by(SessionHandoff.created_at.desc()).limit(50).all()
