"""
Business logic — job creation and background certificate processing.

Design decision: background processing via ``asyncio.get_running_loop().
run_in_executor()`` with a ``ThreadPoolExecutor``.

Why not Celery?
  • Celery requires a broker (Redis / RabbitMQ) which adds operational
    complexity and makes local development harder.
  • A thread-pool executor is sufficient for this workload — each certificate
    is a short, CPU-light PDF render.
  • The architecture is still non-blocking: the API returns 202 immediately
    and generation happens in background threads.

The trade-off is that work is lost if the process crashes.  For a
production system at scale, Celery + Redis would be the natural next step.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import database, config
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.certificate_template import generate_certificate_pdf
from app.schemas import RecipientInput

logger = logging.getLogger(__name__)

# A small pool — certificate generation is mostly I/O (writing files).
executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Job creation (runs inside the request)
# ---------------------------------------------------------------------------

def create_job(
    db: Session,
    event_name: str,
    organizer_name: str,
    issue_date,
    recipients: list,
) -> Job:
    """
    Persist a new Job and its child Certificate rows.

    Each recipient is validated individually: valid ones start PENDING,
    invalid ones are stored as FAILED with the validation error, so the
    client can see exactly which entries were rejected and why.
    """
    job = Job(
        event_name=event_name,
        organizer_name=organizer_name,
        issue_date=issue_date,
        status=JobStatus.PENDING,
        total_count=len(recipients),
        failure_count=0,
    )
    db.add(job)
    db.flush()  # assigns job.id

    for raw in recipients:
        try:
            r = RecipientInput.model_validate(raw)
            cert = Certificate(
                job_id=job.id,
                recipient_name=r.name,
                recipient_email=r.email,
                status=CertificateStatus.PENDING,
            )
        except ValidationError as exc:
            data = raw if isinstance(raw, dict) else {}
            cert = Certificate(
                job_id=job.id,
                recipient_name=str(data.get("name") or ""),
                recipient_email=str(data.get("email") or ""),
                status=CertificateStatus.FAILED,
                error_message="Invalid recipient: " + "; ".join(
                    f"{'.'.join(map(str, e['loc'])) or 'recipient'}: {e['msg']}"
                    for e in exc.errors()
                ),
            )
            job.failure_count += 1
        db.add(cert)

    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Background processing (runs in a thread-pool thread)
# ---------------------------------------------------------------------------

def _process_certificates(job_id: str) -> None:
    """
    Generate PDFs for every certificate in *job_id*.

    Each certificate is processed independently so that one failure does not
    block the rest.

    This function creates its own database session because it runs in a
    background thread (outside the request lifecycle).
    """
    db: Session = database.SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None:
            logger.error("Job %s not found — skipping processing", job_id)
            return

        job.status = JobStatus.PROCESSING
        job.updated_at = datetime.utcnow()
        db.commit()

        # Invalid recipients were already marked FAILED at creation time.
        certificates = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .all()
        )

        for cert in certificates:
            try:
                file_path = generate_certificate_pdf(
                    certificate_id=cert.id,
                    recipient_name=cert.recipient_name,
                    event_name=job.event_name,
                    organizer_name=job.organizer_name,
                    issue_date=job.issue_date.strftime("%B %d, %Y"),
                    output_dir=config.CERTIFICATES_DIR,
                )
                cert.status = CertificateStatus.SUCCESS
                cert.file_path = file_path
                job.success_count += 1
            except Exception as exc:
                cert.status = CertificateStatus.FAILED
                cert.error_message = str(exc)
                job.failure_count += 1
                logger.error(
                    "Certificate %s generation failed: %s", cert.id, exc,
                )

            # Commit after each certificate so live progress is visible via
            # GET /api/jobs/{id} and survives a crash on a later certificate.
            job.updated_at = datetime.utcnow()
            db.commit()

        # Mark as COMPLETED even on partial failure so the client can
        # inspect individual certificate statuses.  FAILED is reserved
        # for cases where the *entire* job could not run.
        job.status = (
            JobStatus.FAILED if job.success_count == 0
            else JobStatus.COMPLETED
        )
        job.updated_at = datetime.utcnow()
        db.commit()

    except Exception as exc:
        logger.exception("Unexpected error while processing job %s", job_id)
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def process_job_background(job_id: str) -> None:
    """
    Submit certificate processing to the thread-pool executor.

    The future is *not* awaited — it is fire-and-forget so the API can
    return ``202 Accepted`` immediately.
    """
    loop = asyncio.get_running_loop()
    loop.run_in_executor(executor, _process_certificates, job_id)
