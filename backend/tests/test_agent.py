"""Tests for agent.py — SSE async generator agent loop.

Covers:
- Direct answers (no tool calls) yield reasoning + done events
- Tool call flow yields tool_start + tool_result + done events
- Resume injection into system prompt
- Loop limit of 20 iterations
- API error handling
- _call_tool dispatch for all known tools
"""
import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Helpers: mock GLM-4 response objects
# ---------------------------------------------------------------------------


def _make_message(content: str = "", tool_calls=None):
    """Create a mock message mimicking ZhipuAI completion response."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in (tool_calls or [])
        ]
        or None,
    }
    return msg


def _make_tool_call(tc_id: str, name: str, arguments: dict):
    """Create a mock tool_call object."""
    tc = MagicMock()
    tc.id = tc_id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments, ensure_ascii=False)
    return tc


def _make_response(content: str = "", tool_calls=None):
    """Create a full mock ZhipuAI chat.completions.create response."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message = _make_message(content, tool_calls)
    return resp


async def _collect_events(gen):
    """Collect all events from an async generator into a list."""
    events = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Tests: direct answer (no tool calls) — yields reasoning + done events
# ---------------------------------------------------------------------------


class TestRunAgentYieldsEvents:
    @pytest.mark.asyncio
    @patch("agent.client")
    async def test_simple_response_yields_done(self, mock_client):
        """Non-tool response should yield a single 'done' event with the message."""
        from agent import run_agent

        mock_client.chat.completions.create.return_value = _make_response(
            content="你好！我可以帮你找工作。"
        )

        events = await _collect_events(run_agent("帮我找工作"))

        assert len(events) == 1
        assert events[0]["event"] == "done"
        assert "你好" in events[0]["data"]["message"]
        assert events[0]["data"]["last_tool_result"] is None

    @pytest.mark.asyncio
    @patch("agent.client")
    async def test_empty_content_response(self, mock_client):
        """Response with None content should yield done with empty message string."""
        from agent import run_agent

        mock_client.chat.completions.create.return_value = _make_response(
            content=None
        )

        events = await _collect_events(run_agent("test"))

        assert len(events) == 1
        assert events[0]["event"] == "done"
        assert events[0]["data"]["message"] == ""

    @pytest.mark.asyncio
    @patch("agent.client")
    @patch("agent._extract_pdf_text")
    async def test_direct_answer_yields_done_with_resume(
        self, mock_extract, mock_client
    ):
        """Direct answer with resume_path should still yield a single done event."""
        from agent import run_agent

        mock_extract.return_value = "resume text"
        mock_client.chat.completions.create.return_value = _make_response(
            content="你好！我是求职助手。"
        )

        events = await _collect_events(run_agent("你好"))

        assert len(events) == 1
        assert events[0]["event"] == "done"
        assert "你好" in events[0]["data"]["message"]


# ---------------------------------------------------------------------------
# Tests: tool call flow — yields tool_start + tool_result + done
# ---------------------------------------------------------------------------


class TestRunAgentWithToolCall:
    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_tool_call_yields_start_result_done(
        self, mock_client, mock_call_tool
    ):
        """A single tool call should yield reasoning, tool_start, tool_result, then done."""
        from agent import run_agent

        tc = _make_tool_call(
            "tc-1", "browser_job_search", {"query": "Python engineer", "location": "remote"}
        )

        # Round 1: tool call with reasoning text
        resp1 = _make_response(content="让我帮你搜索职位。", tool_calls=[tc])
        # Round 2: final answer
        resp2 = _make_response(content="找到了2个匹配的职位。")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_call_tool.return_value = [
            {"job_id": "j1", "title": "Python Dev", "company": "Co1"}
        ]

        events = await _collect_events(run_agent("找Python工作"))

        event_types = [e["event"] for e in events]
        assert "reasoning" in event_types
        assert "tool_start" in event_types
        assert "tool_result" in event_types
        assert "done" in event_types

        # Verify order: reasoning -> tool_start -> tool_result -> done
        reasoning_idx = event_types.index("reasoning")
        tool_start_idx = event_types.index("tool_start")
        tool_result_idx = event_types.index("tool_result")
        done_idx = event_types.index("done")

        assert reasoning_idx < tool_start_idx < tool_result_idx < done_idx

    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_tool_start_contains_name_and_args(
        self, mock_client, mock_call_tool
    ):
        """tool_start event should include tool name and arguments."""
        from agent import run_agent

        tc = _make_tool_call(
            "tc-2",
            "interview_prep",
            {
                "company": "TestCo",
                "job_title": "Dev",
                "job_description": "Python role",
            },
        )
        resp1 = _make_response(content="准备面试材料。", tool_calls=[tc])
        resp2 = _make_response(content="面试准备完成。")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_call_tool.return_value = {"company": "TestCo", "questions": []}

        events = await _collect_events(run_agent("准备面试"))

        tool_start = [e for e in events if e["event"] == "tool_start"][0]
        assert tool_start["data"]["tool"] == "interview_prep"
        assert tool_start["data"]["args"]["company"] == "TestCo"

    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_tool_result_contains_result_data(
        self, mock_client, mock_call_tool
    ):
        """tool_result event should contain the tool name and its result data."""
        from agent import run_agent

        tc = _make_tool_call("tc-3", "browser_job_search", {"query": "Python"})
        mock_result = [{"job_id": "j1", "title": "Python Dev"}]

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Done."),
        ]
        mock_call_tool.return_value = mock_result

        events = await _collect_events(run_agent("search"))

        tool_result = [e for e in events if e["event"] == "tool_result"][0]
        assert tool_result["data"]["tool"] == "browser_job_search"
        assert tool_result["data"]["result"] == mock_result

    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_tool_error_captured_in_result(
        self, mock_client, mock_call_tool
    ):
        """When a tool raises, the error should be captured in tool_result, not crash."""
        from agent import run_agent

        tc = _make_tool_call("tc-err", "browser_job_search", {"query": "test"})
        resp1 = _make_response(content="搜索中...", tool_calls=[tc])
        resp2 = _make_response(content="搜索失败了")

        mock_client.chat.completions.create.side_effect = [resp1, resp2]
        mock_call_tool.side_effect = RuntimeError("Network timeout")

        events = await _collect_events(run_agent("搜索"))

        tool_result = [e for e in events if e["event"] == "tool_result"][0]
        assert "error" in tool_result["data"]["result"]
        assert "Network timeout" in tool_result["data"]["result"]["error"]

    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_done_event_has_last_tool_result(
        self, mock_client, mock_call_tool
    ):
        """Done event after tool usage should include last_tool_result."""
        from agent import run_agent

        tc = _make_tool_call("tc-done", "browser_job_search", {"query": "Python"})

        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Here are results."),
        ]
        mock_call_tool.return_value = [{"job_id": "j1"}]

        events = await _collect_events(run_agent("find jobs"))

        done = [e for e in events if e["event"] == "done"][0]
        assert done["data"]["last_tool_result"] is not None
        assert done["data"]["last_tool_result"]["tool"] == "browser_job_search"
        assert done["data"]["last_tool_result"]["result"] == [{"job_id": "j1"}]


# ---------------------------------------------------------------------------
# Tests: resume injection into system prompt
# ---------------------------------------------------------------------------


class TestRunAgentResumeInjection:
    @pytest.mark.asyncio
    @patch("agent._extract_pdf_text")
    @patch("agent.client")
    async def test_resume_path_injects_text(self, mock_client, mock_extract):
        """When resume_path is provided, system prompt should contain resume text."""
        from agent import run_agent

        mock_extract.return_value = "张三 Python工程师 5年经验"
        mock_client.chat.completions.create.return_value = _make_response(
            content="收到简历。"
        )

        events = await _collect_events(
            run_agent("帮我找工作", resume_path="/tmp/test.pdf")
        )

        # Verify the system prompt was built with resume text
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get(
            "messages", []
        )
        system_msg = messages[0]["content"]
        assert "张三" in system_msg
        assert "Python工程师" in system_msg

    @pytest.mark.asyncio
    @patch("agent.client")
    async def test_no_resume_uses_placeholder(self, mock_client):
        """When resume_path is None, system prompt should include default placeholder."""
        from agent import run_agent

        mock_client.chat.completions.create.return_value = _make_response(
            content="Direct answer"
        )

        events = await _collect_events(run_agent("hello", resume_path=None))

        assert len(events) == 1
        assert events[0]["event"] == "done"

        # Verify system prompt was built with default text
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get(
            "messages", []
        )
        system_msg = messages[0]["content"]
        assert "尚未上传简历" in system_msg

    @pytest.mark.asyncio
    @patch("agent._extract_pdf_text")
    @patch("agent.client")
    async def test_resume_path_in_user_message(self, mock_client, mock_extract):
        """When resume_path is provided, user message should include the file path."""
        from agent import run_agent

        mock_extract.return_value = "Resume text"
        mock_client.chat.completions.create.return_value = _make_response(
            content="OK"
        )

        events = await _collect_events(
            run_agent("customize resume", resume_path="/tmp/my_resume.pdf")
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get(
            "messages", []
        )
        user_msg = messages[1]["content"]
        assert "/tmp/my_resume.pdf" in user_msg

    @pytest.mark.asyncio
    @patch("agent._extract_pdf_text")
    @patch("agent.client")
    async def test_resume_extraction_failure_handled(
        self, mock_client, mock_extract
    ):
        """When PDF extraction fails, system prompt should contain error message."""
        from agent import run_agent

        mock_extract.side_effect = Exception("corrupt PDF")
        mock_client.chat.completions.create.return_value = _make_response(
            content="OK"
        )

        events = await _collect_events(
            run_agent("help", resume_path="/tmp/bad.pdf")
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get(
            "messages", []
        )
        system_msg = messages[0]["content"]
        assert "简历解析失败" in system_msg


# ---------------------------------------------------------------------------
# Tests: loop limit (max 20 iterations)
# ---------------------------------------------------------------------------


class TestRunAgentLoopLimit:
    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_loop_stops_at_20(self, mock_client, mock_call_tool):
        """If GLM-4 always returns tool_calls, loop should stop at 20 iterations."""
        from agent import run_agent

        tc = _make_tool_call("tc-loop", "browser_job_search", {"query": "loop"})

        # Always return tool calls — never a final answer
        mock_client.chat.completions.create.return_value = _make_response(
            tool_calls=[tc]
        )
        mock_call_tool.return_value = {"jobs": []}

        events = await _collect_events(run_agent("infinite loop test"))

        # Should have 20 rounds of tool_start + tool_result, then a done
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert "最大迭代次数" in done_events[0]["data"]["message"]

        # Exactly 20 tool_start events
        tool_starts = [e for e in events if e["event"] == "tool_start"]
        assert len(tool_starts) == 20

    @pytest.mark.asyncio
    @patch("agent._call_tool", new_callable=AsyncMock)
    @patch("agent.client")
    async def test_loop_limit_preserves_last_tool_result(
        self, mock_client, mock_call_tool
    ):
        """When loop limit is hit, last_tool_result should still be present."""
        from agent import run_agent

        tc = _make_tool_call(
            "tc-lim",
            "interview_prep",
            {"company": "Co", "job_title": "Dev", "job_description": "JD"},
        )

        mock_client.chat.completions.create.return_value = _make_response(
            tool_calls=[tc]
        )
        mock_call_tool.return_value = {"company": "Co", "questions": []}

        events = await _collect_events(run_agent("loop test"))

        done = [e for e in events if e["event"] == "done"][0]
        assert done["data"]["last_tool_result"] is not None
        assert done["data"]["last_tool_result"]["tool"] == "interview_prep"


# ---------------------------------------------------------------------------
# Tests: API error handling
# ---------------------------------------------------------------------------


class TestRunAgentApiError:
    @pytest.mark.asyncio
    @patch("agent.client")
    async def test_api_error_yields_error_event(self, mock_client):
        """When GLM-4 API throws, should yield an error event and stop."""
        from agent import run_agent

        mock_client.chat.completions.create.side_effect = RuntimeError(
            "API key invalid"
        )

        events = await _collect_events(run_agent("test"))

        assert len(events) == 1
        assert events[0]["event"] == "error"
        assert "GLM-4 API 调用失败" in events[0]["data"]["message"]


# ---------------------------------------------------------------------------
# Tests: _call_tool dispatch for all known tools
# ---------------------------------------------------------------------------


class TestCallTool:
    @pytest.mark.asyncio
    @patch("agent.browser_job_search", new_callable=AsyncMock)
    async def test_dispatch_browser_job_search(self, mock_search):
        """browser_job_search should be dispatched correctly."""
        from agent import _call_tool

        mock_search.return_value = [{"job_id": "1", "title": "Test Job"}]
        result = await _call_tool(
            "browser_job_search", {"query": "python", "location": "remote"}
        )

        mock_search.assert_called_once_with(query="python", location="remote")
        assert result == [{"job_id": "1", "title": "Test Job"}]

    @pytest.mark.asyncio
    @patch("agent.resume_customizer")
    async def test_dispatch_resume_customizer(self, mock_rc):
        """resume_customizer should be dispatched correctly."""
        from agent import _call_tool

        mock_rc.return_value = {"customized_text": "test"}
        result = await _call_tool(
            "resume_customizer",
            {"resume_path": "/tmp/r.pdf", "job_description": "JD"},
        )

        mock_rc.assert_called_once_with(
            resume_path="/tmp/r.pdf", job_description="JD"
        )
        assert result["customized_text"] == "test"

    @pytest.mark.asyncio
    @patch("agent.interview_prep")
    async def test_dispatch_interview_prep(self, mock_ip):
        """interview_prep should be dispatched correctly."""
        from agent import _call_tool

        mock_ip.return_value = {"questions": ["Q1"], "star_answers": []}
        result = await _call_tool(
            "interview_prep",
            {"company": "Co", "job_title": "Dev", "job_description": "JD"},
        )

        mock_ip.assert_called_once_with(
            company="Co", job_title="Dev", job_description="JD"
        )
        assert result["questions"] == ["Q1"]

    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self):
        """Calling an unknown tool should raise ValueError."""
        from agent import _call_tool

        with pytest.raises(ValueError, match="Unknown tool"):
            await _call_tool("nonexistent_tool", {})
