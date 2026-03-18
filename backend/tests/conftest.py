"""
Test configuration and fixtures.

Uses the real PostgreSQL agentvault database (test schema: agentforge_test).
Requires running PostgreSQL on localhost:5432.
"""

import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.models import Base, SCHEMA
from backend.models.user import User
from backend.models.agent_identity import AgentIdentity
from backend.database import get_db
from backend.main import app
from backend.crypto.ed25519 import generate_keypair, fingerprint
from backend.crypto.did import generate_did, create_did_document, create_verifiable_credential
from backend.services.identity import PLATFORM_DID, _get_platform_signing_key

# Use the same PostgreSQL instance but a test-specific schema
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:%3FBooker78%21@localhost:5432/agentvault",
)
TEST_SCHEMA = "agentforge_test"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, pool_pre_ping=True)
    with eng.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
    # Temporarily override schema to test schema
    original_schema = Base.metadata.schema
    Base.metadata.schema = TEST_SCHEMA
    for table in Base.metadata.tables.values():
        table.schema = TEST_SCHEMA
    # Also fix FKs by recreating — just create_all with new schema
    Base.metadata.create_all(eng)
    yield eng
    # Cleanup: drop the test schema first (CASCADE handles all tables + dependencies),
    # then attempt drop_all to clean up any schema-level objects (best-effort).
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
    try:
        Base.metadata.drop_all(eng)
    except Exception:
        pass  # Cross-schema enum types (e.g. agentforge.heartbeat_status) may linger — OK
    Base.metadata.schema = original_schema
    for table in Base.metadata.tables.values():
        table.schema = original_schema


@pytest.fixture(scope="function")
def db_session(engine):
    """
    Per-test database session using SAVEPOINT pattern.

    When the service under test calls db.commit(), it releases a SAVEPOINT but
    does NOT commit to the real DB — the outer transaction absorbs it.
    Rolling back the outer transaction at teardown undoes ALL changes, including
    committed data from within the service, keeping tests fully isolated.
    """
    connection = engine.connect()
    outer_tx = connection.begin()
    session = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )()
    try:
        yield session
    finally:
        session.close()
        outer_tx.rollback()
        connection.close()


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create and return a test user."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    user = User(
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=ph.hash("testpassword"),
        name="Test User",
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def second_user(db_session):
    """Create and return a second distinct test user."""
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    user = User(
        email=f"second_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=ph.hash("secondpassword"),
        name="Second User",
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_agent(db_session, test_user):
    """Create and return a test agent identity."""
    agent_uuid = str(uuid.uuid4())
    kp = generate_keypair()
    did_uri = generate_did(agent_uuid)
    did_doc = create_did_document(agent_uuid, kp.public_key)
    vc = create_verifiable_credential(
        agent_uuid=agent_uuid,
        did=did_uri,
        issuer_did=PLATFORM_DID,
        display_name="Test Agent",
        agent_type="assistant",
        model_version="test-1.0",
        purpose="Testing",
        capabilities=["chat"],
        public_key=kp.public_key,
        signing_private_key=_get_platform_signing_key(),
    )
    agent = AgentIdentity(
        agent_id=uuid.UUID(agent_uuid),
        owner_id=test_user.id,
        did_uri=did_uri,
        display_name="Test Agent",
        agent_type="assistant",
        model_version="test-1.0",
        purpose="Testing",
        capabilities=["chat"],
        public_key=kp.public_key,
        key_algorithm="ed25519",
        key_fingerprint=fingerprint(kp.public_key),
        did_document=did_doc,
        verifiable_credential=vc,
        behavioral_signature={},
        routing_config={},
        is_active=True,
        is_public=False,
    )
    db_session.add(agent)
    db_session.flush()
    db_session.refresh(agent)
    return agent


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
