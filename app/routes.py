"""API route handlers."""

import io
import os
import zipfile
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Certificate, CertificateStatus
from app.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobDetailResponse,
    JobSummaryResponse,
)
from app.services import create_job, process_job_background

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# POST /api/jobs — create a new bulk-generation job
# ---------------------------------------------------------------------------

@router.post("/jobs", response_model=JobCreateResponse, status_code=202)
async def create_generation_job(
    request: JobCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Accept a certificate-generation request and return immediately.

    The actual PDF generation runs in a background thread so the client
    is not blocked.
    """
    job = create_job(
        db=db,
        event_name=request.event_name,
        organizer_name=request.organizer_name,
        issue_date=request.issue_date,
        recipients=request.recipients,
    )

    # Fire-and-forget background processing
    await process_job_background(job.id)

    return JobCreateResponse(
        id=job.id,
        status=job.status,
        total_count=job.total_count,
        message=(
            f"Job created. Generating {job.total_count} certificate(s) "
            "in the background."
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/jobs — list all jobs
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=List[JobSummaryResponse])
def list_jobs(db: Session = Depends(get_db)):
    """Return every job ordered by most recent first."""
    return db.query(Job).order_by(Job.created_at.desc()).all()


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — detailed status of a single job
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Return a job with its per-certificate breakdown."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/download — all successful certificates as a ZIP
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/download")
def download_job_certificates(job_id: str, db: Session = Depends(get_db)):
    """Bundle every successfully generated PDF in the job into one ZIP."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    certs = [
        c for c in job.certificates
        if c.status == CertificateStatus.SUCCESS
        and c.file_path and os.path.exists(c.file_path)
    ]
    if not certs:
        raise HTTPException(
            status_code=400,
            detail=f"No generated certificates available. Job status: {job.status.value}",
        )

    # ponytail: built in memory; stream from a temp file if jobs get huge
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for c in certs:
            safe_name = c.recipient_name.replace(" ", "_")
            zf.write(c.file_path, arcname=f"{safe_name}_{c.id}.pdf")

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates_{job_id}.zip"'},
    )


# ---------------------------------------------------------------------------
# GET /api/certificates/{certificate_id}/download — download a PDF
# ---------------------------------------------------------------------------

@router.get("/certificates/{certificate_id}/download")
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    """Stream the generated PDF back to the client."""
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if cert.status != CertificateStatus.SUCCESS:
        raise HTTPException(
            status_code=400,
            detail=f"Certificate not ready. Current status: {cert.status.value}",
        )

    if not cert.file_path or not os.path.exists(cert.file_path):
        raise HTTPException(status_code=404, detail="Certificate file not found on disk")

    safe_name = cert.recipient_name.replace(" ", "_")
    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=f"certificate_{safe_name}.pdf",
    )
