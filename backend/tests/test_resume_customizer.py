"""Tests for tools/resume_customizer.py — resume tailoring + HTML diff."""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: mock Zhipu response
# ---------------------------------------------------------------------------


def _make_mock_response(content: str) -> MagicMock:
    """Create a mock object mimicking ZhipuAI chat completion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


# ---------------------------------------------------------------------------
# Tests for _extract_pdf_text
# ---------------------------------------------------------------------------


class TestExtractPdfText:
    def test_extract_pdf_text_with_mock_pdfplumber(self, tmp_path):
        """Mock pdfplumber to return known text from a fake PDF."""
        from tools.resume_customizer import _extract_pdf_text

        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake pdf content")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("tools.resume_customizer.pdfplumber") as mock_plumber:
            mock_plumber.open.return_value = mock_pdf
            result = _extract_pdf_text(fake_pdf)

        assert result == "Page 1 text"

    def test_extract_pdf_text_multiple_pages(self, tmp_path):
        """Multiple pages should be joined with newlines."""
        from tools.resume_customizer import _extract_pdf_text

        fake_pdf = tmp_path / "multi.pdf"
        fake_pdf.write_bytes(b"fake")

        page1, page2 = MagicMock(), MagicMock()
        page1.extract_text.return_value = "Page 1"
        page2.extract_text.return_value = "Page 2"

        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("tools.resume_customizer.pdfplumber") as mock_plumber:
            mock_plumber.open.return_value = mock_pdf
            result = _extract_pdf_text(fake_pdf)

        assert "Page 1" in result
        assert "Page 2" in result
        assert result == "Page 1\nPage 2"

    def test_extract_pdf_text_empty_page(self, tmp_path):
        """Pages with None text should be skipped."""
        from tools.resume_customizer import _extract_pdf_text

        fake_pdf = tmp_path / "empty.pdf"
        fake_pdf.write_bytes(b"fake")

        page1, page2 = MagicMock(), MagicMock()
        page1.extract_text.return_value = None
        page2.extract_text.return_value = "Only page with text"

        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("tools.resume_customizer.pdfplumber") as mock_plumber:
            mock_plumber.open.return_value = mock_pdf
            result = _extract_pdf_text(fake_pdf)

        assert result == "Only page with text"


# ---------------------------------------------------------------------------
# Tests for _write_diff_html
# ---------------------------------------------------------------------------


class TestWriteDiffHtml:
    def test_write_diff_html_creates_file(self, tmp_path):
        """_write_diff_html should create an HTML file at the specified path."""
        from tools.resume_customizer import _write_diff_html

        output = str(tmp_path / "diff.html")
        _write_diff_html("line one\nline two", "line one\nline TWO", output)

        assert Path(output).exists()

    def test_write_diff_html_contains_expected_elements(self, tmp_path):
        """Generated HTML should contain diff descriptors and styling."""
        from tools.resume_customizer import _write_diff_html

        output = str(tmp_path / "diff.html")
        _write_diff_html("original text", "customized text", output)

        html = Path(output).read_text(encoding="utf-8")
        assert "原始简历" in html
        assert "定制版简历" in html
        assert "<style>" in html
        assert "diff" in html.lower()

    def test_write_diff_html_identical_content(self, tmp_path):
        """When original and customized are identical, still produces valid HTML."""
        from tools.resume_customizer import _write_diff_html

        output = str(tmp_path / "diff_same.html")
        _write_diff_html("same content", "same content", output)

        html = Path(output).read_text(encoding="utf-8")
        assert "<html" in html.lower() or "<!doctype" in html.lower()


# ---------------------------------------------------------------------------
# Tests for resume_customizer (main function)
# ---------------------------------------------------------------------------


class TestResumeCustomizer:
    def test_resume_customizer_invalid_format(self):
        """Non-PDF file should raise ValueError."""
        from tools.resume_customizer import resume_customizer

        with pytest.raises(ValueError, match="只支持 PDF 格式"):
            resume_customizer(
                resume_path="/tmp/resume.docx",
                job_description="Some JD",
            )

    def test_resume_customizer_txt_raises(self):
        """A .txt file should also raise ValueError."""
        from tools.resume_customizer import resume_customizer

        with pytest.raises(ValueError, match="只支持 PDF 格式"):
            resume_customizer(
                resume_path="/tmp/resume.txt",
                job_description="Some JD",
            )

    def test_resume_customizer_missing_file(self):
        """A non-existent PDF should raise FileNotFoundError."""
        from tools.resume_customizer import resume_customizer

        with pytest.raises(FileNotFoundError, match="简历文件不存在"):
            resume_customizer(
                resume_path="/tmp/definitely_does_not_exist_abc123.pdf",
                job_description="Some JD",
            )

    @patch("tools.resume_customizer.client")
    @patch("tools.resume_customizer.pdfplumber")
    def test_resume_customizer_full_flow(
        self, mock_plumber, mock_client, tmp_path, sample_jd
    ):
        """Full flow: extract PDF -> customize -> cover letter -> diff."""
        from tools.resume_customizer import resume_customizer

        # Setup: create a fake PDF file
        fake_pdf = tmp_path / "test_resume.pdf"
        fake_pdf.write_bytes(b"fake pdf")

        # Mock pdfplumber
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "张三\nPython Developer\n5 years experience"
        mock_pdf_obj = MagicMock()
        mock_pdf_obj.pages = [mock_page]
        mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
        mock_pdf_obj.__exit__ = MagicMock(return_value=False)
        mock_plumber.open.return_value = mock_pdf_obj

        # Mock Zhipu client: two calls (customize + cover letter)
        mock_client.chat.completions.create.side_effect = [
            _make_mock_response("# 张三\n## Customized Resume\n- Python Expert"),
            _make_mock_response("Dear Hiring Manager, I am a great fit..."),
        ]

        result = resume_customizer(
            resume_path=str(fake_pdf),
            job_description=sample_jd,
            job_id="test-flow",
            generate_cover_letter=True,
        )

        assert isinstance(result, dict)
        assert "customized_text" in result
        assert "diff_html_path" in result
        assert "resume_file_path" in result
        assert "cover_letter" in result
        assert "cover_letter_file_path" in result
        assert "original_text" in result

        # Verify customized text is what the mock returned
        assert "Customized Resume" in result["customized_text"]
        assert "Dear Hiring Manager" in result["cover_letter"]

        # Verify output files were created
        assert Path(result["resume_file_path"]).exists()
        assert Path(result["diff_html_path"]).exists()
        assert Path(result["cover_letter_file_path"]).exists()

    @patch("tools.resume_customizer.client")
    @patch("tools.resume_customizer.pdfplumber")
    def test_resume_customizer_no_cover_letter(
        self, mock_plumber, mock_client, tmp_path, sample_jd
    ):
        """When generate_cover_letter=False, no cover letter should be produced."""
        from tools.resume_customizer import resume_customizer

        fake_pdf = tmp_path / "test_resume.pdf"
        fake_pdf.write_bytes(b"fake pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Resume content"
        mock_pdf_obj = MagicMock()
        mock_pdf_obj.pages = [mock_page]
        mock_pdf_obj.__enter__ = MagicMock(return_value=mock_pdf_obj)
        mock_pdf_obj.__exit__ = MagicMock(return_value=False)
        mock_plumber.open.return_value = mock_pdf_obj

        # Only one API call (customize only, no cover letter)
        mock_client.chat.completions.create.return_value = _make_mock_response(
            "# Customized Resume"
        )

        result = resume_customizer(
            resume_path=str(fake_pdf),
            job_description=sample_jd,
            generate_cover_letter=False,
        )

        assert result["cover_letter"] == ""
        assert result["cover_letter_file_path"] == ""
        # Only 1 API call should have been made
        assert mock_client.chat.completions.create.call_count == 1
