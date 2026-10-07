"""Tests for retrieving / downloading generated certificates."""

from app.services import _process_certificates


class TestCertificateRetrieval:
    """GET /api/certificates/{id}/download — file download."""

    def test_download_successful_certificate(self, client, sample_request):
        """A completed certificate can be downloaded as a PDF."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]
        _process_certificates(job_id)

        # Pick the first certificate
        job_data = client.get(f"/api/jobs/{job_id}").json()
        cert_id = job_data["certificates"][0]["id"]

        response = client.get(f"/api/certificates/{cert_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        # Verify it is a valid PDF
        assert response.content[:5] == b"%PDF-"

    def test_download_returns_correct_filename(self, client, sample_request):
        """The Content-Disposition header includes the recipient's name."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]
        _process_certificates(job_id)

        job_data = client.get(f"/api/jobs/{job_id}").json()
        cert = job_data["certificates"][0]
        cert_id = cert["id"]

        response = client.get(f"/api/certificates/{cert_id}/download")
        content_disp = response.headers.get("content-disposition", "")
        safe_name = cert["recipient_name"].replace(" ", "_")
        assert safe_name in content_disp

    def test_download_nonexistent_certificate_returns_404(self, client):
        """Requesting a certificate that does not exist returns 404."""
        response = client.get("/api/certificates/no-such-id/download")
        assert response.status_code == 404

    def test_download_pending_certificate_returns_400(self, client, sample_request):
        """Trying to download a certificate that hasn't been generated yet returns 400."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]
        # Do NOT run _process_certificates — certs stay PENDING

        job_data = client.get(f"/api/jobs/{job_id}").json()
        cert_id = job_data["certificates"][0]["id"]

        response = client.get(f"/api/certificates/{cert_id}/download")
        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()

    def test_download_failed_certificate_returns_400(self, client, sample_request):
        """A certificate that failed generation cannot be downloaded."""
        from unittest.mock import patch

        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        # Force all generations to fail
        with patch(
            "app.services.generate_certificate_pdf",
            side_effect=RuntimeError("boom"),
        ):
            _process_certificates(job_id)

        job_data = client.get(f"/api/jobs/{job_id}").json()
        cert_id = job_data["certificates"][0]["id"]

        response = client.get(f"/api/certificates/{cert_id}/download")
        assert response.status_code == 400

    def test_download_job_zip(self, client, sample_request):
        """All successful certificates of a job come back in one ZIP."""
        import io
        import zipfile

        job_id = client.post("/api/jobs", json=sample_request).json()["id"]
        _process_certificates(job_id)

        response = client.get(f"/api/jobs/{job_id}/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        names = zf.namelist()
        assert len(names) == 3
        assert all(zf.read(n)[:5] == b"%PDF-" for n in names)

    def test_download_job_zip_before_processing_returns_400(self, client, sample_request):
        job_id = client.post("/api/jobs", json=sample_request).json()["id"]
        assert client.get(f"/api/jobs/{job_id}/download").status_code == 400

    def test_download_job_zip_unknown_job_returns_404(self, client):
        assert client.get("/api/jobs/nope/download").status_code == 404
