"""
Trust Engine — agent trust scoring and skill connector management.

Trust score = weighted average of:
  - technical_trust  (40%): tamper violations, signature integrity
  - reliability_trust (35%): heartbeat uptime, successful interactions
  - security_trust   (25%): key age, rotation compliance, kill switch events

Trust levels:
  untrusted:    0-19   (blocked from marketplace listings)
  provisional: 20-39   (new agents, limited marketplace access)
  trusted:     40-69   (standard access)
  verified:    70-89   (premium marketplace badge)
  elite:       90-100  (top-tier badge, reduced fees)
"""

import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.agent_identity import AgentIdentity
from ..models.trust import AgentTrustProfile, SkillConnector, AgentSkillBinding, TrustLevel, SkillAuthType
from ..models.tamper import Heartbeat, KillSwitchEvent, MessageSignature, HeartbeatStatus
from ..models.user import User

# Weights
W_TECHNICAL = 0.40
W_RELIABILITY = 0.35
W_SECURITY = 0.25


def _score_to_level(score: float) -> TrustLevel:
    if score >= 90:
        return TrustLevel.elite
    elif score >= 70:
        return TrustLevel.verified
    elif score >= 40:
        return TrustLevel.trusted
    elif score >= 20:
        return TrustLevel.provisional
    else:
        return TrustLevel.untrusted


def calculate_trust_score(db: Session, agent: AgentIdentity) -> AgentTrustProfile:
    """
    Recalculate trust scores from raw event data.
    Creates or updates the agent's trust profile.
    """
    # ── Technical Trust ────────────────────────────────────────────────────────
    # Based on: tamper violations (kill switches + missing signature links)
    kill_events = db.query(KillSwitchEvent).filter_by(agent_id=agent.agent_id).count()
    # Penalize heavily for kill switch events
    tamper_penalty = min(kill_events * 15, 80)
    technical_trust = max(0.0, 100.0 - tamper_penalty)

    # ── Reliability Trust ──────────────────────────────────────────────────────
    # Based on: heartbeat check ratio
    total_hb = db.query(Heartbeat).filter_by(agent_id=agent.agent_id).count()
    failed_hb = db.query(Heartbeat).filter(
        Heartbeat.agent_id == agent.agent_id,
        Heartbeat.status.in_([HeartbeatStatus.missed, HeartbeatStatus.killed]),
    ).count()
    if total_hb > 0:
        uptime_pct = ((total_hb - failed_hb) / total_hb) * 100.0
    else:
        uptime_pct = 100.0  # New agents start optimistic

    # Interaction success rate (placeholder — real system would track this)
    reliability_trust = uptime_pct

    # ── Security Trust ─────────────────────────────────────────────────────────
    # Key age penalty: keys older than 90 days without rotation get penalty
    from datetime import timezone
    key_age_days = (datetime.now(timezone.utc) - agent.created_at).days
    if key_age_days > 90:
        key_age_penalty = min((key_age_days - 90) * 0.5, 30)
    else:
        key_age_penalty = 0.0

    # Agent age bonus: established agents get slight boost
    age_bonus = min(key_age_days * 0.1, 10.0)

    security_trust = max(0.0, min(100.0, 80.0 + age_bonus - key_age_penalty))

    # ── Overall Score ──────────────────────────────────────────────────────────
    overall = (
        technical_trust * W_TECHNICAL
        + reliability_trust * W_RELIABILITY
        + security_trust * W_SECURITY
    )
    overall = round(max(0.0, min(100.0, overall)), 2)

    # ── Upsert Profile ─────────────────────────────────────────────────────────
    profile = db.get(AgentTrustProfile, agent.agent_id)
    if profile is None:
        profile = AgentTrustProfile(agent_id=agent.agent_id)
        db.add(profile)

    profile.overall_score = overall
    profile.trust_level = _score_to_level(overall)
    profile.technical_trust = round(technical_trust, 2)
    profile.reliability_trust = round(reliability_trust, 2)
    profile.security_trust = round(security_trust, 2)
    profile.tamper_violations = kill_events
    profile.heartbeat_checks = total_hb
    profile.heartbeat_failures = failed_hb
    profile.uptime_pct = round(uptime_pct, 2)
    profile.calculated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(profile)
    return profile


def get_trust_profile(db: Session, agent: AgentIdentity) -> AgentTrustProfile:
    """Get or create a trust profile (calculates on first access)."""
    profile = db.get(AgentTrustProfile, agent.agent_id)
    if profile is None:
        profile = calculate_trust_score(db, agent)
    return profile


def batch_recalculate(db: Session, owner: User | None = None) -> int:
    """
    Recalculate trust scores for all agents (or owner's agents).
    Returns count of profiles updated.
    """
    q = db.query(AgentIdentity).filter(AgentIdentity.is_active == True)
    if owner:
        q = q.filter(AgentIdentity.owner_id == owner.id)
    agents = q.all()
    for agent in agents:
        calculate_trust_score(db, agent)
    return len(agents)


# ── Skill Connector Management ─────────────────────────────────────────────────

def create_skill_connector(
    db: Session,
    name: str,
    category: str,
    description: str,
    endpoint_url: str,
    auth_type: str = "none",
    schema_definition: dict | None = None,
    is_public: bool = True,
    created_by: uuid.UUID | None = None,
) -> SkillConnector:
    """Register a new skill connector."""
    connector = SkillConnector(
        name=name,
        category=category,
        description=description,
        endpoint_url=endpoint_url,
        auth_type=SkillAuthType(auth_type),
        schema_definition=schema_definition or {},
        is_public=is_public,
        created_by=created_by,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def list_skill_connectors(
    db: Session,
    category: str | None = None,
    public_only: bool = True,
) -> list[SkillConnector]:
    q = db.query(SkillConnector)
    if public_only:
        q = q.filter(SkillConnector.is_public == True)
    if category:
        q = q.filter(SkillConnector.category == category)
    return q.order_by(SkillConnector.name).all()


def bind_skill(
    db: Session,
    agent: AgentIdentity,
    connector: SkillConnector,
    permissions: dict | None = None,
) -> AgentSkillBinding:
    """Bind a skill connector to an agent with scoped permissions."""
    existing = (
        db.query(AgentSkillBinding)
        .filter_by(agent_id=agent.agent_id, connector_id=connector.connector_id)
        .first()
    )
    if existing:
        existing.enabled = True
        existing.permissions = permissions or {}
        db.commit()
        db.refresh(existing)
        return existing

    binding = AgentSkillBinding(
        agent_id=agent.agent_id,
        connector_id=connector.connector_id,
        permissions=permissions or {},
        enabled=True,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return binding


def unbind_skill(db: Session, agent: AgentIdentity, connector: SkillConnector) -> None:
    binding = (
        db.query(AgentSkillBinding)
        .filter_by(agent_id=agent.agent_id, connector_id=connector.connector_id)
        .first()
    )
    if not binding:
        raise ValueError("Skill not bound to this agent")
    db.delete(binding)
    db.commit()


def list_agent_skills(db: Session, agent: AgentIdentity, enabled_only: bool = True) -> list[AgentSkillBinding]:
    q = db.query(AgentSkillBinding).filter_by(agent_id=agent.agent_id)
    if enabled_only:
        q = q.filter(AgentSkillBinding.enabled == True)
    return q.all()
