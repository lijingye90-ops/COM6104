"""Tests for main.py — FastAPI endpoints (health, resume upload, applications, chat, diff).

All external dependencies (agent, DB) are mocked or redirected to temp storage.
"""
import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.APIConnectionError = RuntimeError
    openai_stub.APITimeoutError = RuntimeError
    openai_stub.InternalServerError = RuntimeError
    openai_stub.RateLimitError = RuntimeError

    class _OpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_stub.OpenAI = _OpenAI
    sys.modules["openai"] = openai_stub


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


class TestJobSearchEndpoint:
    @patch("main.browser_job_search", new_callable=AsyncMock)
    def test_job_search_returns_jobs(self, mock_search, client):
        mock_search.return_value = [
            {
                "job_id": "job-001",
                "title": "Backend Engineer",
                "company": "Acme",
                "url": "https://example.com/jobs/1",
                "description": "Python and FastAPI role",
                "location": "Remote",
                "source": "remoteok",
                "posted_at": "2026-04-23T00:00:00Z",
                "match_score": 0,
                "match_reason": "",
            }
        ]

        resp = client.get("/api/jobs/search", params={"query": "python"})

        assert resp.status_code == 200
        assert resp.json()["jobs"][0]["job_id"] == "job-001"
        mock_search.assert_awaited_once_with(
            query="python",
            location="remote",
            limit=10,
            source="remoteok",
        )


class TestJobApplyEndpoint:
    @patch("main.send_email_message")
    @patch("main.external_auto_apply", new_callable=AsyncMock)
    @patch("main.linkedin_auto_apply", new_callable=AsyncMock)
    @patch("main.resume_customizer")
    def test_apply_linkedin_job_tracks_application(self, mock_customize, mock_apply, mock_external_apply, mock_send_email, client):
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-001.md",
            "cover_letter_file_path": "/tmp/cover_job-001.md",
        }
        mock_apply.return_value = {
            "status": "applied",
            "job_id": "job-001",
            "detail": "Easy Apply submitted",
        }
        mock_send_email.return_value = {"status": "sent"}

        resp = client.post(
            "/api/jobs/apply",
            json={
                "job_id": "job-001",
                "title": "Backend Engineer",
                "company": "Acme",
                "url": "https://www.linkedin.com/jobs/view/1",
                "description": "Python role",
                "resume_path": "/tmp/resume.pdf",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["application"]["status"] == "applied"
        assert data["apply_result"]["status"] == "applied"
        mock_external_apply.assert_not_awaited()

    @patch("main.send_email_message")
    @patch("main.external_auto_apply", new_callable=AsyncMock)
    @patch("main.resume_customizer")
    def test_apply_non_linkedin_job_uses_external_flow(self, mock_customize, mock_external_apply, mock_send_email, client):
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-002.md",
            "cover_letter_file_path": "/tmp/cover_job-002.md",
        }
        mock_external_apply.return_value = {
            "status": "fallback",
            "reason": "no_application_path_found",
        }
        mock_send_email.return_value = {"status": "sent"}

        resp = client.post(
            "/api/jobs/apply",
            json={
                "job_id": "job-002",
                "title": "SRE",
                "company": "Pave",
                "url": "https://remoteok.com/remote-jobs/123",
                "description": "Infra role",
                "resume_path": "/tmp/resume.pdf",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["application"]["status"] == "fallback"
        assert data["apply_result"]["reason"] == "no_application_path_found"
        mock_external_apply.assert_awaited_once_with(
            job_url="https://remoteok.com/remote-jobs/123",
            resume_md_path="/tmp/resume_job-002.md",
            job_id="job-002",
            cover_letter_path="/tmp/cover_job-002.md",
            job_title="SRE",
            company="Pave",
        )

    @patch("main.send_email_message")
    @patch("main.external_auto_apply", new_callable=AsyncMock)
    @patch("main.resume_customizer")
    def test_apply_non_linkedin_email_only_job_sends_email(self, mock_customize, mock_external_apply, mock_send_email, client):
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-003.md",
            "cover_letter_file_path": "/tmp/cover_job-003.md",
        }
        mock_external_apply.return_value = {
            "status": "fallback",
            "reason": "email_only_application",
            "package": {
                "resume_pdf": "/tmp/resume_job-003.pdf",
                "cover_letter": "/tmp/cover_job-003.md",
                "job_url": "https://news.ycombinator.com/item?id=3",
                "apply_email": "recruiting@starbridge.ai",
            },
        }
        mock_send_email.return_value = {
            "status": "sent",
            "provider": "resend",
            "message_id": "re_123",
        }

        resp = client.post(
            "/api/jobs/apply",
            json={
                "job_id": "job-003",
                "title": "Software Engineer",
                "company": "Starbridge",
                "url": "https://news.ycombinator.com/item?id=3",
                "description": "Python role",
                "resume_path": "/tmp/resume.pdf",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["application"]["status"] == "applied"
        assert data["apply_result"]["status"] == "applied"
        assert data["apply_result"]["channel"] == "email"
        mock_send_email.assert_called_once()


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
        assert "preview_text" in data
        assert "size_bytes" in data

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
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        assert resp.json() == []


class TestResumeCustomizeEndpoint:
    @patch("main.resume_customizer")
    def test_customize_resume_returns_payload(self, mock_customize, client):
        mock_customize.return_value = {
            "job_id": "job-123",
            "customized_text": "# Resume",
            "cover_letter": "letter",
            "diff_html_path": "/tmp/diff_job-123.html",
            "resume_file_path": "/tmp/resume_job-123.md",
            "cover_letter_file_path": "/tmp/cover_job-123.md",
        }

        resp = client.post(
            "/api/resume/customize",
            json={
                "resume_path": "/tmp/resume.pdf",
                "job_description": "frontend engineer",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-123"


class TestInterviewPrepEndpoint:
    @patch("main.interview_prep")
    def test_interview_prep_returns_payload(self, mock_interview_prep, client):
        mock_interview_prep.return_value = {
            "company": "Acme",
            "role": "Frontend Engineer",
            "questions": ["Q1"],
            "star_answers": [{"question": "Q1", "star": {"S": "s", "T": "t", "A": "a", "R": "r"}}],
        }

        resp = client.post(
            "/api/interview/prep",
            json={
                "company": "Acme",
                "job_title": "Frontend Engineer",
                "job_description": "React and TypeScript",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["questions"] == ["Q1"]


class TestSendEmailEndpoint:
    @patch("main.send_email_message")
    def test_send_email_returns_provider_result(self, mock_send_email, client):
        mock_send_email.return_value = {
            "status": "sent",
            "provider": "resend",
            "message_id": "re_123",
        }

        resp = client.post(
            "/api/email/send",
            json={
                "to_email": "jobs@example.com",
                "subject": "Application",
                "body": "Hello",
                "resume_path": "/tmp/resume.pdf",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["provider"] == "resend"


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

        async def capture_gen(msg, resume_path=None, conversation_history=None, memory_context=None):
            captured_args["msg"] = msg
            captured_args["resume_path"] = resume_path
            captured_args["conversation_history"] = conversation_history
            captured_args["memory_context"] = memory_context
            yield {"event": "done", "data": {"message": "ok", "last_tool_result": None}}

        mock_run_agent.side_effect = capture_gen

        resp = client.post(
            "/api/chat",
            json={"message": "test", "resume_path": "/tmp/my.pdf"},
        )

        assert resp.status_code == 200
        # run_agent should have been called (either via side_effect or return_value)
        assert mock_run_agent.called
        assert captured_args["resume_path"] == "/tmp/my.pdf"

    @patch("main.run_agent")
    def test_chat_returns_conversation_id_header(self, mock_run_agent, client):
        async def mock_gen(msg, resume_path=None, conversation_history=None, memory_context=None):
            yield {"event": "done", "data": {"message": "ok", "last_tool_result": None}}

        mock_run_agent.side_effect = mock_gen

        resp = client.post("/api/chat", json={"message": "remember this"})

        assert resp.status_code == 200
        assert resp.headers.get("X-Conversation-Id")

    @patch("main.run_agent")
    def test_chat_history_returns_persisted_messages(self, mock_run_agent, client):
        async def mock_gen(msg, resume_path=None, conversation_history=None, memory_context=None):
            yield {"event": "done", "data": {"message": "persisted answer", "last_tool_result": None}}

        mock_run_agent.side_effect = mock_gen

        resp = client.post("/api/chat", json={"message": "save history"})
        conversation_id = resp.headers.get("X-Conversation-Id")

        history = client.get("/api/chat/history", params={"conversation_id": conversation_id})

        assert history.status_code == 200
        payload = history.json()
        assert payload["conversation_id"] == conversation_id
        assert any(item["content"] == "save history" for item in payload["messages"])
        assert any(item["content"] == "persisted answer" for item in payload["messages"])
        assert "workflow" in payload


class TestWorkflowEndpoint:
    @patch("main.run_workflow")
    def test_workflow_run_returns_conversation_id_header(self, mock_run_workflow, client):
        async def mock_gen(*args, **kwargs):
            yield {"event": "plan", "data": {"steps": ["A", "B", "C"]}}
            yield {
                "event": "done",
                "data": {
                    "summary": "workflow done",
                    "message": "workflow done",
                    "workflow_state": {"conversation_id": "conv-x", "current_stage": "apply_done"},
                },
            }

        mock_run_workflow.side_effect = mock_gen

        resp = client.post("/api/workflow/run", json={"goal": "python backend"})

        assert resp.status_code == 200
        assert resp.headers.get("X-Conversation-Id")

    @patch("main.run_workflow")
    def test_workflow_run_persists_user_and_done_messages(self, mock_run_workflow, client):
        async def mock_gen(*args, **kwargs):
            yield {
                "event": "done",
                "data": {
                    "summary": "workflow done",
                    "message": "workflow done",
                    "workflow_state": {"current_stage": "apply_done"},
                },
            }

        mock_run_workflow.side_effect = mock_gen

        resp = client.post("/api/workflow/run", json={"goal": "site reliability engineer"})
        conversation_id = resp.headers.get("X-Conversation-Id")

        history = client.get("/api/chat/history", params={"conversation_id": conversation_id})

        assert history.status_code == 200
        payload = history.json()
        assert any(item["content"] == "site reliability engineer" for item in payload["messages"])
        assert any(item["content"] == "workflow done" for item in payload["messages"])

    def test_workflow_state_endpoint_returns_payload(self, client):
        from workflow_store import create_or_reset_workflow_state, update_workflow_state

        create_or_reset_workflow_state("conv-state-1", goal="python backend")
        update_workflow_state("conv-state-1", current_stage="match_done", recommended_job={"job_id": "job-1"})

        resp = client.get("/api/workflow/state", params={"conversation_id": "conv-state-1"})

        assert resp.status_code == 200
        assert resp.json()["workflow"]["current_stage"] == "match_done"


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
