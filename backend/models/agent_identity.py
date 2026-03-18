import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class AgentIdentity(Base):
    __tablename__ = "agent_identities"

    agent_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    did_uri: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, default="assistant")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    public_key: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    key_algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="ed25519")
    key_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    did_document: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    verifiable_credential: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    vc_signature: Mapped[bytes | None] = mapped_column(LargeBinary(64), nullable=True)
    behavioral_signature: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    preferred_runtime: Mapped[str] = mapped_column(String(32), nullable=False, default="nim")
    routing_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="agents")  # noqa: F821
    sessions: Mapped[list["AgentSession"]] = relationship(back_populates="agent", lazy="select")
    certificates: Mapped[list["AgentCertificate"]] = relationship(back_populates="agent", lazy="select")


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    merkle_root: Mapped[str | None] = mapped_column(String(64), nullable=True)

    agent: Mapped["AgentIdentity"] = relationship(back_populates="sessions")


class AgentCertificate(Base):
    __tablename__ = "agent_certificates"

    cert_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cert_der: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["AgentIdentity"] = relationship(back_populates="certificates")
