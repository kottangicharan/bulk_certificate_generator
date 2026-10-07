"""Tests for creating a certificate-generation job."""


class TestCreateJob:
    """POST /api/jobs — job creation."""

    def test_create_job_returns_202(self, client, sample_request):
        """A valid request returns 202 Accepted with a job ID."""
        response = client.post("/api/jobs", json=sample_request)

        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["total_count"] == 3
        assert "message" in data

    def test_create_job_persists_in_database(self, client, sample_request, db_session):
        """The job and its certificates are persisted after creation."""
        from app.models import Job, Certificate

        response = client.post("/api/jobs", json=sample_request)
        job_id = response.json()["id"]

        job = db_session.query(Job).filter(Job.id == job_id).first()
        assert job is not None
        assert job.event_name == "Python Workshop 2024"
        assert job.organizer_name == "Tech Academy"
        assert job.total_count == 3

        certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
        assert len(certs) == 3

    def test_create_job_sets_pending_status(self, client, sample_request):
        """Newly created job starts in PENDING status."""
        response = client.post("/api/jobs", json=sample_request)
        assert response.json()["status"] == "pending"

    def test_create_job_with_single_recipient(self, client):
        """A job with only one recipient is valid."""
        payload = {
            "event_name": "Single Cert",
            "organizer_name": "Org",
            "issue_date": "2024-06-01",
            "recipients": [{"name": "Solo User", "email": "solo@example.com"}],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 202
        assert response.json()["total_count"] == 1

    def test_create_job_with_many_recipients(self, client):
        """A bulk job with many recipients is accepted."""
        recipients = [
            {"name": f"User {i}", "email": f"user{i}@example.com"}
            for i in range(50)
        ]
        payload = {
            "event_name": "Big Event",
            "organizer_name": "Big Org",
            "issue_date": "2024-12-01",
            "recipients": recipients,
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 202
        assert response.json()["total_count"] == 50
