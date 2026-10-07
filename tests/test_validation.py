"""Tests for input validation on the job-creation endpoint."""


class TestInputValidation:
    """POST /api/jobs — validation errors should return 422."""

    # -- missing required fields ---------------------------------------------

    def test_missing_event_name(self, client):
        payload = {
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [{"name": "A", "email": "a@b.com"}],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    def test_missing_recipients(self, client):
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    def test_empty_recipients_list(self, client):
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    # -- invalid recipient data ----------------------------------------------
    # Bad recipients don't reject the batch; they're recorded as FAILED
    # certificates with the validation error, and valid ones still proceed.

    def _submit_one(self, client, recipient):
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [recipient],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 202
        data = client.get(f"/api/jobs/{response.json()['id']}").json()
        assert data["failure_count"] == 1
        cert = data["certificates"][0]
        assert cert["status"] == "failed"
        return cert["error_message"]

    def test_invalid_email_format(self, client):
        err = self._submit_one(client, {"name": "Alice", "email": "not-an-email"})
        assert "email" in err.lower()

    def test_empty_recipient_name(self, client):
        err = self._submit_one(client, {"name": "", "email": "a@b.com"})
        assert "name" in err

    def test_whitespace_only_name(self, client):
        err = self._submit_one(client, {"name": "   ", "email": "a@b.com"})
        assert "name" in err

    def test_missing_recipient_email(self, client):
        err = self._submit_one(client, {"name": "Alice"})
        assert "email" in err

    def test_non_object_recipient(self, client):
        err = self._submit_one(client, "just a string")
        assert err.startswith("Invalid recipient")

    def test_mixed_batch_generates_only_valid(self, client):
        from app.services import _process_certificates

        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bad", "email": "nope"},
                {"name": "Carol", "email": "carol@example.com"},
            ],
        }
        job_id = client.post("/api/jobs", json=payload).json()["id"]
        _process_certificates(job_id)

        data = client.get(f"/api/jobs/{job_id}").json()
        assert data["status"] == "completed"
        assert data["total_count"] == 3
        assert data["success_count"] == 2
        assert data["failure_count"] == 1
        failed = [c for c in data["certificates"] if c["status"] == "failed"]
        assert [c["recipient_name"] for c in failed] == ["Bad"]

    def test_too_many_recipients_rejected(self, client):
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [{"name": "A", "email": "a@b.com"}] * 10_001,
        }
        assert client.post("/api/jobs", json=payload).status_code == 422

    # -- invalid date --------------------------------------------------------

    def test_invalid_date_format(self, client):
        payload = {
            "event_name": "Evt",
            "organizer_name": "Org",
            "issue_date": "not-a-date",
            "recipients": [{"name": "Alice", "email": "a@b.com"}],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    # -- whitespace-only top-level fields ------------------------------------

    def test_whitespace_event_name(self, client):
        payload = {
            "event_name": "   ",
            "organizer_name": "Org",
            "issue_date": "2024-01-01",
            "recipients": [{"name": "Alice", "email": "a@b.com"}],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    def test_whitespace_organizer_name(self, client):
        payload = {
            "event_name": "Evt",
            "organizer_name": "   ",
            "issue_date": "2024-01-01",
            "recipients": [{"name": "Alice", "email": "a@b.com"}],
        }
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 422

    # -- completely empty body -----------------------------------------------

    def test_empty_body(self, client):
        response = client.post("/api/jobs", json={})
        assert response.status_code == 422
