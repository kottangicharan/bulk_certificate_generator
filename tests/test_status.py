"""Tests for job status and progress tracking."""

from app.services import _process_certificates


class TestJobStatus:
    """GET /api/jobs and GET /api/jobs/{job_id} — status tracking."""

    def test_job_starts_as_pending(self, client, sample_request):
        """Immediately after creation the job is PENDING."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    def test_job_completed_after_processing(self, client, sample_request):
        """After background processing finishes, the job is COMPLETED."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        _process_certificates(job_id)

        response = client.get(f"/api/jobs/{job_id}")
        data = response.json()
        assert data["status"] == "completed"
        assert data["success_count"] == 3
        assert data["failure_count"] == 0

    def test_job_detail_includes_certificates(self, client, sample_request):
        """The detail endpoint returns per-certificate breakdown."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        _process_certificates(job_id)

        response = client.get(f"/api/jobs/{job_id}")
        data = response.json()
        assert "certificates" in data
        assert len(data["certificates"]) == 3

        names = {c["recipient_name"] for c in data["certificates"]}
        assert names == {"Alice Johnson", "Bob Smith", "Charlie Brown"}

    def test_list_jobs_returns_all(self, client, sample_request):
        """GET /api/jobs lists every submitted job."""
        client.post("/api/jobs", json=sample_request)
        client.post("/api/jobs", json=sample_request)

        response = client.get("/api/jobs")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_nonexistent_job_returns_404(self, client):
        """Requesting a non-existent job ID returns 404."""
        response = client.get("/api/jobs/does-not-exist")
        assert response.status_code == 404

    def test_job_counts_reflect_progress(self, client, sample_request):
        """total_count, success_count, and failure_count are accurate."""
        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        # Before processing
        data = client.get(f"/api/jobs/{job_id}").json()
        assert data["total_count"] == 3
        assert data["success_count"] == 0
        assert data["failure_count"] == 0

        _process_certificates(job_id)

        # After processing
        data = client.get(f"/api/jobs/{job_id}").json()
        assert data["total_count"] == 3
        assert data["success_count"] == 3
        assert data["failure_count"] == 0

    def test_progress_is_visible_mid_job(self, client, sample_request):
        """Counts are committed per certificate, so progress shows while running."""
        from unittest.mock import patch
        from app.certificate_template import generate_certificate_pdf

        job_id = client.post("/api/jobs", json=sample_request).json()["id"]
        seen = []

        def spy(*args, **kwargs):
            seen.append(client.get(f"/api/jobs/{job_id}").json()["success_count"])
            return generate_certificate_pdf(*args, **kwargs)

        with patch("app.services.generate_certificate_pdf", side_effect=spy):
            _process_certificates(job_id)

        assert seen == [0, 1, 2]
