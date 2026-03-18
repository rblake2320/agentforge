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


def set_db_user_context(db: Session, user_id: str) -> None:
    """Set the PostgreSQL session variable used by RLS policies.

    Must be called at the start of every authenticated request, after the
    JWT has been verified and the User record confirmed active.  The session
    variable is transaction-scoped (``is_local=true`` inside the plpgsql
    helper) so it is automatically cleared when the transaction ends.

    Args:
        db:      The active SQLAlchemy ``Session`` for this request.
        user_id: The authenticated user's UUID as a plain string.
    """
    db.execute(
        text("SELECT agentforge.set_current_user(:uid)"),
        {"uid": user_id},
    )


def init_db():
    """Create the agentforge schema and all tables."""
    from .models import Base  # noqa: F401 — triggers model registration
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    Base.metadata.create_all(engine)
