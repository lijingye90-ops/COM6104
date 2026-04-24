import sys
import types
from unittest.mock import patch

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


class TestBrowserJobSearchFallbacks:
    @pytest.mark.asyncio
    @patch("tools.job_search._load_cached_jobs")
    @patch("tools.job_search._fetch_remoteok_jobs")
    @patch("tools.job_search._fetch_hn_jobs")
    async def test_hn_empty_remoteok_empty_falls_back_to_cache(
        self,
        mock_hn,
        mock_remoteok,
        mock_cache,
    ):
        from tools.job_search import browser_job_search

        mock_hn.side_effect = RuntimeError("Connection error")
        mock_remoteok.return_value = []
        mock_cache.return_value = [{"job_id": "cached-1"}]

        result = await browser_job_search("Python developer", source="hn")

        assert result == [{"job_id": "cached-1"}]
        mock_cache.assert_called_once_with("Python developer", 10)

    @pytest.mark.asyncio
    @patch("tools.job_search._load_cached_jobs")
    @patch("tools.job_search._fetch_remoteok_jobs")
    async def test_remoteok_empty_falls_back_to_cache(self, mock_remoteok, mock_cache):
        from tools.job_search import browser_job_search

        mock_remoteok.return_value = []
        mock_cache.return_value = [{"job_id": "cached-2"}]

        result = await browser_job_search("Python backend engineer", source="remoteok")

        assert result == [{"job_id": "cached-2"}]
        mock_cache.assert_called_once_with("Python backend engineer", 10)


class TestHNBrowserNavigation:
    @pytest.mark.asyncio
    @patch("tools.job_search.run_browser_harness_script")
    async def test_hn_browser_navigation_uses_browser_harness(self, mock_harness):
        import tools.job_search as job_search

        mock_harness.return_value = {"clicked": True, "url": "https://news.ycombinator.com/item?id=47601859"}
        thread_url = await job_search._get_latest_hn_thread_url_via_browser()

        assert thread_url == "https://news.ycombinator.com/item?id=47601859"
        script = mock_harness.call_args.args[0]
        assert "news.ycombinator.com/submitted?id=whoishiring" in script
        assert "ask hn: who is hiring" in script.lower()
