"""Tests for handling individual certificate generation failures."""

from unittest.mock import patch

from app.services import _process_certificates
from app.certificate_template import generate_certificate_pdf


def _failing_generate(*args, **kwargs):
    """Mock that raises for one specific recipient and succeeds for others."""
    if kwargs.get("recipient_name") == "Bob Smith":
        raise RuntimeError("Simulated PDF rendering error")
    return generate_certificate_pdf(*args, **kwargs)


class TestFailureHandling:
    """One certificate failing must NOT prevent the rest from generating."""

    def test_partial_failure_does_not_block_others(self, client, sample_request):
        """If one cert fails, the remaining ones still succeed."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        with patch(
            "app.services.generate_certificate_pdf",
            side_effect=_failing_generate,
        ):
            _process_certificates(job_id)

        data = client.get(f"/api/jobs/{job_id}").json()
        assert data["success_count"] == 2
        assert data["failure_count"] == 1
        # Job is COMPLETED (not FAILED) because most certs succeeded.
        assert data["status"] == "completed"

    def test_failed_certificate_has_error_message(self, client, sample_request):
        """The failed certificate records a human-readable error."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        with patch(
            "app.services.generate_certificate_pdf",
            side_effect=_failing_generate,
        ):
            _process_certificates(job_id)

        data = client.get(f"/api/jobs/{job_id}").json()
        failed = [c for c in data["certificates"] if c["status"] == "failed"]
        assert len(failed) == 1
        assert failed[0]["recipient_name"] == "Bob Smith"
        assert "Simulated PDF rendering error" in failed[0]["error_message"]

    def test_successful_certs_unaffected_by_failure(self, client, sample_request):
        """Certificates for Alice and Charlie are fully successful."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        with patch(
            "app.services.generate_certificate_pdf",
            side_effect=_failing_generate,
        ):
            _process_certificates(job_id)

        data = client.get(f"/api/jobs/{job_id}").json()
        succeeded = [c for c in data["certificates"] if c["status"] == "success"]
        assert len(succeeded) == 2
        succeeded_names = {c["recipient_name"] for c in succeeded}
        assert succeeded_names == {"Alice Johnson", "Charlie Brown"}

    def test_all_failures_marks_job_failed(self, client):
        """When every certificate fails, the job status is FAILED."""
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [
                {"name": "Bob Smith", "email": "bob@example.com"},
            ],
        }
        response = client.post("/api/jobs", json=payload)
        job_id = response.json()["id"]

        with patch(
            "app.services.generate_certificate_pdf",
            side_effect=_failing_generate,
        ):
            _process_certificates(job_id)

        data = client.get(f"/api/jobs/{job_id}").json()
        assert data["status"] == "failed"
        assert data["success_count"] == 0
        assert data["failure_count"] == 1
