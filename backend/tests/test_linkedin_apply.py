import sys
import types
from pathlib import Path
from unittest.mock import patch

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


class TestExternalAutoApply:
    def test_demo_placeholder_url_skips_browser_automation(self, tmp_path):
        from tools.linkedin_apply import external_auto_apply
        import asyncio

        resume_md = tmp_path / "resume.md"
        resume_md.write_text("# Resume", encoding="utf-8")

        result = asyncio.run(
            external_auto_apply(
                job_url="https://example.com/jobs/003",
                resume_md_path=str(resume_md),
                job_id="job-demo-1",
                cover_letter_path="/tmp/cover.md",
            )
        )

        assert result["status"] == "fallback"
        assert result["reason"] == "demo_placeholder_job_url"
        assert "演示占位链接" in result["detail"]

    def test_multistep_harness_apply_returns_applied(self, tmp_path):
        from tools.linkedin_apply import external_auto_apply
        import asyncio

        resume_md = tmp_path / "resume.md"
        resume_md.write_text(
            "# Zhang Xinsen\n\nEmail: xinsen@example.com\nPhone: +852 5173 7655\nGitHub: https://github.com/example\n",
            encoding="utf-8",
        )

        with patch("tools.linkedin_apply._md_to_pdf", return_value=True), patch("tools.linkedin_apply.run_browser_harness_script") as mock_harness:
            mock_harness.return_value = {"status": "applied"}

            result = asyncio.run(
                external_auto_apply(
                    job_url="https://jobs.ashbyhq.com/river/r123",
                    resume_md_path=str(resume_md),
                    job_id="job-ashby-1",
                    cover_letter_path="/tmp/cover.md",
                    job_title="Senior Software Engineer (React, Full-stack)",
                    company="River",
                )
            )

        assert result["status"] == "applied"
        assert result["detail"] == "External application submitted via browser-harness"
        script = mock_harness.call_args.args[0]
        assert "Senior Software Engineer (React, Full-stack)" in script
        assert "xinsen@example.com" in script

    def test_multistep_harness_nonstandard_field_returns_fallback(self, tmp_path):
        from tools.linkedin_apply import external_auto_apply
        import asyncio

        resume_md = tmp_path / "resume.md"
        resume_md.write_text("# Resume\n\nEmail: xinsen@example.com\n", encoding="utf-8")

        with patch("tools.linkedin_apply._md_to_pdf", return_value=True), patch("tools.linkedin_apply.run_browser_harness_script") as mock_harness:
            mock_harness.return_value = {
                "status": "non_standard_field",
                "fields": [{"label": "Work authorization", "tag": "select", "type": ""}],
            }

            result = asyncio.run(
                external_auto_apply(
                    job_url="https://jobs.ashbyhq.com/river/r123",
                    resume_md_path=str(resume_md),
                    job_id="job-ashby-2",
                    job_title="Senior Software Engineer (React, Full-stack)",
                    company="River",
                )
            )

        assert result["status"] == "fallback"
        assert result["reason"] == "non_standard_form_field"
        assert "Work authorization" in result["detail"]


class TestLinkedinAutoApply:
    def test_linkedin_harness_apply_returns_applied(self, tmp_path):
        from tools.linkedin_apply import linkedin_auto_apply
        import asyncio

        resume_md = tmp_path / "resume.md"
        resume_md.write_text(
            "# Zhang Xinsen\n\nEmail: p253254@hsu.edu.hk\nPhone: +852 5173 7655\n",
            encoding="utf-8",
        )

        with patch("tools.linkedin_apply._md_to_pdf", return_value=True), patch(
            "tools.linkedin_apply.run_browser_harness_script"
        ) as mock_harness:
            mock_harness.return_value = {"status": "applied"}

            result = asyncio.run(
                linkedin_auto_apply(
                    job_url="https://www.linkedin.com/jobs/view/123",
                    resume_md_path=str(resume_md),
                    job_id="li-1",
                )
            )

        assert result["status"] == "applied"
        assert result["detail"] == "Easy Apply submitted via browser-harness"
        script = mock_harness.call_args.args[0]
        assert "Easy Apply" in script
        assert "p253254@hsu.edu.hk" in script

    def test_linkedin_harness_nonstandard_field_returns_fallback(self, tmp_path):
        from tools.linkedin_apply import linkedin_auto_apply
        import asyncio

        resume_md = tmp_path / "resume.md"
        resume_md.write_text("# Resume\n\nEmail: p253254@hsu.edu.hk\n", encoding="utf-8")

        with patch("tools.linkedin_apply._md_to_pdf", return_value=True), patch(
            "tools.linkedin_apply.run_browser_harness_script"
        ) as mock_harness:
            mock_harness.return_value = {
                "status": "non_standard_field",
                "fields": [{"label": "Work authorization", "tag": "select", "type": ""}],
            }

            result = asyncio.run(
                linkedin_auto_apply(
                    job_url="https://www.linkedin.com/jobs/view/456",
                    resume_md_path=str(resume_md),
                    job_id="li-2",
                )
            )

        assert result["status"] == "fallback"
        assert result["reason"] == "non_standard_form_field"
        assert "Work authorization" in result["detail"]
