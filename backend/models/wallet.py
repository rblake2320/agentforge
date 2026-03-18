import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary, Integer, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Wallet(Base):
    __tablename__ = "wallets"

    wallet_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    master_key_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    master_key_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    owner: Mapped["User"] = relationship()  # noqa: F821
    keys: Mapped[list["WalletKey"]] = relationship(back_populates="wallet", lazy="select")
    wallet_agents: Mapped[list["WalletAgent"]] = relationship(back_populates="wallet", lazy="select")


class WalletAgent(Base):
    __tablename__ = "wallet_agents"
    __table_args__ = (UniqueConstraint("wallet_id", "agent_id"),)

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.wallets.wallet_id", ondelete="CASCADE"), primary_key=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="wallet_agents")
    agent: Mapped["AgentIdentity"] = relationship()  # noqa: F821


class WalletKey(Base):
    __tablename__ = "wallet_keys"

    key_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.wallets.wallet_id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    private_key_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    wallet: Mapped["Wallet"] = relationship(back_populates="keys")
    agent: Mapped["AgentIdentity"] = relationship()  # noqa: F821
