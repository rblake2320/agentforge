import uuid
import enum as py_enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary, Integer, Text, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class MemoryLayer(py_enum.Enum):
    hot = "hot"        # Last 48h, full fidelity
    warm = "warm"      # Vector-indexed, RAG searchable
    cold = "cold"      # Compressed archive


class HandoffStatus(py_enum.Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False, default="desktop")
    device_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AgentMemoryLayer(Base):
    __tablename__ = "memory_layers"

    memory_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    layer: Mapped[MemoryLayer] = mapped_column(
        Enum(MemoryLayer, name="memory_layer_enum", schema="agentforge"), nullable=False
    )
    content_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class SessionHandoff(Base):
    __tablename__ = "session_handoffs"

    handoff_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.agent_sessions.session_id"), nullable=True
    )
    to_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.agent_sessions.session_id"), nullable=True
    )
    from_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.devices.device_id"), nullable=True
    )
    to_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.devices.device_id"), nullable=True
    )
    state_snapshot_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    handoff_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[HandoffStatus] = mapped_column(
        Enum(HandoffStatus, name="handoff_status_enum", schema="agentforge"),
        nullable=False,
        default=HandoffStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
