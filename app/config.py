"""Application configuration."""

import os

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./certificates.db")
CERTIFICATES_DIR: str = os.getenv("CERTIFICATES_DIR", "certificates")
