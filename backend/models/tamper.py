import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary, Integer, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum as py_enum
from .base import Base


class HeartbeatStatus(py_enum.Enum):
    alive = "alive"
    missed = "missed"
    killed = "killed"


class MessageSignature(Base):
    __tablename__ = "message_signatures"

    sig_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_hash: Mapped[str] = mapped_column(String(64), nullable=False)   # SHA-256 hex
    signature: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class MerkleCheckpoint(Base):
    __tablename__ = "merkle_checkpoints"

    checkpoint_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    merkle_root: Mapped[str] = mapped_column(String(64), nullable=False)
    leaf_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    heartbeat_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.agent_sessions.session_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[HeartbeatStatus] = mapped_column(
        Enum(HeartbeatStatus, name="heartbeat_status", schema="agentforge"), nullable=False
    )
    challenge: Mapped[str] = mapped_column(String(64), nullable=False)   # hex challenge issued by server
    response: Mapped[str | None] = mapped_column(String(128), nullable=True)   # hex signature from agent
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class KillSwitchEvent(Base):
    __tablename__ = "kill_switch_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class CertificateRevocation(Base):
    __tablename__ = "certificate_revocation_list"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    serial_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    revoked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("agentforge.users.id"), nullable=False)
