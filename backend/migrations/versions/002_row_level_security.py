"""Row Level Security for all sensitive agentforge tables.

Revision ID: 002
Revises: 001
Create Date: 2026-03-18

Enables PostgreSQL RLS on every sensitive table in the agentforge schema and
creates per-table policies that filter rows by the session variable
``agentforge.current_user_id`` (a UUID set at the start of every request).

The ``postgres`` superuser is granted BYPASSRLS so the backend service account
can still perform admin / migration operations without being filtered.

A helper function ``agentforge.set_current_user(uuid)`` is also installed so
application code and the SQLAlchemy dependency can set the context with a
single ``SELECT agentforge.set_current_user(:uid)`` call.
"""

from __future__ import annotations

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

SCHEMA = "agentforge"

# ---------------------------------------------------------------------------
# Tables that get RLS enabled (in dependency order)
# ---------------------------------------------------------------------------
RLS_TABLES = [
    "users",
    "agent_identities",
    "wallets",
    "wallet_keys",
    "devices",
    "memory_layers",
    "session_handoffs",
    "agent_trust_profiles",
    "agent_skill_bindings",
    "licenses",
    "license_usage_records",
]


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1.  Helper function — lets application code set the session variable
    #     with a clean SQL API instead of raw set_config() calls.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}.set_current_user(user_id uuid)
        RETURNS void AS $$
        BEGIN
            PERFORM set_config('agentforge.current_user_id', user_id::text, true);
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ------------------------------------------------------------------
    # 2.  Grant the postgres service account BYPASSRLS so migrations and
    #     admin tasks are never blocked by the policies below.
    # ------------------------------------------------------------------
    op.execute("ALTER USER postgres BYPASSRLS;")

    # ------------------------------------------------------------------
    # 3.  Enable RLS on every sensitive table.
    #     FORCE ROW LEVEL SECURITY is NOT set — table owners (postgres)
    #     already bypass via BYPASSRLS above.
    # ------------------------------------------------------------------
    for table in RLS_TABLES:
        op.execute(
            f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;"
        )

    # ------------------------------------------------------------------
    # 4.  Per-table policies
    # ------------------------------------------------------------------

    # --- users ---------------------------------------------------------
    # A user may only see and modify their own record.
    op.execute(
        f"""
        CREATE POLICY users_own ON {SCHEMA}.users
            USING (
                id = current_setting('agentforge.current_user_id', true)::uuid
            );
        """
    )

    # --- agent_identities ----------------------------------------------
    # Owners see / manage their own agents; public agents are visible to all.
    op.execute(
        f"""
        CREATE POLICY agents_own ON {SCHEMA}.agent_identities
            USING (
                owner_id = current_setting('agentforge.current_user_id', true)::uuid
            );
        """
    )
    op.execute(
        f"""
        CREATE POLICY agents_public ON {SCHEMA}.agent_identities
            FOR SELECT
            USING (is_public = true);
        """
    )

    # --- wallets -------------------------------------------------------
    # Owner-only access.
    op.execute(
        f"""
        CREATE POLICY wallets_own ON {SCHEMA}.wallets
            USING (
                owner_id = current_setting('agentforge.current_user_id', true)::uuid
            );
        """
    )

    # --- wallet_keys ---------------------------------------------------
    # Access granted through wallet ownership (subquery join).
    op.execute(
        f"""
        CREATE POLICY wallet_keys_own ON {SCHEMA}.wallet_keys
            USING (
                wallet_id IN (
                    SELECT wallet_id
                    FROM   {SCHEMA}.wallets
                    WHERE  owner_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- devices -------------------------------------------------------
    # Owner-only.
    op.execute(
        f"""
        CREATE POLICY devices_own ON {SCHEMA}.devices
            USING (
                owner_id = current_setting('agentforge.current_user_id', true)::uuid
            );
        """
    )

    # --- memory_layers -------------------------------------------------
    # Access through agent ownership.
    op.execute(
        f"""
        CREATE POLICY memory_own ON {SCHEMA}.memory_layers
            USING (
                agent_id IN (
                    SELECT agent_id
                    FROM   {SCHEMA}.agent_identities
                    WHERE  owner_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- session_handoffs ----------------------------------------------
    # Access through agent ownership.
    op.execute(
        f"""
        CREATE POLICY session_handoffs_own ON {SCHEMA}.session_handoffs
            USING (
                agent_id IN (
                    SELECT agent_id
                    FROM   {SCHEMA}.agent_identities
                    WHERE  owner_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- agent_trust_profiles ------------------------------------------
    # Trust profiles belong to agents which belong to users.
    op.execute(
        f"""
        CREATE POLICY trust_profiles_own ON {SCHEMA}.agent_trust_profiles
            USING (
                agent_id IN (
                    SELECT agent_id
                    FROM   {SCHEMA}.agent_identities
                    WHERE  owner_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- agent_skill_bindings ------------------------------------------
    # Bindings belong to agents which belong to users.
    op.execute(
        f"""
        CREATE POLICY skill_bindings_own ON {SCHEMA}.agent_skill_bindings
            USING (
                agent_id IN (
                    SELECT agent_id
                    FROM   {SCHEMA}.agent_identities
                    WHERE  owner_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- licenses ------------------------------------------------------
    # Buyers see their own licenses; sellers can SELECT licenses tied to
    # their listings.
    op.execute(
        f"""
        CREATE POLICY licenses_buyer ON {SCHEMA}.licenses
            USING (
                buyer_id = current_setting('agentforge.current_user_id', true)::uuid
            );
        """
    )
    op.execute(
        f"""
        CREATE POLICY licenses_seller ON {SCHEMA}.licenses
            FOR SELECT
            USING (
                listing_id IN (
                    SELECT listing_id
                    FROM   {SCHEMA}.license_listings
                    WHERE  seller_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )

    # --- license_usage_records -----------------------------------------
    # Access through license ownership (buyer side).
    op.execute(
        f"""
        CREATE POLICY license_usage_own ON {SCHEMA}.license_usage_records
            USING (
                license_id IN (
                    SELECT license_id
                    FROM   {SCHEMA}.licenses
                    WHERE  buyer_id = current_setting('agentforge.current_user_id', true)::uuid
                )
            );
        """
    )


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Drop policies in reverse creation order
    op.execute(f"DROP POLICY IF EXISTS license_usage_own    ON {SCHEMA}.license_usage_records;")
    op.execute(f"DROP POLICY IF EXISTS licenses_seller       ON {SCHEMA}.licenses;")
    op.execute(f"DROP POLICY IF EXISTS licenses_buyer        ON {SCHEMA}.licenses;")
    op.execute(f"DROP POLICY IF EXISTS skill_bindings_own    ON {SCHEMA}.agent_skill_bindings;")
    op.execute(f"DROP POLICY IF EXISTS trust_profiles_own    ON {SCHEMA}.agent_trust_profiles;")
    op.execute(f"DROP POLICY IF EXISTS session_handoffs_own  ON {SCHEMA}.session_handoffs;")
    op.execute(f"DROP POLICY IF EXISTS memory_own            ON {SCHEMA}.memory_layers;")
    op.execute(f"DROP POLICY IF EXISTS devices_own           ON {SCHEMA}.devices;")
    op.execute(f"DROP POLICY IF EXISTS wallet_keys_own       ON {SCHEMA}.wallet_keys;")
    op.execute(f"DROP POLICY IF EXISTS wallets_own           ON {SCHEMA}.wallets;")
    op.execute(f"DROP POLICY IF EXISTS agents_public         ON {SCHEMA}.agent_identities;")
    op.execute(f"DROP POLICY IF EXISTS agents_own            ON {SCHEMA}.agent_identities;")
    op.execute(f"DROP POLICY IF EXISTS users_own             ON {SCHEMA}.users;")

    # Disable RLS on every table
    for table in reversed(RLS_TABLES):
        op.execute(
            f"ALTER TABLE {SCHEMA}.{table} DISABLE ROW LEVEL SECURITY;"
        )

    # Remove the helper function
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}.set_current_user(uuid);")

    # Note: we intentionally do NOT revoke BYPASSRLS from postgres because
    # that privilege is a cluster-level superuser default; revoking it here
    # could break other tooling unexpectedly.
