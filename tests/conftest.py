"""Shared pytest fixtures for the test suite."""

import os
import shutil

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app import database, config
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path):
    """
    Before each test:
      - Point the DB at a temporary SQLite file.
      - Point the certificates output dir at a temp folder.
      - Initialize the schema.
    After each test:
      - Tear down tables (tmp_path is auto-cleaned by pytest).
    """
    test_db_path = tmp_path / "test.db"
    test_certs_dir = tmp_path / "certs"

    # Reconfigure the app-wide settings
    original_certs_dir = config.CERTIFICATES_DIR
    config.CERTIFICATES_DIR = str(test_certs_dir)

    database.init_db(f"sqlite:///{test_db_path}")

    yield

    # Restore original settings
    config.CERTIFICATES_DIR = original_certs_dir
    database.Base.metadata.drop_all(bind=database.engine)


@pytest.fixture
def db_session():
    """Provide a fresh database session for direct DB assertions."""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """
    FastAPI TestClient with background processing mocked out.

    ``process_job_background`` is replaced with a no-op ``AsyncMock`` so that
    tests can call ``_process_certificates`` synchronously when they need to
    verify generation results — keeping tests deterministic.
    """
    with patch("app.routes.process_job_background", new_callable=AsyncMock):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def sample_request():
    """Minimal valid job-creation payload."""
    return {
        "event_name": "Python Workshop 2024",
        "organizer_name": "Tech Academy",
        "issue_date": "2024-01-15",
        "recipients": [
            {"name": "Alice Johnson", "email": "alice@example.com"},
            {"name": "Bob Smith", "email": "bob@example.com"},
            {"name": "Charlie Brown", "email": "charlie@example.com"},
        ],
    }
