"""Tests for the actual certificate generation logic."""

import os

from app.services import _process_certificates


class TestCertificateGeneration:
    """Verify that PDFs are generated correctly."""

    def test_certificates_are_generated_as_pdf(self, client, sample_request):
        """Each certificate produces a real PDF file on disk."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        # Run generation synchronously (background is mocked in fixture)
        _process_certificates(job_id)

        # Fetch updated job
        response = client.get(f"/api/jobs/{job_id}")
        data = response.json()

        assert data["status"] == "completed"
        assert data["success_count"] == 3
        assert data["failure_count"] == 0

        for cert in data["certificates"]:
            assert cert["status"] == "success"

    def test_generated_pdf_file_exists(self, client, sample_request, db_session):
        """The file_path recorded in the DB actually exists on disk."""
        from app.models import Certificate

        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]
        _process_certificates(job_id)

        certs = (
            db_session.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .all()
        )
        for cert in certs:
            assert cert.file_path is not None
            assert os.path.isfile(cert.file_path)
            # Basic sanity: PDF files start with %PDF
            with open(cert.file_path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-"

    def test_each_certificate_gets_unique_file(self, client, sample_request, db_session):
        """No two certificates share the same file."""
        from app.models import Certificate

        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]
        _process_certificates(job_id)

        certs = (
            db_session.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .all()
        )
        paths = [c.file_path for c in certs]
        assert len(paths) == len(set(paths))
