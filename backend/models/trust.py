import uuid
import enum as py_enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Float, Text, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class TrustLevel(py_enum.Enum):
    untrusted = "untrusted"     # Score < 20
    provisional = "provisional" # Score 20-39
    trusted = "trusted"         # Score 40-69
    verified = "verified"       # Score 70-89
    elite = "elite"             # Score 90-100


class SkillAuthType(py_enum.Enum):
    none = "none"
    api_key = "api_key"
    oauth2 = "oauth2"
    basic = "basic"


class AgentTrustProfile(Base):
    __tablename__ = "agent_trust_profiles"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"),
        primary_key=True,
    )
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    trust_level: Mapped[TrustLevel] = mapped_column(
        Enum(TrustLevel, name="trust_level_enum", schema="agentforge"),
        nullable=False,
        default=TrustLevel.provisional,
    )
    # Component scores (0-100 each)
    technical_trust: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    reliability_trust: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    security_trust: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    # Raw metrics
    tamper_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heartbeat_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heartbeat_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uptime_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    total_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_interactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Timestamps
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    agent: Mapped["AgentIdentity"] = relationship()  # noqa: F821


class SkillConnector(Base):
    __tablename__ = "skill_connectors"

    connector_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="utility")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    endpoint_url: Mapped[str] = mapped_column(String(512), nullable=False)
    auth_type: Mapped[SkillAuthType] = mapped_column(
        Enum(SkillAuthType, name="skill_auth_type_enum", schema="agentforge"),
        nullable=False,
        default=SkillAuthType.none,
    )
    # JSON Schema describing the skill's input/output
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    bindings: Mapped[list["AgentSkillBinding"]] = relationship(back_populates="connector", lazy="select")


class AgentSkillBinding(Base):
    __tablename__ = "agent_skill_bindings"
    __table_args__ = (
        UniqueConstraint("agent_id", "connector_id", name="uq_agent_skill"),
        {"schema": "agentforge"},
    )

    binding_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.skill_connectors.connector_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Scoped permissions for this agent's use of this skill
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    connector: Mapped["SkillConnector"] = relationship(back_populates="bindings")
    agent: Mapped["AgentIdentity"] = relationship()  # noqa: F821
