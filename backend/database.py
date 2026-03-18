from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from .config import get_settings
from .models.base import SCHEMA

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create the agentforge schema and all tables."""
    from .models import Base  # noqa: F401 — triggers model registration
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    Base.metadata.create_all(engine)
