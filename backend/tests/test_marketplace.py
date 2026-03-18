"""
Marketplace service tests — listings, purchase/clone mechanism, license management.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from ..services import marketplace as svc
from ..models.marketplace import (
    LicenseListing, License, LicenseUsageRecord, PaymentTransaction,
    LicenseType, LicenseStatus, PaymentStatus,
)
from ..models.agent_identity import AgentIdentity


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _create_listing(db, agent, seller, **kwargs) -> LicenseListing:
    """Convenience wrapper around svc.create_listing with sensible defaults."""
    defaults = dict(
        title="Test Agent Pro",
        description="A capable test agent",
        price_cents=999,
        license_type="perpetual",
        max_clones=50,
        category="productivity",
        tags=["ai", "test"],
    )
    defaults.update(kwargs)
    return svc.create_listing(db, agent, seller, **defaults)


# ── Listings Tests ───────────────────────────────────────────────────────────────

class TestListings:
    def test_create_listing(self, db_session: Session, test_agent, test_user):
        listing = _create_listing(db_session, test_agent, test_user)

        assert listing.listing_id is not None
        assert listing.agent_id == test_agent.agent_id
        assert listing.seller_id == test_user.id
        assert listing.title == "Test Agent Pro"
        assert listing.description == "A capable test agent"
        assert listing.price_cents == 999
        assert listing.license_type == LicenseType.perpetual
        assert listing.max_clones == 50
        assert listing.category == "productivity"
        assert listing.tags == ["ai", "test"]
        assert listing.is_active is True
        assert listing.total_sales == 0

    def test_browse_listings_returns_active(self, db_session: Session, test_agent, test_user):
        _create_listing(db_session, test_agent, test_user, title="Agent A")
        _create_listing(db_session, test_agent, test_user, title="Agent B")

        listings, total = svc.browse_listings(db_session)
        titles = [l.title for l in listings]

        assert "Agent A" in titles
        assert "Agent B" in titles
        assert total >= 2

    def test_browse_filter_by_category(self, db_session: Session, test_agent, test_user):
        _create_listing(db_session, test_agent, test_user, title="Cat-Sec", category="security")
        _create_listing(db_session, test_agent, test_user, title="Cat-Gen", category="general")

        listings, total = svc.browse_listings(db_session, category="security")
        titles = [l.title for l in listings]

        assert "Cat-Sec" in titles
        assert "Cat-Gen" not in titles

    def test_browse_search_by_title(self, db_session: Session, test_agent, test_user):
        _create_listing(db_session, test_agent, test_user, title="Unique-XYZ-Agent")
        _create_listing(db_session, test_agent, test_user, title="Completely Different")

        listings, total = svc.browse_listings(db_session, search="Unique-XYZ")
        titles = [l.title for l in listings]

        assert "Unique-XYZ-Agent" in titles
        assert "Completely Different" not in titles

    def test_inactive_listing_hidden(self, db_session: Session, test_agent, test_user):
        active = _create_listing(db_session, test_agent, test_user, title="Active-Visible")
        inactive = _create_listing(db_session, test_agent, test_user, title="Inactive-Hidden")
        # Deactivate the second listing directly
        inactive.is_active = False
        db_session.commit()

        listings, _ = svc.browse_listings(db_session)
        titles = [l.title for l in listings]

        assert "Active-Visible" in titles
        assert "Inactive-Hidden" not in titles

    def test_max_price_filter(self, db_session: Session, test_agent, test_user):
        _create_listing(db_session, test_agent, test_user, title="Cheap-500", price_cents=500)
        _create_listing(db_session, test_agent, test_user, title="Pricey-5000", price_cents=5000)

        listings, _ = svc.browse_listings(db_session, max_price_cents=1000)
        titles = [l.title for l in listings]

        assert "Cheap-500" in titles
        assert "Pricey-5000" not in titles


# ── Purchase Tests ───────────────────────────────────────────────────────────────

class TestPurchase:
    def _purchase(self, db, agent, seller, buyer, **listing_kwargs):
        listing = _create_listing(db, agent, seller, **listing_kwargs)
        license_, (clone, _private_key) = svc.purchase_license(db, listing, buyer)
        return listing, license_, clone

    def test_purchase_creates_clone(self, db_session: Session, test_agent, test_user, second_user):
        _listing, _license, clone = self._purchase(db_session, test_agent, test_user, second_user)

        assert clone is not None
        assert clone.agent_id != test_agent.agent_id
        # Clone is owned by buyer
        assert clone.owner_id == second_user.id

    def test_clone_has_fresh_keypair(self, db_session: Session, test_agent, test_user, second_user):
        _listing, _license, clone = self._purchase(db_session, test_agent, test_user, second_user)

        assert clone.public_key != test_agent.public_key
        assert clone.key_fingerprint != test_agent.key_fingerprint

    def test_clone_linked_via_license(self, db_session: Session, test_agent, test_user, second_user):
        _listing, license_, clone = self._purchase(db_session, test_agent, test_user, second_user)

        assert license_.clone_agent_id == clone.agent_id

    def test_license_key_format(self, db_session: Session, test_agent, test_user, second_user):
        _listing, license_, _clone = self._purchase(db_session, test_agent, test_user, second_user)

        assert license_.license_key.startswith("AFORGE-")
        # Should have the prefix + 32 hex chars uppercase
        suffix = license_.license_key[len("AFORGE-"):]
        assert len(suffix) == 32
        assert suffix == suffix.upper()

    def test_cannot_buy_own_listing(self, db_session: Session, test_agent, test_user):
        listing = _create_listing(db_session, test_agent, test_user)

        with pytest.raises(ValueError, match="own listing"):
            svc.purchase_license(db_session, listing, test_user)

    def test_max_clones_enforced(self, db_session: Session, test_agent, test_user, second_user):
        listing = _create_listing(db_session, test_agent, test_user, max_clones=1)

        # First purchase should succeed
        svc.purchase_license(db_session, listing, second_user)

        # Refresh listing to get updated total_sales
        db_session.refresh(listing)
        assert listing.total_sales == 1

        # Second purchase should fail — max clones reached
        with pytest.raises(ValueError, match="Maximum clones"):
            svc.purchase_license(db_session, listing, second_user)

    def test_seller_revenue(self, db_session: Session, test_agent, test_user, second_user):
        listing = _create_listing(db_session, test_agent, test_user, price_cents=1000, max_clones=10)
        svc.purchase_license(db_session, listing, second_user)

        revenue = svc.get_seller_revenue(db_session, test_user)

        assert revenue["listings"] >= 1
        assert revenue["total_licenses"] >= 1
        assert revenue["active_licenses"] >= 1
        # Gross should equal the price paid
        assert revenue["total_gross_cents"] >= 1000
        # Net = gross - 20% fee = 800 cents for a 1000-cent sale
        expected_net = 1000 - int(1000 * svc.PLATFORM_FEE_PCT)
        assert revenue["total_net_cents"] >= expected_net
        assert revenue["total_fees_cents"] >= int(1000 * svc.PLATFORM_FEE_PCT)


# ── License Management Tests ─────────────────────────────────────────────────────

class TestLicenseManagement:
    def _setup(self, db, agent, seller, buyer, **listing_kwargs):
        """Create a listing + purchase, return (listing, license, clone)."""
        listing = _create_listing(db, agent, seller, max_clones=100, **listing_kwargs)
        license_, (clone, _pk) = svc.purchase_license(db, listing, buyer)
        return listing, license_, clone

    def test_track_usage(self, db_session: Session, test_agent, test_user, second_user):
        _listing, license_, _clone = self._setup(db_session, test_agent, test_user, second_user)
        initial_count = license_.usage_count

        svc.track_usage(db_session, license_, action="chat", tokens=50)
        db_session.refresh(license_)

        assert license_.usage_count == initial_count + 1

    def test_usage_limit_enforced(self, db_session: Session, test_agent, test_user, second_user):
        # per_use type gives a default limit of 100; override directly for the test
        listing = _create_listing(db_session, test_agent, test_user, max_clones=100)
        license_, (clone, _pk) = svc.purchase_license(db_session, listing, second_user)

        # Manually set a low usage_limit and max out the counter
        license_.usage_limit = 2
        license_.usage_count = 2
        db_session.commit()

        with pytest.raises(ValueError, match="Usage limit exceeded"):
            svc.track_usage(db_session, license_, action="chat")

    def test_expired_license_raises(self, db_session: Session, test_agent, test_user, second_user):
        listing = _create_listing(db_session, test_agent, test_user, max_clones=100)
        license_, (_clone, _pk) = svc.purchase_license(db_session, listing, second_user)

        # Artificially expire the license
        license_.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.commit()

        with pytest.raises(ValueError, match="expired"):
            svc.track_usage(db_session, license_, action="chat")

    def test_revoke_license(self, db_session: Session, test_agent, test_user, second_user):
        _listing, license_, clone = self._setup(db_session, test_agent, test_user, second_user)

        revoked = svc.revoke_license(db_session, license_, revoker=test_user)

        assert revoked.status == LicenseStatus.revoked
        # Clone agent should be deactivated
        db_session.refresh(clone)
        assert clone.is_active is False

    def test_only_seller_can_revoke(self, db_session: Session, test_agent, test_user, second_user):
        _listing, license_, _clone = self._setup(db_session, test_agent, test_user, second_user)

        # second_user is the buyer, not the seller — should be rejected
        with pytest.raises(ValueError, match="Only the seller"):
            svc.revoke_license(db_session, license_, revoker=second_user)
