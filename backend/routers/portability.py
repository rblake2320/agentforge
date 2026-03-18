"""
Portability router — device management, memory layers, session handoff.
"""

import uuid
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models.user import User
from ..models.agent_identity import AgentIdentity
from ..models.portability import Device, AgentMemoryLayer, SessionHandoff
from ..services import portability as svc

router = APIRouter(prefix="/api/v1/portability", tags=["portability"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class DeviceRegisterRequest(BaseModel):
    device_name: str = Field(..., max_length=255)
    device_type: str = Field(default="desktop", max_length=64)
    device_fingerprint: str = Field(..., max_length=128)
    public_key_hex: str = Field(..., description="Device Ed25519 public key as hex")


class DeviceOut(BaseModel):
    device_id: uuid.UUID
    device_name: str
    device_type: str
    device_fingerprint: str
    last_seen: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryWriteRequest(BaseModel):
    agent_id: uuid.UUID
    layer: Literal["hot", "warm", "cold"] = "hot"
    content_hex: str = Field(..., description="Memory content as hex-encoded bytes")
    passphrase: str
    summary: str = ""
    priority: int = Field(default=5, ge=1, le=10)


class MemoryOut(BaseModel):
    memory_id: uuid.UUID
    agent_id: uuid.UUID
    layer: str
    content_hash: str
    summary: str
    priority: int
    created_at: datetime
    accessed_at: datetime

    class Config:
        from_attributes = True


class MemoryReadRequest(BaseModel):
    passphrase: str


class HandoffCreateRequest(BaseModel):
    agent_id: uuid.UUID
    from_session_id: uuid.UUID | None = None
    from_device_id: uuid.UUID | None = None
    state_snapshot_hex: str = Field(..., description="Serialized agent state as hex")
    passphrase: str


class HandoffOut(BaseModel):
    handoff_id: uuid.UUID
    agent_id: uuid.UUID
    handoff_token: str
    status: str
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class HandoffAcceptRequest(BaseModel):
    token: str
    to_device_id: uuid.UUID
    to_session_id: uuid.UUID | None = None
    passphrase: str


# ── Device Endpoints ───────────────────────────────────────────────────────────

@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    req: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        public_key = bytes.fromhex(req.public_key_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid public_key_hex")
    device = svc.register_device(
        db, user, req.device_name, req.device_type, req.device_fingerprint, public_key
    )
    return device


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.list_devices(db, user)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def deregister_device(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        device = svc.get_device(db, device_id, user)
        svc.deregister_device(db, device, user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/devices/{device_id}/touch", response_model=DeviceOut)
def touch_device(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        device = svc.get_device(db, device_id, user)
        return svc.touch_device(db, device)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Memory Endpoints ───────────────────────────────────────────────────────────

def _get_agent(db: Session, agent_id: uuid.UUID, user: User) -> AgentIdentity:
    agent = db.get(AgentIdentity, agent_id)
    if not agent or agent.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/memory", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def write_memory(
    req: MemoryWriteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, req.agent_id, user)
    try:
        content = bytes.fromhex(req.content_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid content_hex")
    mem = svc.write_memory(db, agent, req.layer, content, req.passphrase, req.summary, req.priority)
    return mem


@router.get("/memory/{agent_id}", response_model=list[MemoryOut])
def list_memories(
    agent_id: uuid.UUID,
    layer: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    return svc.list_memories(db, agent, layer)


@router.post("/memory/{memory_id}/read")
def read_memory(
    memory_id: uuid.UUID,
    req: MemoryReadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = db.get(AgentMemoryLayer, memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    agent = _get_agent(db, mem.agent_id, user)
    try:
        content = svc.read_memory(db, mem, req.passphrase)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")
    return {"memory_id": str(memory_id), "content_hex": content.hex(), "layer": mem.layer.value}


@router.post("/memory/{memory_id}/promote", response_model=MemoryOut)
def promote_memory(
    memory_id: uuid.UUID,
    new_layer: Literal["hot", "warm", "cold"],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = db.get(AgentMemoryLayer, memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    _get_agent(db, mem.agent_id, user)
    try:
        return svc.promote_memory(db, mem, new_layer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/memory/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = db.get(AgentMemoryLayer, memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    try:
        svc.delete_memory(db, mem, user)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── Handoff Endpoints ──────────────────────────────────────────────────────────

@router.post("/handoff", response_model=HandoffOut, status_code=status.HTTP_201_CREATED)
def create_handoff(
    req: HandoffCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, req.agent_id, user)
    try:
        snapshot = bytes.fromhex(req.state_snapshot_hex)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state_snapshot_hex")
    handoff = svc.create_handoff(
        db, agent, req.from_session_id, req.from_device_id, snapshot, req.passphrase
    )
    return handoff


@router.post("/handoff/accept")
def accept_handoff(
    req: HandoffAcceptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    to_device = db.get(Device, req.to_device_id)
    if not to_device or to_device.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Target device not found")
    try:
        handoff, snapshot = svc.accept_handoff(
            db, req.token, to_device, req.to_session_id, req.passphrase
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "handoff_id": str(handoff.handoff_id),
        "status": handoff.status.value,
        "state_snapshot_hex": snapshot.hex(),
        "agent_id": str(handoff.agent_id),
    }


@router.get("/handoff/{agent_id}", response_model=list[HandoffOut])
def list_handoffs(
    agent_id: uuid.UUID,
    handoff_status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    try:
        return svc.list_handoffs(db, agent, handoff_status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
