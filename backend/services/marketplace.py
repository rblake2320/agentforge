"""
Marketplace service — listings, licensing, clone mechanism.

Clone mechanism (PATENT TARGET):
  1. Buyer purchases a listing
  2. System spawns a new AgentIdentity with fresh Ed25519 keypair
  3. Clone copies capabilities/personality from source agent
  4. Clone is cryptographically linked to source via license record
  5. All clone usage tracked in license_usage_records
  6. Heartbeat + tamper active on clones from day 1
  7. Seller can revoke via license revocation (CRL update)
"""

import os
import uuid
import hashlib
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..models.agent_identity import AgentIdentity
from ..models.marketplace import (
    LicenseListing, License, LicenseUsageRecord, PaymentTransaction,
    LicenseType, LicenseStatus, PaymentStatus,
)
from ..models.user import User
from ..crypto.ed25519 import generate_keypair, fingerprint
from ..crypto.did import generate_did, create_did_document
from ..config import get_settings

settings = get_settings()

PLATFORM_FEE_PCT = 0.20   # 20% marketplace take rate


def create_listing(
    db: Session,
    agent: AgentIdentity,
    seller: User,
    title: str,
    description: str,
    price_cents: int,
    license_type: str,
    max_clones: int = 100,
    category: str = "general",
    tags: list[str] | None = None,
    terms: dict | None = None,
) -> LicenseListing:
    """List an agent on the marketplace."""
    listing = LicenseListing(
        agent_id=agent.agent_id,
        seller_id=seller.id,
        title=title,
        description=description,
        price_cents=price_cents,
        license_type=LicenseType(license_type),
        max_clones=max_clones,
        terms=terms or {},
        category=category,
        tags=tags or [],
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def browse_listings(
    db: Session,
    category: str | None = None,
    max_price_cents: int | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[LicenseListing], int]:
    """Browse active marketplace listings."""
    q = db.query(LicenseListing).filter(LicenseListing.is_active == True)
    if category:
        q = q.filter(LicenseListing.category == category)
    if max_price_cents is not None:
        q = q.filter(LicenseListing.price_cents <= max_price_cents)
    if search:
        q = q.filter(LicenseListing.title.ilike(f"%{search}%"))
    total = q.count()
    listings = q.order_by(LicenseListing.total_sales.desc()).offset(offset).limit(limit).all()
    return listings, total


def purchase_license(
    db: Session,
    listing: LicenseListing,
    buyer: User,
) -> tuple[License, AgentIdentity]:
    """
    Purchase a license — creates a cryptographically signed clone agent.

    PATENT TARGET: Clone mechanism with cryptographic provenance.
    The clone is a new agent identity linked to source via license record.
    """
    # Validate listing
    if not listing.is_active:
        raise ValueError("Listing is not active")
    if listing.total_sales >= listing.max_clones:
        raise ValueError("Maximum clones reached for this listing")
    if listing.seller_id == buyer.id:
        raise ValueError("Cannot purchase your own listing")

    # Generate clone agent — returns (AgentIdentity, private_key_bytes)
    clone_agent, clone_private_key = _spawn_clone(db, listing.agent, buyer)

    # Generate license key (deterministic from listing + buyer + clone)
    license_key = _generate_license_key(listing.listing_id, buyer.id, clone_agent.agent_id)

    # Determine expiry
    expires_at = None
    usage_limit = None
    if listing.license_type == LicenseType.subscription:
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    elif listing.license_type == LicenseType.per_use:
        usage_limit = 100   # default per-use limit

    license = License(
        listing_id=listing.listing_id,
        buyer_id=buyer.id,
        clone_agent_id=clone_agent.agent_id,
        license_key=license_key,
        status=LicenseStatus.active,
        starts_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        usage_limit=usage_limit,
    )
    db.add(license)
    db.flush()  # Materialise license_id before PaymentTransaction FK reference

    # Record payment transaction
    fee = int(listing.price_cents * PLATFORM_FEE_PCT)
    tx = PaymentTransaction(
        license_id=license.license_id,
        from_user_id=buyer.id,
        to_user_id=listing.seller_id,
        amount_cents=listing.price_cents,
        platform_fee_cents=fee,
        status=PaymentStatus.completed,   # Phase 4+: Stripe integration
    )
    db.add(tx)

    # Update listing stats
    listing.total_sales += 1
    db.commit()
    db.refresh(license)
    db.refresh(clone_agent)
    return license, (clone_agent, clone_private_key)


def _spawn_clone(db: Session, source: AgentIdentity, owner: User) -> AgentIdentity:
    """
    Create a new agent identity that is a clone of source.
    Fresh Ed25519 keypair — cryptographically distinct but capability-identical.
    """
    agent_uuid = str(uuid.uuid4())
    kp = generate_keypair()
    did_uri = generate_did(agent_uuid, settings.agentforge_domain)

    from ..crypto.did import create_verifiable_credential
    from ..services.identity import PLATFORM_DID, _get_platform_signing_key

    did_doc = create_did_document(agent_uuid, kp.public_key, settings.agentforge_domain)
    vc = create_verifiable_credential(
        agent_uuid=agent_uuid,
        did=did_uri,
        issuer_did=PLATFORM_DID,
        display_name=f"{source.display_name} (Licensed Clone)",
        agent_type=source.agent_type,
        model_version=source.model_version,
        purpose=source.purpose,
        capabilities=list(source.capabilities),
        public_key=kp.public_key,
        signing_private_key=_get_platform_signing_key(),
    )

    clone = AgentIdentity(
        agent_id=uuid.UUID(agent_uuid),
        owner_id=owner.id,
        did_uri=did_uri,
        display_name=f"{source.display_name} (Licensed)",
        agent_type=source.agent_type,
        model_version=source.model_version,
        purpose=source.purpose,
        capabilities=list(source.capabilities),
        public_key=kp.public_key,
        key_algorithm="ed25519",
        key_fingerprint=fingerprint(kp.public_key),
        did_document=did_doc,
        verifiable_credential=vc,
        vc_signature=None,
        behavioral_signature={"clone_of": str(source.agent_id), "created_at": datetime.now(timezone.utc).isoformat()},
        preferred_runtime=source.preferred_runtime,
        routing_config=dict(source.routing_config),
        is_active=True,
        is_public=False,
    )
    db.add(clone)
    db.flush()
    db.refresh(clone)
    return clone, kp.private_key


def _generate_license_key(listing_id: uuid.UUID, buyer_id: uuid.UUID, clone_id: uuid.UUID) -> str:
    """Generate a deterministic license key from the purchase components."""
    data = f"{listing_id}:{buyer_id}:{clone_id}:{os.urandom(16).hex()}"
    return "AFORGE-" + hashlib.sha256(data.encode()).hexdigest()[:32].upper()


def track_usage(db: Session, license: License, action: str, tokens: int = 0) -> LicenseUsageRecord:
    """Record a usage event against a license."""
    if license.usage_limit and license.usage_count >= license.usage_limit:
        raise ValueError("Usage limit exceeded")
    if license.expires_at and datetime.now(timezone.utc) > license.expires_at:
        raise ValueError("License has expired")
    if license.status != LicenseStatus.active:
        raise ValueError(f"License is {license.status.value}")

    license.usage_count += 1
    record = LicenseUsageRecord(
        license_id=license.license_id,
        action=action,
        tokens_consumed=tokens,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def revoke_license(db: Session, license: License, revoker: User) -> License:
    """Revoke a license (seller or admin only)."""
    listing = db.get(LicenseListing, license.listing_id)
    if not listing or listing.seller_id != revoker.id:
        raise ValueError("Only the seller can revoke a license")
    license.status = LicenseStatus.revoked
    # Deactivate clone agent
    if license.clone_agent_id:
        clone = db.get(AgentIdentity, license.clone_agent_id)
        if clone:
            clone.is_active = False
    db.commit()
    db.refresh(license)
    return license


def get_seller_revenue(db: Session, seller: User) -> dict:
    """Calculate seller revenue statistics."""
    listings = db.query(LicenseListing).filter_by(seller_id=seller.id).all()
    listing_ids = [l.listing_id for l in listings]
    licenses = db.query(License).filter(License.listing_id.in_(listing_ids)).all()
    transactions = db.query(PaymentTransaction).filter_by(to_user_id=seller.id).all()

    total_gross = sum(t.amount_cents for t in transactions if t.status == PaymentStatus.completed)
    total_fees = sum(t.platform_fee_cents for t in transactions if t.status == PaymentStatus.completed)
    total_net = total_gross - total_fees

    return {
        "listings": len(listings),
        "total_licenses": len(licenses),
        "active_licenses": len([l for l in licenses if l.status == LicenseStatus.active]),
        "total_gross_cents": total_gross,
        "total_fees_cents": total_fees,
        "total_net_cents": total_net,
        "total_gross_usd": total_gross / 100,
        "total_net_usd": total_net / 100,
    }
