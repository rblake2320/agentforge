"""Initial schema — all agentforge tables.

Revision ID: 001
Revises:
Create Date: 2026-03-18

Creates all tables in FK-dependency order inside the `agentforge` schema.
All PostgreSQL enum types are created explicitly before the tables that
use them, and dropped in reverse order on downgrade.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

SCHEMA = "agentforge"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _enum(*values: str, name: str) -> sa.Enum:
    """Return a schema-qualified sa.Enum ready for CREATE TYPE."""
    return sa.Enum(*values, name=name, schema=SCHEMA)


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # Ensure schema exists (idempotent; env.py also does this, but safe to repeat)
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ------------------------------------------------------------------
    # 1.  PostgreSQL ENUM types
    #     Must exist before any table column references them.
    # ------------------------------------------------------------------
    heartbeat_status = _enum("alive", "missed", "killed", name="heartbeat_status")
    heartbeat_status.create(op.get_bind(), checkfirst=True)

    license_type_enum = _enum("perpetual", "subscription", "per_use", name="license_type_enum")
    license_type_enum.create(op.get_bind(), checkfirst=True)

    license_status_enum = _enum("active", "expired", "revoked", name="license_status_enum")
    license_status_enum.create(op.get_bind(), checkfirst=True)

    payment_status_enum = _enum("pending", "completed", "failed", "refunded", name="payment_status_enum")
    payment_status_enum.create(op.get_bind(), checkfirst=True)

    memory_layer_enum = _enum("hot", "warm", "cold", name="memory_layer_enum")
    memory_layer_enum.create(op.get_bind(), checkfirst=True)

    handoff_status_enum = _enum("pending", "accepted", "expired", name="handoff_status_enum")
    handoff_status_enum.create(op.get_bind(), checkfirst=True)

    trust_level_enum = _enum(
        "untrusted", "provisional", "trusted", "verified", "elite",
        name="trust_level_enum",
    )
    trust_level_enum.create(op.get_bind(), checkfirst=True)

    skill_auth_type_enum = _enum("none", "api_key", "oauth2", "basic", name="skill_auth_type_enum")
    skill_auth_type_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 2.  agentforge.users  (no FK dependencies)
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        schema=SCHEMA,
    )
    op.create_index("ix_users_email", "users", ["email"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 3.  agentforge.agent_identities  (FK → users)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_identities",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("did_uri", sa.String(512), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False, server_default="assistant"),
        sa.Column("model_version", sa.String(128), nullable=False, server_default=""),
        sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("public_key", sa.LargeBinary(32), nullable=False),
        sa.Column("key_algorithm", sa.String(32), nullable=False, server_default="ed25519"),
        sa.Column("key_fingerprint", sa.String(64), nullable=False),
        sa.Column("did_document", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("verifiable_credential", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("vc_signature", sa.LargeBinary(64), nullable=True),
        sa.Column("behavioral_signature", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("preferred_runtime", sa.String(32), nullable=False, server_default="nim"),
        sa.Column("routing_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_agent_identities_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("did_uri", name="uq_agent_identities_did_uri"),
        sa.UniqueConstraint("key_fingerprint", name="uq_agent_identities_key_fingerprint"),
        sa.PrimaryKeyConstraint("agent_id", name="pk_agent_identities"),
        schema=SCHEMA,
    )
    op.create_index("ix_agent_identities_owner_id", "agent_identities", ["owner_id"], schema=SCHEMA)
    op.create_index("ix_agent_identities_did_uri", "agent_identities", ["did_uri"], schema=SCHEMA)
    op.create_index(
        "ix_agent_identities_key_fingerprint",
        "agent_identities",
        ["key_fingerprint"],
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 4.  agentforge.agent_sessions  (FK → agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("merkle_root", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_agent_sessions_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_agent_sessions"),
        schema=SCHEMA,
    )
    op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 5.  agentforge.agent_certificates  (FK → agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_certificates",
        sa.Column("cert_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cert_der", sa.LargeBinary(), nullable=False),
        sa.Column("serial_number", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_agent_certificates_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("serial_number", name="uq_agent_certificates_serial_number"),
        sa.PrimaryKeyConstraint("cert_id", name="pk_agent_certificates"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_certificates_agent_id", "agent_certificates", ["agent_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 6.  agentforge.wallets  (FK → users)
    # ------------------------------------------------------------------
    op.create_table(
        "wallets",
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("master_key_enc", sa.LargeBinary(), nullable=False),
        sa.Column("master_key_salt", sa.LargeBinary(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_wallets_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("owner_id", name="uq_wallets_owner_id"),
        sa.PrimaryKeyConstraint("wallet_id", name="pk_wallets"),
        schema=SCHEMA,
    )
    op.create_index("ix_wallets_owner_id", "wallets", ["owner_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 7.  agentforge.wallet_agents  (FK → wallets, agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "wallet_agents",
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            [f"{SCHEMA}.wallets.wallet_id"],
            name="fk_wallet_agents_wallet_id_wallets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_wallet_agents_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("wallet_id", "agent_id", name="uq_wallet_agents_wallet_id"),
        sa.PrimaryKeyConstraint("wallet_id", "agent_id", name="pk_wallet_agents"),
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 8.  agentforge.wallet_keys  (FK → wallets, agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "wallet_keys",
        sa.Column("key_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("private_key_enc", sa.LargeBinary(), nullable=False),
        sa.Column("key_salt", sa.LargeBinary(16), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            [f"{SCHEMA}.wallets.wallet_id"],
            name="fk_wallet_keys_wallet_id_wallets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_wallet_keys_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("key_id", name="pk_wallet_keys"),
        schema=SCHEMA,
    )
    op.create_index("ix_wallet_keys_wallet_id", "wallet_keys", ["wallet_id"], schema=SCHEMA)
    op.create_index("ix_wallet_keys_agent_id", "wallet_keys", ["agent_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 9.  agentforge.message_signatures  (FK → agent_identities, agent_sessions)
    # ------------------------------------------------------------------
    op.create_table(
        "message_signatures",
        sa.Column("sig_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.LargeBinary(64), nullable=False),
        sa.Column("sequence_num", sa.Integer(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_message_signatures_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            [f"{SCHEMA}.agent_sessions.session_id"],
            name="fk_message_signatures_session_id_agent_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("sig_id", name="pk_message_signatures"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_message_signatures_agent_id", "message_signatures", ["agent_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_message_signatures_session_id", "message_signatures", ["session_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 10. agentforge.merkle_checkpoints  (FK → agent_identities, agent_sessions)
    # ------------------------------------------------------------------
    op.create_table(
        "merkle_checkpoints",
        sa.Column("checkpoint_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merkle_root", sa.String(64), nullable=False),
        sa.Column("leaf_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_merkle_checkpoints_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            [f"{SCHEMA}.agent_sessions.session_id"],
            name="fk_merkle_checkpoints_session_id_agent_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("checkpoint_id", name="pk_merkle_checkpoints"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_merkle_checkpoints_agent_id", "merkle_checkpoints", ["agent_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_merkle_checkpoints_session_id", "merkle_checkpoints", ["session_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 11. agentforge.heartbeats  (FK → agent_identities, agent_sessions)
    # ------------------------------------------------------------------
    op.create_table(
        "heartbeats",
        sa.Column("heartbeat_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("alive", "missed", "killed", name="heartbeat_status", schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("challenge", sa.String(64), nullable=False),
        sa.Column("response", sa.String(128), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_heartbeats_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            [f"{SCHEMA}.agent_sessions.session_id"],
            name="fk_heartbeats_session_id_agent_sessions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("heartbeat_id", name="pk_heartbeats"),
        schema=SCHEMA,
    )
    op.create_index("ix_heartbeats_agent_id", "heartbeats", ["agent_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 12. agentforge.kill_switch_events  (FK → agent_identities, users)
    # ------------------------------------------------------------------
    op.create_table(
        "kill_switch_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_kill_switch_events_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by"],
            [f"{SCHEMA}.users.id"],
            name="fk_kill_switch_events_triggered_by_users",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_kill_switch_events"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_kill_switch_events_agent_id", "kill_switch_events", ["agent_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 13. agentforge.certificate_revocation_list  (FK → agent_identities, users)
    # ------------------------------------------------------------------
    op.create_table(
        "certificate_revocation_list",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("serial_number", sa.String(64), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_certificate_revocation_list_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"],
            [f"{SCHEMA}.users.id"],
            name="fk_certificate_revocation_list_revoked_by_users",
        ),
        sa.UniqueConstraint(
            "serial_number", name="uq_certificate_revocation_list_serial_number"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_certificate_revocation_list"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_certificate_revocation_list_serial_number",
        "certificate_revocation_list",
        ["serial_number"],
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 14. agentforge.license_listings  (FK → agent_identities, users)
    # ------------------------------------------------------------------
    op.create_table(
        "license_listings",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "license_type",
            sa.Enum(
                "perpetual", "subscription", "per_use",
                name="license_type_enum",
                schema=SCHEMA,
            ),
            nullable=False,
        ),
        sa.Column("max_clones", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("terms", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total_sales", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_license_listings_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_license_listings_seller_id_users",
        ),
        sa.PrimaryKeyConstraint("listing_id", name="pk_license_listings"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_license_listings_agent_id", "license_listings", ["agent_id"], schema=SCHEMA
    )
    op.create_index(
        "ix_license_listings_seller_id", "license_listings", ["seller_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 15. agentforge.licenses  (FK → license_listings, users, agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "licenses",
        sa.Column("license_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clone_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("license_key", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active", "expired", "revoked",
                name="license_status_enum",
                schema=SCHEMA,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            [f"{SCHEMA}.license_listings.listing_id"],
            name="fk_licenses_listing_id_license_listings",
        ),
        sa.ForeignKeyConstraint(
            ["buyer_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_licenses_buyer_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["clone_agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_licenses_clone_agent_id_agent_identities",
        ),
        sa.UniqueConstraint("license_key", name="uq_licenses_license_key"),
        sa.PrimaryKeyConstraint("license_id", name="pk_licenses"),
        schema=SCHEMA,
    )
    op.create_index("ix_licenses_listing_id", "licenses", ["listing_id"], schema=SCHEMA)
    op.create_index("ix_licenses_buyer_id", "licenses", ["buyer_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 16. agentforge.license_usage_records  (FK → licenses)
    # ------------------------------------------------------------------
    op.create_table(
        "license_usage_records",
        sa.Column("record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("license_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("tokens_consumed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "usage_extra_data", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["license_id"],
            [f"{SCHEMA}.licenses.license_id"],
            name="fk_license_usage_records_license_id_licenses",
        ),
        sa.PrimaryKeyConstraint("record_id", name="pk_license_usage_records"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_license_usage_records_license_id",
        "license_usage_records",
        ["license_id"],
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 17. agentforge.payment_transactions  (FK → licenses, users x2)
    # ------------------------------------------------------------------
    op.create_table(
        "payment_transactions",
        sa.Column("tx_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("license_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("platform_fee_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "completed", "failed", "refunded",
                name="payment_status_enum",
                schema=SCHEMA,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["license_id"],
            [f"{SCHEMA}.licenses.license_id"],
            name="fk_payment_transactions_license_id_licenses",
        ),
        sa.ForeignKeyConstraint(
            ["from_user_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_payment_transactions_from_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["to_user_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_payment_transactions_to_user_id_users",
        ),
        sa.PrimaryKeyConstraint("tx_id", name="pk_payment_transactions"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_payment_transactions_license_id",
        "payment_transactions",
        ["license_id"],
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 18. agentforge.devices  (FK → users)
    # ------------------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(64), nullable=False, server_default="desktop"),
        sa.Column("device_fingerprint", sa.String(128), nullable=False),
        sa.Column("public_key", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{SCHEMA}.users.id"],
            name="fk_devices_owner_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("device_fingerprint", name="uq_devices_device_fingerprint"),
        sa.PrimaryKeyConstraint("device_id", name="pk_devices"),
        schema=SCHEMA,
    )
    op.create_index("ix_devices_owner_id", "devices", ["owner_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 19. agentforge.memory_layers  (FK → agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "memory_layers",
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "layer",
            sa.Enum("hot", "warm", "cold", name="memory_layer_enum", schema=SCHEMA),
            nullable=False,
        ),
        sa.Column("content_enc", sa.LargeBinary(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_memory_layers_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("memory_id", name="pk_memory_layers"),
        schema=SCHEMA,
    )
    op.create_index("ix_memory_layers_agent_id", "memory_layers", ["agent_id"], schema=SCHEMA)

    # ------------------------------------------------------------------
    # 20. agentforge.session_handoffs
    #     (FK → agent_identities, agent_sessions x2, devices x2)
    # ------------------------------------------------------------------
    op.create_table(
        "session_handoffs",
        sa.Column("handoff_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("from_device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state_snapshot_enc", sa.LargeBinary(), nullable=False),
        sa.Column("handoff_token", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "accepted", "expired",
                name="handoff_status_enum",
                schema=SCHEMA,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_session_handoffs_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_session_id"],
            [f"{SCHEMA}.agent_sessions.session_id"],
            name="fk_session_handoffs_from_session_id_agent_sessions",
        ),
        sa.ForeignKeyConstraint(
            ["to_session_id"],
            [f"{SCHEMA}.agent_sessions.session_id"],
            name="fk_session_handoffs_to_session_id_agent_sessions",
        ),
        sa.ForeignKeyConstraint(
            ["from_device_id"],
            [f"{SCHEMA}.devices.device_id"],
            name="fk_session_handoffs_from_device_id_devices",
        ),
        sa.ForeignKeyConstraint(
            ["to_device_id"],
            [f"{SCHEMA}.devices.device_id"],
            name="fk_session_handoffs_to_device_id_devices",
        ),
        sa.UniqueConstraint("handoff_token", name="uq_session_handoffs_handoff_token"),
        sa.PrimaryKeyConstraint("handoff_id", name="pk_session_handoffs"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_session_handoffs_agent_id", "session_handoffs", ["agent_id"], schema=SCHEMA
    )

    # ------------------------------------------------------------------
    # 21. agentforge.agent_trust_profiles  (FK → agent_identities)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_trust_profiles",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("overall_score", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column(
            "trust_level",
            sa.Enum(
                "untrusted", "provisional", "trusted", "verified", "elite",
                name="trust_level_enum",
                schema=SCHEMA,
            ),
            nullable=False,
            server_default="provisional",
        ),
        sa.Column("technical_trust", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("reliability_trust", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("security_trust", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("tamper_violations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heartbeat_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heartbeat_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uptime_pct", sa.Float(), nullable=False, server_default="100.0"),
        sa.Column("total_interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_agent_trust_profiles_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id", name="pk_agent_trust_profiles"),
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 22. agentforge.skill_connectors  (FK → users, nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "skill_connectors",
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="utility"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("endpoint_url", sa.String(512), nullable=False),
        sa.Column(
            "auth_type",
            sa.Enum(
                "none", "api_key", "oauth2", "basic",
                name="skill_auth_type_enum",
                schema=SCHEMA,
            ),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "schema_definition", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            [f"{SCHEMA}.users.id"],
            name="fk_skill_connectors_created_by_users",
        ),
        sa.UniqueConstraint("name", name="uq_skill_connectors_name"),
        sa.PrimaryKeyConstraint("connector_id", name="pk_skill_connectors"),
        schema=SCHEMA,
    )

    # ------------------------------------------------------------------
    # 23. agentforge.agent_skill_bindings  (FK → agent_identities, skill_connectors)
    # ------------------------------------------------------------------
    op.create_table(
        "agent_skill_bindings",
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permissions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            [f"{SCHEMA}.agent_identities.agent_id"],
            name="fk_agent_skill_bindings_agent_id_agent_identities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            [f"{SCHEMA}.skill_connectors.connector_id"],
            name="fk_agent_skill_bindings_connector_id_skill_connectors",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "agent_id", "connector_id", name="uq_agent_skill"
        ),
        sa.PrimaryKeyConstraint("binding_id", name="pk_agent_skill_bindings"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_skill_bindings_agent_id",
        "agent_skill_bindings",
        ["agent_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_skill_bindings_connector_id",
        "agent_skill_bindings",
        ["connector_id"],
        schema=SCHEMA,
    )


# ---------------------------------------------------------------------------
# downgrade — drop in reverse dependency order, then enum types
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Tables — reverse order of creation
    op.drop_table("agent_skill_bindings", schema=SCHEMA)
    op.drop_table("skill_connectors", schema=SCHEMA)
    op.drop_table("agent_trust_profiles", schema=SCHEMA)
    op.drop_table("session_handoffs", schema=SCHEMA)
    op.drop_table("memory_layers", schema=SCHEMA)
    op.drop_table("devices", schema=SCHEMA)
    op.drop_table("payment_transactions", schema=SCHEMA)
    op.drop_table("license_usage_records", schema=SCHEMA)
    op.drop_table("licenses", schema=SCHEMA)
    op.drop_table("license_listings", schema=SCHEMA)
    op.drop_table("certificate_revocation_list", schema=SCHEMA)
    op.drop_table("kill_switch_events", schema=SCHEMA)
    op.drop_table("heartbeats", schema=SCHEMA)
    op.drop_table("merkle_checkpoints", schema=SCHEMA)
    op.drop_table("message_signatures", schema=SCHEMA)
    op.drop_table("wallet_keys", schema=SCHEMA)
    op.drop_table("wallet_agents", schema=SCHEMA)
    op.drop_table("wallets", schema=SCHEMA)
    op.drop_table("agent_certificates", schema=SCHEMA)
    op.drop_table("agent_sessions", schema=SCHEMA)
    op.drop_table("agent_identities", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)

    # Enum types — drop after tables that reference them
    bind = op.get_bind()
    sa.Enum(name="skill_auth_type_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="trust_level_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="handoff_status_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="memory_layer_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="payment_status_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="license_status_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="license_type_enum", schema=SCHEMA).drop(bind, checkfirst=True)
    sa.Enum(name="heartbeat_status", schema=SCHEMA).drop(bind, checkfirst=True)
