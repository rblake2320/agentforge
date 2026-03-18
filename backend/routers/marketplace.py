"""
Marketplace endpoints.

GET  /api/v1/marketplace/listings                     — Browse listings
POST /api/v1/marketplace/listings                     — Create listing
GET  /api/v1/marketplace/listings/{id}                — Listing detail
POST /api/v1/marketplace/listings/{id}/purchase       — Purchase → spawn clone
GET  /api/v1/marketplace/licenses                     — My purchased licenses
DELETE /api/v1/marketplace/licenses/{id}              — Revoke (seller only)
GET  /api/v1/marketplace/revenue                      — Seller revenue dashboard
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..deps import CurrentUser, DbDep
from ..services.marketplace import (
    create_listing, browse_listings, purchase_license,
    revoke_license, get_seller_revenue, track_usage,
)
from ..services.identity import get_agent
from ..models.marketplace import LicenseListing, License

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


class CreateListingRequest(BaseModel):
    agent_id: uuid.UUID
    title: str
    description: str = ""
    price_cents: int = 0
    license_type: str = "perpetual"
    max_clones: int = 100
    category: str = "general"
    tags: list[str] = []
    terms: dict = {}


class ListingOut(BaseModel):
    listing_id: uuid.UUID
    agent_id: uuid.UUID
    seller_id: uuid.UUID
    title: str
    description: str
    price_cents: float
    license_type: str
    max_clones: int
    category: str
    tags: list
    total_sales: int
    is_active: bool
    created_at: datetime

    @classmethod
    def from_orm(cls, listing: LicenseListing) -> "ListingOut":
        return cls(
            listing_id=listing.listing_id,
            agent_id=listing.agent_id,
            seller_id=listing.seller_id,
            title=listing.title,
            description=listing.description,
            price_cents=listing.price_cents,
            license_type=listing.license_type.value,
            max_clones=listing.max_clones,
            category=listing.category,
            tags=listing.tags,
            total_sales=listing.total_sales,
            is_active=listing.is_active,
            created_at=listing.created_at,
        )


class PurchaseResponse(BaseModel):
    license_id: uuid.UUID
    license_key: str
    clone_agent_id: uuid.UUID
    clone_private_key_hex: str
    expires_at: datetime | None
    warning: str = "Store clone private key securely. It will not be shown again."


@router.get("/listings", response_model=dict)
def list_marketplace(
    current_user: CurrentUser,
    db: DbDep,
    category: str | None = Query(None),
    max_price: int | None = Query(None),
    search: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    listings, total = browse_listings(db, category, max_price, search, offset, limit)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "listings": [ListingOut.from_orm(l).model_dump() for l in listings],
    }


@router.post("/listings", response_model=ListingOut, status_code=201)
def create_marketplace_listing(body: CreateListingRequest, current_user: CurrentUser, db: DbDep):
    agent = get_agent(db, body.agent_id, current_user)
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not agent.is_active:
        raise HTTPException(400, "Cannot list an inactive agent")
    valid_types = {"perpetual", "subscription", "per_use"}
    if body.license_type not in valid_types:
        raise HTTPException(422, f"license_type must be one of {valid_types}")
    listing = create_listing(
        db, agent, current_user,
        title=body.title,
        description=body.description,
        price_cents=body.price_cents,
        license_type=body.license_type,
        max_clones=body.max_clones,
        category=body.category,
        tags=body.tags,
        terms=body.terms,
    )
    return ListingOut.from_orm(listing)


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    listing = db.get(LicenseListing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return ListingOut.from_orm(listing)


@router.post("/listings/{listing_id}/purchase", response_model=PurchaseResponse, status_code=201)
def purchase(listing_id: uuid.UUID, current_user: CurrentUser, db: DbDep):
    listing = db.get(LicenseListing, listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    try:
        license, (clone_agent, clone_private_key) = purchase_license(db, listing, current_user)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return PurchaseResponse(
        license_id=license.license_id,
        license_key=license.license_key,
        clone_agent_id=clone_agent.agent_id,
        clone_private_key_hex=clone_private_key.hex(),
        expires_at=license.expires_at,
    )


@router.get("/licenses", response_model=list[dict])
def my_licenses(current_user: CurrentUser, db: DbDep) -> list[dict]:
    licenses = db.query(License).filter_by(buyer_id=current_user.id).all()
    return [
        {
            "license_id": str(l.license_id),
            "listing_id": str(l.listing_id),
            "clone_agent_id": str(l.clone_agent_id),
            "license_key": l.license_key,
            "status": l.status.value,
            "usage_count": l.usage_count,
            "usage_limit": l.usage_limit,
            "expires_at": l.expires_at.isoformat() if l.expires_at else None,
            "created_at": l.created_at.isoformat(),
        }
        for l in licenses
    ]


@router.delete("/licenses/{license_id}", status_code=204)
def revoke(license_id: uuid.UUID, current_user: CurrentUser, db: DbDep) -> None:
    license = db.get(License, license_id)
    if not license:
        raise HTTPException(404, "License not found")
    try:
        revoke_license(db, license, current_user)
    except ValueError as e:
        raise HTTPException(403, str(e))


@router.get("/revenue", response_model=dict)
def revenue_dashboard(current_user: CurrentUser, db: DbDep) -> dict:
    return get_seller_revenue(db, current_user)
