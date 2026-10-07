"""Database engine, session factory, and base model."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

engine = None
SessionLocal = None


def init_db(database_url: str = None):
    """
    Initialize the database engine, session factory, and create all tables.

    Can be called multiple times (e.g. once for production, once per test) to
    point the application at a different database.
    """
    global engine, SessionLocal

    if database_url is None:
        from app import config
        database_url = config.DATABASE_URL

    connect_args = {}
    if "sqlite" in database_url:
        connect_args = {"check_same_thread": False}

    engine = create_engine(database_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import models so Base.metadata knows about them, then create tables.
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a database session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
