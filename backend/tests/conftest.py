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
from backend.database import get_db
from backend.main import app

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
    # Cleanup
    Base.metadata.drop_all(eng)
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
    Base.metadata.schema = original_schema


@pytest.fixture(scope="function")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


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
