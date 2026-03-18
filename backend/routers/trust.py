"""
Trust Engine router — trust scores, skill connectors, skill bindings.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..models.user import User
from ..models.agent_identity import AgentIdentity
from ..models.trust import SkillConnector, AgentSkillBinding
from ..services import trust as svc

router = APIRouter(prefix="/api/v1/trust", tags=["trust"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class TrustProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: uuid.UUID
    overall_score: float
    trust_level: str
    technical_trust: float
    reliability_trust: float
    security_trust: float
    tamper_violations: int
    heartbeat_checks: int
    heartbeat_failures: int
    uptime_pct: float
    calculated_at: datetime


class SkillConnectorCreate(BaseModel):
    name: str = Field(..., max_length=128)
    category: str = Field(default="utility", max_length=64)
    description: str = ""
    endpoint_url: str = Field(..., max_length=512)
    auth_type: str = "none"
    schema_definition: dict = {}
    is_public: bool = True


class SkillConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    connector_id: uuid.UUID
    name: str
    category: str
    description: str
    endpoint_url: str
    auth_type: str
    is_public: bool
    created_at: datetime


class SkillBindRequest(BaseModel):
    connector_id: uuid.UUID
    permissions: dict = {}


class SkillBindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    binding_id: uuid.UUID
    agent_id: uuid.UUID
    connector_id: uuid.UUID
    permissions: dict
    enabled: bool
    created_at: datetime


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_agent(db: Session, agent_id: uuid.UUID, user: User) -> AgentIdentity:
    agent = db.get(AgentIdentity, agent_id)
    if not agent or agent.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── Trust Endpoints ────────────────────────────────────────────────────────────

@router.get("/profile/{agent_id}", response_model=TrustProfileOut)
def get_trust_profile(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    profile = svc.get_trust_profile(db, agent)
    # Serialize trust_level as string value
    out = TrustProfileOut(
        agent_id=profile.agent_id,
        overall_score=profile.overall_score,
        trust_level=profile.trust_level.value,
        technical_trust=profile.technical_trust,
        reliability_trust=profile.reliability_trust,
        security_trust=profile.security_trust,
        tamper_violations=profile.tamper_violations,
        heartbeat_checks=profile.heartbeat_checks,
        heartbeat_failures=profile.heartbeat_failures,
        uptime_pct=profile.uptime_pct,
        calculated_at=profile.calculated_at,
    )
    return out


@router.post("/profile/{agent_id}/recalculate", response_model=TrustProfileOut)
def recalculate_trust(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    profile = svc.calculate_trust_score(db, agent)
    return TrustProfileOut(
        agent_id=profile.agent_id,
        overall_score=profile.overall_score,
        trust_level=profile.trust_level.value,
        technical_trust=profile.technical_trust,
        reliability_trust=profile.reliability_trust,
        security_trust=profile.security_trust,
        tamper_violations=profile.tamper_violations,
        heartbeat_checks=profile.heartbeat_checks,
        heartbeat_failures=profile.heartbeat_failures,
        uptime_pct=profile.uptime_pct,
        calculated_at=profile.calculated_at,
    )


# ── Skill Connector Endpoints ──────────────────────────────────────────────────

@router.post("/skills/connectors", response_model=SkillConnectorOut, status_code=status.HTTP_201_CREATED)
def create_connector(
    req: SkillConnectorCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        connector = svc.create_skill_connector(
            db,
            name=req.name,
            category=req.category,
            description=req.description,
            endpoint_url=req.endpoint_url,
            auth_type=req.auth_type,
            schema_definition=req.schema_definition,
            is_public=req.is_public,
            created_by=user.id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SkillConnectorOut(
        connector_id=connector.connector_id,
        name=connector.name,
        category=connector.category,
        description=connector.description,
        endpoint_url=connector.endpoint_url,
        auth_type=connector.auth_type.value,
        is_public=connector.is_public,
        created_at=connector.created_at,
    )


@router.get("/skills/connectors", response_model=list[SkillConnectorOut])
def list_connectors(
    category: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    connectors = svc.list_skill_connectors(db, category=category)
    return [
        SkillConnectorOut(
            connector_id=c.connector_id,
            name=c.name,
            category=c.category,
            description=c.description,
            endpoint_url=c.endpoint_url,
            auth_type=c.auth_type.value,
            is_public=c.is_public,
            created_at=c.created_at,
        )
        for c in connectors
    ]


@router.post("/skills/bind/{agent_id}", response_model=SkillBindingOut, status_code=status.HTTP_201_CREATED)
def bind_skill(
    agent_id: uuid.UUID,
    req: SkillBindRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    connector = db.get(SkillConnector, req.connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    binding = svc.bind_skill(db, agent, connector, req.permissions)
    return binding


@router.delete("/skills/bind/{agent_id}/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def unbind_skill(
    agent_id: uuid.UUID,
    connector_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    connector = db.get(SkillConnector, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    try:
        svc.unbind_skill(db, agent, connector)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/skills/{agent_id}", response_model=list[SkillBindingOut])
def list_agent_skills(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _get_agent(db, agent_id, user)
    return svc.list_agent_skills(db, agent)
