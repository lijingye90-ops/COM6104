import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

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


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "test_workflow.db")


async def _collect(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


class TestWorkflowRun:
    @pytest.mark.asyncio
    @patch("workflow._apply_worker", new_callable=AsyncMock)
    @patch("workflow._agent_c_customize_worker", new_callable=AsyncMock)
    @patch("workflow._agent_b_match_worker", new_callable=AsyncMock)
    @patch("workflow._agent_a_search_worker", new_callable=AsyncMock)
    async def test_run_workflow_happy_path(
        self,
        mock_search,
        mock_match,
        mock_customize,
        mock_apply,
    ):
        from workflow import run_workflow
        from workflow_store import get_workflow_state

        mock_search.return_value = [
            {"job_id": "job-1", "title": "Backend Engineer", "company": "Acme", "url": "https://example.com/job-1", "description": "Python"}
        ]
        mock_match.return_value = {
            "job_id": "job-1",
            "title": "Backend Engineer",
            "company": "Acme",
            "url": "https://example.com/job-1",
            "description": "Python",
            "selection_reason": "best match",
        }
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-1.md",
            "cover_letter_file_path": "/tmp/cover_job-1.md",
        }
        mock_apply.return_value = {"status": "fallback", "detail": "manual finish"}

        events = await _collect(
            run_workflow(goal="python backend", conversation_id="conv-1", resume_path="/tmp/resume.pdf")
        )

        event_types = [event["event"] for event in events]
        assert "plan" in event_types
        assert event_types.count("workflow") >= 4
        assert event_types[-1] == "done"

        state = get_workflow_state("conv-1")
        assert state is not None
        assert state["current_stage"] == "apply_done"
        assert state["apply_result"]["status"] == "fallback"

    @pytest.mark.asyncio
    @patch("workflow._apply_worker", new_callable=AsyncMock)
    @patch("workflow._agent_c_customize_worker", new_callable=AsyncMock)
    @patch("workflow._agent_b_match_worker", new_callable=AsyncMock)
    @patch("workflow._agent_a_search_worker", new_callable=AsyncMock)
    async def test_run_workflow_reuses_completed_search_stage(
        self,
        mock_search,
        mock_match,
        mock_customize,
        mock_apply,
    ):
        from workflow import run_workflow
        from workflow_store import create_or_reset_workflow_state, update_workflow_state

        create_or_reset_workflow_state("conv-2", goal="python backend", input_resume_path="/tmp/resume.pdf")
        update_workflow_state(
            "conv-2",
            current_stage="search_done",
            search_results=[{"job_id": "job-2", "title": "Platform Engineer", "company": "Beta", "url": "https://example.com/job-2", "description": "FastAPI"}],
        )

        mock_match.return_value = {
            "job_id": "job-2",
            "title": "Platform Engineer",
            "company": "Beta",
            "url": "https://example.com/job-2",
            "description": "FastAPI",
            "selection_reason": "best match",
        }
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-2.md",
            "cover_letter_file_path": "/tmp/cover_job-2.md",
        }
        mock_apply.return_value = {"status": "fallback", "detail": "manual finish"}

        events = await _collect(
            run_workflow(goal="python backend", conversation_id="conv-2", resume_path="/tmp/resume.pdf")
        )

        mock_search.assert_not_awaited()
        reasoning_messages = [
            event["data"].get("text", "")
            for event in events
            if event["event"] == "reasoning"
        ]
        assert any("复用 Agent A" in message for message in reasoning_messages)

    @pytest.mark.asyncio
    @patch("workflow._agent_d_interview_prep_worker", new_callable=AsyncMock)
    @patch("workflow._agent_c_customize_worker", new_callable=AsyncMock)
    @patch("workflow._agent_b_match_worker", new_callable=AsyncMock)
    @patch("workflow._apply_worker", new_callable=AsyncMock)
    @patch("workflow._agent_a_search_worker")
    async def test_run_workflow_emits_tool_progress(
        self,
        mock_search,
        mock_apply,
        mock_match,
        mock_customize,
        mock_interview,
    ):
        from workflow import run_workflow

        async def fake_search(goal, progress_callback=None):
            assert goal == "python backend"
            if progress_callback:
                await progress_callback(
                    {
                        "stage": "hn_navigation",
                        "message": "正在打开 whoishiring 页面并定位最新 HN 招聘帖",
                    }
                )
            return [
                {
                    "job_id": "job-1",
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "url": "https://example.com/job-1",
                    "description": "Python",
                }
            ]

        async def fake_apply(job, customized, progress_callback=None):
            if progress_callback:
                await progress_callback(
                    {
                        "stage": "open_job",
                        "message": "已打开目标职位入口页",
                    }
                )
            return {"status": "fallback", "detail": "manual finish"}

        mock_search.side_effect = fake_search
        mock_match.return_value = {
            "job_id": "job-1",
            "title": "Backend Engineer",
            "company": "Acme",
            "url": "https://example.com/job-1",
            "description": "Python",
            "selection_reason": "best match",
        }
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-1.md",
            "cover_letter_file_path": "/tmp/cover_job-1.md",
        }
        mock_apply.side_effect = fake_apply
        mock_interview.return_value = {"questions": []}

        events = await _collect(
            run_workflow(goal="python backend", conversation_id="conv-progress", resume_path="/tmp/resume.pdf")
        )

        progress_events = [event for event in events if event["event"] == "tool_progress"]
        assert any(event["data"]["tool"] == "browser_job_search" for event in progress_events)
        assert any(event["data"]["tool"] == "apply_worker" for event in progress_events)

    @pytest.mark.asyncio
    @patch("workflow.send_email")
    @patch("workflow._agent_d_interview_prep_worker", new_callable=AsyncMock)
    @patch("workflow._agent_c_customize_worker", new_callable=AsyncMock)
    @patch("workflow._agent_b_match_worker", new_callable=AsyncMock)
    @patch("workflow._apply_worker", new_callable=AsyncMock)
    @patch("workflow._agent_a_search_worker", new_callable=AsyncMock)
    async def test_run_workflow_auto_sends_email_only_application(
        self,
        mock_search,
        mock_apply,
        mock_match,
        mock_customize,
        mock_interview,
        mock_send_email,
    ):
        from workflow import run_workflow

        mock_search.return_value = [
            {"job_id": "job-1", "title": "Software Engineer", "company": "Starbridge", "url": "https://news.ycombinator.com/item?id=1", "description": "Python"}
        ]
        mock_match.return_value = {
            "job_id": "job-1",
            "title": "Software Engineer",
            "company": "Starbridge",
            "url": "https://news.ycombinator.com/item?id=1",
            "description": "Python",
            "selection_reason": "best match",
        }
        mock_customize.return_value = {
            "resume_file_path": "/tmp/resume_job-1.md",
            "cover_letter_file_path": "/tmp/cover_job-1.md",
        }
        mock_apply.return_value = {
            "status": "fallback",
            "reason": "email_only_application",
            "package": {
                "resume_pdf": "/tmp/resume_job-1.pdf",
                "cover_letter": "/tmp/cover_job-1.md",
                "job_url": "https://news.ycombinator.com/item?id=1",
                "apply_email": "recruiting@starbridge.ai",
            },
        }
        mock_send_email.return_value = {
            "status": "sent",
            "provider": "resend",
            "message_id": "re_123",
        }
        mock_interview.return_value = {"questions": []}

        events = await _collect(
            run_workflow(goal="python backend", conversation_id="conv-email", resume_path="/tmp/resume.pdf")
        )

        tool_starts = [event for event in events if event["event"] == "tool_start"]
        assert any(event["data"]["tool"] == "send_email" for event in tool_starts)
        done_payload = next(event["data"] for event in events if event["event"] == "done")
        assert done_payload["workflow_state"]["apply_result"]["status"] == "applied"
        assert done_payload["workflow_state"]["apply_result"]["channel"] == "email"
