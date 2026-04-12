"""
MCP Server — Job Hunt Agent Tools
Exposes all 4 tools as MCP-compliant endpoints.
Test with: npx @modelcontextprotocol/inspector python mcp_server.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="Job Hunt Agent",
    instructions=(
        "This server provides job hunting tools: "
        "search jobs, customize resumes, prepare for interviews, "
        "and auto-apply on LinkedIn."
    ),
)


@mcp.tool()
async def browser_job_search(
    query: str,
    location: str = "remote",
    limit: int = 10,
    source: str = "hn",
) -> list:
    """
    Search for jobs matching a query.

    Args:
        query:    Job keywords, e.g. 'Python backend engineer'
        location: Location or 'remote' (default: remote)
        limit:    Max results to return (default: 10)
        source:   Data source — 'hn' (HN Who's Hiring) or 'remoteok'

    Returns:
        List of job dicts with title, company, url, description, location.
    """
    from tools.job_search import browser_job_search as _search
    return await _search(query=query, location=location, limit=limit, source=source)


@mcp.tool()
def resume_customizer(
    resume_path: str,
    job_description: str,
    job_id: str = "",
    generate_cover_letter: bool = True,
) -> dict:
    """
    Customize a PDF resume for a specific job description.

    Args:
        resume_path:           Absolute path to the PDF resume file
        job_description:       Full JD text of the target position
        job_id:                Optional job ID for naming output files
        generate_cover_letter: Whether to generate a Cover Letter (default: true)

    Returns:
        Dict with customized_text, diff_html_path, resume_file_path, cover_letter.
    """
    from tools.resume_customizer import resume_customizer as _customize
    return _customize(
        resume_path=resume_path,
        job_description=job_description,
        job_id=job_id or None,
        generate_cover_letter=generate_cover_letter,
    )


@mcp.tool()
def interview_prep(
    company: str,
    job_title: str,
    job_description: str,
) -> dict:
    """
    Generate 5 interview questions with full STAR framework answers.

    Args:
        company:         Target company name
        job_title:       Target job title
        job_description: Full JD text

    Returns:
        Dict with company, role, questions list, and star_answers list.
    """
    from tools.interview_prep import interview_prep as _prep
    return _prep(company=company, job_title=job_title, job_description=job_description)


@mcp.tool()
async def linkedin_auto_apply(
    job_url: str,
    resume_md_path: str,
    job_id: str,
    cover_letter_path: str = "",
) -> dict:
    """
    Automate LinkedIn Easy Apply for a given job posting.

    Args:
        job_url:           LinkedIn job page URL
        resume_md_path:    Path to the customized Markdown resume
        job_id:            Job ID for tracking
        cover_letter_path: Optional path to the cover letter file

    Returns:
        {'status': 'applied', ...} on success, or
        {'status': 'fallback', 'package': {...}, 'reason': '...'} if auto-apply
        is unavailable (no Easy Apply button, non-standard form, etc.).
    """
    from tools.linkedin_apply import linkedin_auto_apply as _apply
    return await _apply(
        job_url=job_url,
        resume_md_path=resume_md_path,
        job_id=job_id,
        cover_letter_path=cover_letter_path,
    )


if __name__ == "__main__":
    mcp.run()
