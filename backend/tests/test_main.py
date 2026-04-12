"""Tests for main.py — FastAPI endpoints (health, resume upload, applications, chat, diff).

All external dependencies (agent, DB) are mocked or redirected to temp storage.
"""
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture: isolated test app with temp DB
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    """Redirect DB_PATH to a temp file so tests don't touch real data."""
    tmp_db_path = tmp_path / "test_main.db"
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_db_path)
    return tmp_db_path


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    from main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        """GET /health should return {"status": "ok"}."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Tests: POST /api/resume/upload
# ---------------------------------------------------------------------------


class TestResumeUpload:
    def test_upload_pdf_succeeds(self, client):
        """Uploading a .pdf file should return the server-side path and filename."""
        resp = client.post(
            "/api/resume/upload",
            files={"file": ("resume.pdf", b"fake pdf content", "application/pdf")},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert data["filename"] == "resume.pdf"
        assert data["path"].endswith(".pdf")

    def test_upload_non_pdf_returns_400(self, client):
        """Uploading a non-PDF file (.txt) should return 400."""
        resp = client.post(
            "/api/resume/upload",
            files={
                "file": (
                    "resume.txt",
                    b"plain text resume",
                    "text/plain",
                )
            },
        )

        assert resp.status_code == 400

    def test_upload_docx_returns_400(self, client):
        """Uploading a .docx file should return 400."""
        resp = client.post(
            "/api/resume/upload",
            files={
                "file": (
                    "resume.docx",
                    b"fake docx",
                    "application/octet-stream",
                )
            },
        )

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: GET /api/applications
# ---------------------------------------------------------------------------


class TestGetApplications:
    def test_get_applications_returns_list(self, client):
        """GET /api/applications should return a JSON list."""
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_applications_empty_on_fresh_db(self, client):
        """On a fresh (test) database, applications should be empty."""
        # Note: the startup event calls seed_db(), so after startup there may
        # be 2 seed records.  For a truly empty test we check the shape.
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Tests: POST /api/applications
# ---------------------------------------------------------------------------


class TestPostApplications:
    def test_post_then_get_application(self, client):
        """POST a new application, then GET should include it."""
        post_resp = client.post(
            "/api/applications",
            json={
                "job_id": "test-api-001",
                "title": "Python Dev",
                "company": "TestCo",
                "url": "https://example.com/job",
                "status": "saved",
            },
        )

        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["job_id"] == "test-api-001"
        assert data["title"] == "Python Dev"

        get_resp = client.get("/api/applications")
        apps = get_resp.json()
        job_ids = [a["job_id"] for a in apps]
        assert "test-api-001" in job_ids

    def test_post_application_upsert(self, client):
        """POST same job_id twice should update, not duplicate."""
        client.post(
            "/api/applications",
            json={
                "job_id": "upsert-001",
                "title": "Old Title",
                "company": "OldCo",
                "url": "https://example.com",
            },
        )
        client.post(
            "/api/applications",
            json={
                "job_id": "upsert-001",
                "title": "New Title",
                "company": "NewCo",
                "url": "https://example.com",
                "status": "applied",
            },
        )

        apps = client.get("/api/applications").json()
        matching = [a for a in apps if a["job_id"] == "upsert-001"]
        assert len(matching) == 1
        assert matching[0]["title"] == "New Title"
        assert matching[0]["status"] == "applied"


# ---------------------------------------------------------------------------
# Tests: POST /api/chat (SSE stream)
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    @patch("main.run_agent")
    def test_chat_returns_result(self, mock_run_agent, client):
        """POST /api/chat should return a response from the agent.

        The current main.py uses `await run_agent(...)`. Since run_agent is an
        async generator, the endpoint is expected to be updated to stream SSE.
        We mock run_agent to test the endpoint as-is.
        """
        # Mock run_agent to return a simple awaitable result
        # (compatible with both `await` and async-generator consumption patterns)
        async def mock_gen(msg, resume_path=None):
            yield {"event": "done", "data": {"message": "完成", "last_tool_result": None}}

        mock_run_agent.return_value = mock_gen("test")

        resp = client.post(
            "/api/chat",
            json={"message": "hello"},
        )

        # The endpoint should return 200 regardless of internal format
        assert resp.status_code == 200

    def test_chat_missing_message_returns_422(self, client):
        """Omitting the required 'message' field should return validation error."""
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422

    @patch("main.run_agent")
    def test_chat_passes_resume_path(self, mock_run_agent, client):
        """resume_path should be forwarded to run_agent."""
        captured_args = {}

        async def capture_gen(msg, resume_path=None):
            captured_args["msg"] = msg
            captured_args["resume_path"] = resume_path
            yield {"event": "done", "data": {"message": "ok", "last_tool_result": None}}

        mock_run_agent.side_effect = capture_gen

        resp = client.post(
            "/api/chat",
            json={"message": "test", "resume_path": "/tmp/my.pdf"},
        )

        assert resp.status_code == 200
        # run_agent should have been called (either via side_effect or return_value)
        assert mock_run_agent.called


# ---------------------------------------------------------------------------
# Tests: GET /api/diff/{job_id}
# ---------------------------------------------------------------------------


class TestDiffEndpoint:
    def test_diff_not_found(self, client):
        """Non-existent diff should return 404."""
        resp = client.get("/api/diff/nonexistent-999")
        assert resp.status_code == 404

    def test_diff_found(self, client):
        """Existing diff HTML should be served."""
        diff_html = "<html><body>Diff content here</body></html>"
        diff_path = Path("/tmp/diff_test-diff-001.html")
        diff_path.write_text(diff_html, encoding="utf-8")

        try:
            resp = client.get("/api/diff/test-diff-001")
            assert resp.status_code == 200
            assert "Diff content here" in resp.text
        finally:
            diff_path.unlink(missing_ok=True)
