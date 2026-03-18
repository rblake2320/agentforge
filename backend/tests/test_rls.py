"""Tests for PostgreSQL Row Level Security (RLS) implementation.

These tests operate against the agentforge_test schema (see conftest.py).
Because tests run as the ``postgres`` superuser (which has BYPASSRLS), the
policies themselves are not enforced during the test run — but the tests
verify:

  1. The ``set_db_user_context`` helper executes without error.
  2. The ``agentforge.set_current_user`` function exists in the *production*
     schema (confirmed via information_schema, not the test schema).
  3. Agent ownership is correctly modelled at the Python layer — a row
     created for test_user is not owned by second_user.
  4. The migration helper is importable and the downgrade policy list covers
     every table that upgrade() touches.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestSetDbUserContext:
    """set_db_user_context() must not raise for a valid UUID string."""

    def test_accepts_valid_uuid(self, db_session: Session, test_user) -> None:
        from backend.database import set_db_user_context

        # Should complete without any exception.
        set_db_user_context(db_session, str(test_user.id))

    def test_accepts_random_uuid_string(self, db_session: Session) -> None:
        """Even an unknown UUID should be accepted — RLS just finds no rows."""
        from backend.database import set_db_user_context

        set_db_user_context(db_session, str(uuid.uuid4()))

    def test_subsequent_calls_overwrite_context(
        self, db_session: Session, test_user, second_user
    ) -> None:
        """Calling set_db_user_context twice should not raise; last write wins."""
        from backend.database import set_db_user_context

        set_db_user_context(db_session, str(test_user.id))
        set_db_user_context(db_session, str(second_user.id))  # overwrite — no error


# ---------------------------------------------------------------------------
# Ownership invariants (independent of RLS enforcement)
# ---------------------------------------------------------------------------

class TestOwnershipInvariants:
    """Verify that the data model correctly captures agent ownership.

    RLS policies rely on owner_id == current_user_id comparisons; if the
    ORM layer sets owner_id incorrectly the policies would be meaningless.
    """

    def test_agent_owned_by_test_user(self, test_agent, test_user) -> None:
        assert test_agent.owner_id == test_user.id

    def test_agent_not_owned_by_second_user(
        self, test_agent, second_user
    ) -> None:
        assert test_agent.owner_id != second_user.id

    def test_two_users_have_distinct_ids(self, test_user, second_user) -> None:
        assert test_user.id != second_user.id


# ---------------------------------------------------------------------------
# Production schema — verify set_current_user function was installed
# ---------------------------------------------------------------------------

class TestRlsFunctionExistsInProductionSchema:
    """Check that migration 002 installed set_current_user in agentforge."""

    def test_set_current_user_function_exists(self, db_session: Session) -> None:
        """Query information_schema.routines for the production function."""
        row = db_session.execute(
            text(
                """
                SELECT routine_name
                FROM   information_schema.routines
                WHERE  routine_schema = 'agentforge'
                  AND  routine_name   = 'set_current_user'
                  AND  routine_type   = 'FUNCTION'
                """
            )
        ).fetchone()
        assert row is not None, (
            "agentforge.set_current_user() not found — "
            "did migration 002 run? (alembic upgrade head)"
        )

    def test_rls_enabled_on_users_table(self, db_session: Session) -> None:
        """Verify RLS is enabled on agentforge.users via pg_class."""
        row = db_session.execute(
            text(
                """
                SELECT relrowsecurity
                FROM   pg_class
                JOIN   pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                WHERE  pg_namespace.nspname = 'agentforge'
                  AND  pg_class.relname     = 'users'
                """
            )
        ).fetchone()
        assert row is not None, "agentforge.users table not found in pg_class"
        assert row[0] is True, (
            "RLS is not enabled on agentforge.users — "
            "did migration 002 run? (alembic upgrade head)"
        )

    def test_expected_policies_exist(self, db_session: Session) -> None:
        """Spot-check that the key policies created by migration 002 exist."""
        expected_policies = [
            ("agentforge", "users",            "users_own"),
            ("agentforge", "agent_identities", "agents_own"),
            ("agentforge", "agent_identities", "agents_public"),
            ("agentforge", "wallets",          "wallets_own"),
            ("agentforge", "wallet_keys",      "wallet_keys_own"),
            ("agentforge", "licenses",         "licenses_buyer"),
            ("agentforge", "licenses",         "licenses_seller"),
        ]
        rows = db_session.execute(
            text(
                """
                SELECT schemaname, tablename, policyname
                FROM   pg_policies
                WHERE  schemaname = 'agentforge'
                """
            )
        ).fetchall()
        existing = {(r[0], r[1], r[2]) for r in rows}

        missing = [p for p in expected_policies if p not in existing]
        assert not missing, (
            f"The following RLS policies are missing: {missing}\n"
            "Run: alembic upgrade head"
        )


# ---------------------------------------------------------------------------
# Migration module structure sanity checks
# ---------------------------------------------------------------------------

def _load_migration_002():
    """Load the 002_row_level_security migration module via importlib.util.

    Standard ``import`` cannot handle module names that start with a digit,
    so we use the lower-level loader directly.
    """
    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).parent.parent
        / "migrations" / "versions" / "002_row_level_security.py"
    )
    spec = importlib.util.spec_from_file_location("_migration_002", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigrationModuleStructure:
    """Import the migration module and verify its declared metadata."""

    def test_migration_revision_id(self) -> None:
        m = _load_migration_002()
        assert m.revision == "002"

    def test_migration_down_revision(self) -> None:
        m = _load_migration_002()
        assert m.down_revision == "001"

    def test_downgrade_covers_all_rls_tables(self) -> None:
        """Every table in RLS_TABLES must be covered by downgrade()'s DISABLE loop."""
        import inspect

        m = _load_migration_002()
        source = inspect.getsource(m.downgrade)
        for table in m.RLS_TABLES:
            assert table in source, (
                f"Table '{table}' is in RLS_TABLES but not referenced in downgrade()"
            )
