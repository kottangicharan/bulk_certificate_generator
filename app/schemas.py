"""Pydantic schemas for request validation and response serialization."""

import re
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models import JobStatus, CertificateStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RecipientInput(BaseModel):
    """A single recipient in a bulk-generation request."""
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=1, max_length=254)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be empty or whitespace only")
        return stripped

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email format")
        return v.strip().lower()


class JobCreateRequest(BaseModel):
    """Payload for creating a new certificate-generation job."""
    event_name: str = Field(..., min_length=1, max_length=500)
    organizer_name: str = Field(..., min_length=1, max_length=500)
    issue_date: date
    # ponytail: raw items so one bad recipient doesn't 422 the whole batch;
    # each item is validated against RecipientInput in services.create_job.
    recipients: List[Any] = Field(
        ..., min_length=1, max_length=10_000,
        json_schema_extra={"items": RecipientInput.model_json_schema()},
    )

    @field_validator("event_name", "organizer_name")
    @classmethod
    def validate_not_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only")
        return stripped


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CertificateResponse(BaseModel):
    """Serialized view of a single certificate."""
    id: str
    recipient_name: str
    recipient_email: str
    status: CertificateStatus
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobSummaryResponse(BaseModel):
    """Summary view returned when listing jobs."""
    id: str
    event_name: str
    organizer_name: str
    issue_date: date
    status: JobStatus
    total_count: int
    success_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(JobSummaryResponse):
    """Full view including per-certificate breakdown."""
    certificates: List[CertificateResponse] = []


class JobCreateResponse(BaseModel):
    """Returned immediately when a job is accepted."""
    id: str
    status: JobStatus
    total_count: int
    message: str
