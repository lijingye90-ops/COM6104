import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def sample_resume_text():
    return """张小明
    高级Python工程师 | 5年经验
    技能：Python, FastAPI, PostgreSQL, Docker
    经历：曾在 Acme Corp 担任后端工程师3年"""


@pytest.fixture
def sample_jd():
    return """Senior Python Backend Engineer
    Requirements: 3+ years Python, FastAPI experience, familiar with Docker
    Company: TechStartup Inc."""


@pytest.fixture
def sample_resume_pdf(sample_resume_text):
    """Create a temporary PDF-like file for testing."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir="/tmp")
    # Write minimal content (not real PDF, but enough for path testing)
    tmp.write(sample_resume_text.encode())
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_jobs():
    return [
        {
            "job_id": "test-001",
            "title": "Python Engineer",
            "company": "TestCo",
            "url": "https://example.com/1",
            "description": "Python backend role",
            "location": "Remote",
            "source": "test",
        },
        {
            "job_id": "test-002",
            "title": "Backend Developer",
            "company": "DevCo",
            "url": "https://example.com/2",
            "description": "FastAPI developer needed",
            "location": "Remote",
            "source": "test",
        },
    ]
