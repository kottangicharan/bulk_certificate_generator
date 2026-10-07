"""SQLAlchemy ORM models for Job and Certificate."""

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Enum, ForeignKey, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobStatus(str, enum.Enum):
    """Lifecycle status of a bulk-generation job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CertificateStatus(str, enum.Enum):
    """Generation status of an individual certificate."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Job(Base):
    """A bulk certificate-generation job submitted by a client."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String, nullable=False)
    organizer_name = Column(String, nullable=False)
    issue_date = Column(Date, nullable=False)
    status = Column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False,
    )
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    certificates = relationship(
        "Certificate", back_populates="job", lazy="joined",
    )


class Certificate(Base):
    """An individual certificate belonging to a Job."""
    __tablename__ = "certificates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    recipient_name = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False)
    status = Column(
        Enum(CertificateStatus), default=CertificateStatus.PENDING, nullable=False,
    )
    error_message = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="certificates")
