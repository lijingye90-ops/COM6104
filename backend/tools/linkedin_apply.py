"""MCP Tool 4: linkedin_auto_apply — browser-use powered LinkedIn Easy Apply (Zhipu GLM)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"
_ZHIPU_API_KEY = os.getenv("ZHIPUAI_API_KEY", "")

STORAGE_STATE_PATH = Path(__file__).parent.parent / "data" / "linkedin_state.json"
TMP_DIR = Path("/tmp")


def _md_to_pdf(md_path: str, output_path: str) -> bool:
    """Convert Markdown to PDF. Returns True on success."""
    try:
        import mistune
        from weasyprint import HTML

        md_text = Path(md_path).read_text(encoding="utf-8")
        html_content = mistune.html(md_text)
        # Add basic CSS for readable PDF
        styled_html = f"""
        <html><head><style>
        body {{ font-family: system-ui, sans-serif; font-size: 11pt; line-height: 1.5; margin: 2cm; }}
        h1 {{ font-size: 18pt; }} h2 {{ font-size: 14pt; }} h3 {{ font-size: 12pt; }}
        </style></head><body>{html_content}</body></html>
        """
        HTML(string=styled_html).write_pdf(output_path)
        return True
    except ImportError:
        return False


def _build_fallback(
    job_id: str,
    job_url: str,
    resume_pdf: str,
    cover_letter_path: str,
    reason: str,
) -> dict:
    """Build a standardised fallback response dict."""
    return {
        "status": "fallback",
        "package": {
            "resume_pdf": resume_pdf,
            "cover_letter": cover_letter_path,
            "job_url": job_url,
        },
        "reason": reason,
    }


async def linkedin_auto_apply(
    job_url: str,
    resume_md_path: str,
    job_id: str,
    cover_letter_path: str = "",
) -> dict:
    """
    Automate LinkedIn Easy Apply for a given job URL.

    Steps:
      1. Convert Markdown resume to PDF.
      2. Load pre-authenticated LinkedIn session.
      3. Use browser-use Agent (Zhipu GLM) to complete Easy Apply.

    Returns:
      - Success  : {"status": "applied", "job_id": "...", "detail": "..."}
      - Fallback : {"status": "fallback", "package": {...}, "reason": "..."}
    """
    resume_pdf_path = str(TMP_DIR / f"resume_{job_id}.pdf")

    # ------------------------------------------------------------------
    # Step 1 — Convert MD resume to PDF
    # ------------------------------------------------------------------
    if not Path(resume_md_path).exists():
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason=f"resume_not_found: {resume_md_path}",
        )

    pdf_ok = _md_to_pdf(resume_md_path, resume_pdf_path)
    if not pdf_ok:
        return _build_fallback(
            job_id, job_url, "", cover_letter_path,
            reason="pdf_conversion_unavailable",
        )

    # ------------------------------------------------------------------
    # Step 2 — Verify pre-authenticated LinkedIn session exists
    # ------------------------------------------------------------------
    if not STORAGE_STATE_PATH.exists():
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason="session_not_found",
        )

    # ------------------------------------------------------------------
    # Step 3 — Launch browser-use Agent for Easy Apply
    # ------------------------------------------------------------------
    try:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model="glm-4",
            api_key=_ZHIPU_API_KEY,
            base_url=_ZHIPU_BASE_URL,
        )

        browser = Browser(config=BrowserConfig(
            headless=False,
            storage_state=str(STORAGE_STATE_PATH),
        ))

        task = (
            f"Go to {job_url} .\n"
            "Wait up to 5 seconds for the page to fully load.\n"
            "Look for an 'Easy Apply' button on the page.\n"
            "If there is NO 'Easy Apply' button, reply EXACTLY: NO_EASY_APPLY\n"
            "\n"
            "If 'Easy Apply' IS present:\n"
            "1. Click the 'Easy Apply' button.\n"
            "2. In the application modal, fill in ONLY standard fields:\n"
            "   - Name, Email, Phone — use what is pre-filled or leave as-is.\n"
            f"  - Resume upload — upload the file at: {resume_pdf_path}\n"
            "3. If you encounter any NON-STANDARD form fields (e.g. essay questions, "
            "   work authorization, salary expectations, custom questions), "
            "   reply EXACTLY: NON_STANDARD_FIELD\n"
            "4. After filling in all standard fields, click 'Submit application' "
            "   (or 'Next' then 'Submit').\n"
            "5. Once submitted, reply EXACTLY: APPLIED\n"
        )

        agent = Agent(task=task, llm=llm, browser=browser)
        result = await agent.run()

        raw = result.final_result() if hasattr(result, "final_result") else str(result)
        raw_stripped = raw.strip() if raw else ""

        if "NO_EASY_APPLY" in raw_stripped:
            return _build_fallback(
                job_id, job_url, resume_pdf_path, cover_letter_path,
                reason="easy_apply_not_available",
            )

        if "NON_STANDARD_FIELD" in raw_stripped:
            return _build_fallback(
                job_id, job_url, resume_pdf_path, cover_letter_path,
                reason="non_standard_form_field",
            )

        if "APPLIED" in raw_stripped:
            return {
                "status": "applied",
                "job_id": job_id,
                "detail": "Easy Apply submitted",
            }

        # Agent returned something unexpected — treat as fallback
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason=f"unexpected_agent_response: {raw_stripped[:200]}",
        )

    except Exception as exc:
        return _build_fallback(
            job_id, job_url, resume_pdf_path, cover_letter_path,
            reason=f"exception: {exc}",
        )
