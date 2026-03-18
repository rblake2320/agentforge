import uuid
import enum as py_enum
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary, Integer, Text, Enum, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class LicenseType(py_enum.Enum):
    perpetual = "perpetual"
    subscription = "subscription"
    per_use = "per_use"


class LicenseStatus(py_enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class PaymentStatus(py_enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class LicenseListing(Base):
    __tablename__ = "license_listings"

    listing_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    license_type: Mapped[LicenseType] = mapped_column(
        Enum(LicenseType, name="license_type_enum", schema="agentforge"), nullable=False
    )
    max_clones: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    terms: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    seller: Mapped["User"] = relationship()  # noqa: F821
    agent: Mapped["AgentIdentity"] = relationship()  # noqa: F821
    licenses: Mapped[list["License"]] = relationship(back_populates="listing", lazy="select")


class License(Base):
    __tablename__ = "licenses"

    license_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.license_listings.listing_id"), nullable=False, index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.users.id"), nullable=False, index=True
    )
    clone_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agentforge.agent_identities.agent_id"), nullable=True
    )
    license_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, name="license_status_enum", schema="agentforge"),
        nullable=False,
        default=LicenseStatus.active,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    listing: Mapped["LicenseListing"] = relationship(back_populates="licenses")
    buyer: Mapped["User"] = relationship()  # noqa: F821
    clone_agent: Mapped["AgentIdentity | None"] = relationship()  # noqa: F821
    usage_records: Mapped[list["LicenseUsageRecord"]] = relationship(back_populates="license", lazy="select")
    transactions: Mapped[list["PaymentTransaction"]] = relationship(back_populates="license", lazy="select")


class LicenseUsageRecord(Base):
    __tablename__ = "license_usage_records"

    record_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.licenses.license_id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    license: Mapped["License"] = relationship(back_populates="usage_records")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    tx_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agentforge.licenses.license_id"), nullable=False, index=True
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agentforge.users.id"), nullable=False)
    to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agentforge.users.id"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", schema="agentforge"),
        nullable=False,
        default=PaymentStatus.pending,
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    license: Mapped["License"] = relationship(back_populates="transactions")
