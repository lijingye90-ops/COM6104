"""Tests for tools/interview_prep.py — interview question generation."""
import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(content: str) -> MagicMock:
    """Create a mock mimicking ZhipuAI chat completion response."""
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content
    return mock_resp


VALID_QUESTIONS_JSON = json.dumps(
    [
        {
            "question": "Tell me about a challenging Python project.",
            "star": {
                "S": "At Acme Corp we had a legacy system.",
                "T": "I was tasked with migrating to FastAPI.",
                "A": "I designed a phased migration plan.",
                "R": "Reduced latency by 40%.",
            },
        },
        {
            "question": "How do you handle tight deadlines?",
            "star": {
                "S": "Sprint deadline approaching.",
                "T": "Deliver feature on time.",
                "A": "Prioritized critical path.",
                "R": "Delivered 1 day early.",
            },
        },
        {
            "question": "Describe your experience with Docker.",
            "star": {
                "S": "Production deployment needed containers.",
                "T": "Containerize all services.",
                "A": "Created multi-stage Dockerfiles.",
                "R": "Deployment time reduced by 60%.",
            },
        },
        {
            "question": "How do you collaborate with frontend teams?",
            "star": {
                "S": "Cross-functional team project.",
                "T": "Define API contracts.",
                "A": "Used OpenAPI specs.",
                "R": "Zero integration issues at launch.",
            },
        },
        {
            "question": "Tell me about a production incident you resolved.",
            "star": {
                "S": "Database outage during peak traffic.",
                "T": "Restore service ASAP.",
                "A": "Implemented read replicas.",
                "R": "99.9% uptime achieved.",
            },
        },
    ],
    ensure_ascii=False,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInterviewPrepReturnsStructure:
    @patch("tools.interview_prep.client")
    def test_returns_expected_keys(self, mock_client):
        """Return dict should have company, role, questions, star_answers."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            VALID_QUESTIONS_JSON
        )

        result = interview_prep(
            company="TestCo",
            job_title="Python Engineer",
            job_description="Build backend services with Python and FastAPI.",
        )

        assert isinstance(result, dict)
        assert result["company"] == "TestCo"
        assert result["role"] == "Python Engineer"
        assert "questions" in result
        assert "star_answers" in result

    @patch("tools.interview_prep.client")
    def test_questions_are_strings(self, mock_client):
        """The 'questions' field should be a list of strings."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            VALID_QUESTIONS_JSON
        )

        result = interview_prep(
            company="TestCo",
            job_title="Python Engineer",
            job_description="Build backend services.",
        )

        assert isinstance(result["questions"], list)
        assert len(result["questions"]) == 5
        for q in result["questions"]:
            assert isinstance(q, str)

    @patch("tools.interview_prep.client")
    def test_star_answers_have_star_keys(self, mock_client):
        """Each star_answer should have question and star with S/T/A/R keys."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            VALID_QUESTIONS_JSON
        )

        result = interview_prep(
            company="TestCo",
            job_title="Python Engineer",
            job_description="Build backend services.",
        )

        assert isinstance(result["star_answers"], list)
        assert len(result["star_answers"]) == 5
        for answer in result["star_answers"]:
            assert "question" in answer
            assert "star" in answer
            star = answer["star"]
            assert "S" in star
            assert "T" in star
            assert "A" in star
            assert "R" in star


class TestInterviewPrepFallback:
    @patch("tools.interview_prep.client")
    def test_fallback_on_invalid_json(self, mock_client):
        """When API returns non-JSON, should fall back to placeholder structure."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            "Here are some questions for you:\n1. Tell me about yourself\n2. Why this company?"
        )

        result = interview_prep(
            company="TestCo",
            job_title="Backend Dev",
            job_description="Python backend role.",
        )

        assert isinstance(result, dict)
        assert result["company"] == "TestCo"
        assert result["role"] == "Backend Dev"
        # Fallback returns 1 placeholder question
        assert len(result["questions"]) == 1
        assert len(result["star_answers"]) == 1
        assert "Backend Dev" in result["questions"][0]

    @patch("tools.interview_prep.client")
    def test_fallback_on_malformed_json(self, mock_client):
        """Truncated/malformed JSON should trigger fallback."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            '[{"question": "incomplete...'  # malformed JSON
        )

        result = interview_prep(
            company="DevCo",
            job_title="SRE",
            job_description="Site reliability engineering.",
        )

        assert isinstance(result, dict)
        # Fallback structure
        assert len(result["star_answers"]) == 1
        assert "SRE" in result["questions"][0]

    @patch("tools.interview_prep.client")
    def test_fallback_star_has_all_fields(self, mock_client):
        """Fallback STAR answer should have all four fields."""
        from tools.interview_prep import interview_prep

        mock_client.chat.completions.create.return_value = _make_mock_response(
            "Not JSON at all"
        )

        result = interview_prep(
            company="X",
            job_title="Y",
            job_description="Z",
        )

        star = result["star_answers"][0]["star"]
        assert "S" in star
        assert "T" in star
        assert "A" in star
        assert "R" in star


class TestGenerateQuestionsValidJson:
    @patch("tools.interview_prep.client")
    def test_valid_json_response_parsed(self, mock_client):
        """When API returns valid JSON array, it should be parsed correctly."""
        from tools.interview_prep import _generate_questions

        mock_client.chat.completions.create.return_value = _make_mock_response(
            VALID_QUESTIONS_JSON
        )

        result = _generate_questions(
            company="BigCorp",
            title="Senior Python Engineer",
            jd="Python, FastAPI, Docker required",
        )

        assert isinstance(result, list)
        assert len(result) == 5
        assert result[0]["question"] == "Tell me about a challenging Python project."

    @patch("tools.interview_prep.client")
    def test_json_embedded_in_text(self, mock_client):
        """JSON array embedded in surrounding text should still be extracted."""
        from tools.interview_prep import _generate_questions

        response_text = (
            "Here are 5 interview questions:\n\n"
            + VALID_QUESTIONS_JSON
            + "\n\nHope this helps!"
        )
        mock_client.chat.completions.create.return_value = _make_mock_response(
            response_text
        )

        result = _generate_questions(
            company="Corp",
            title="Dev",
            jd="Python",
        )

        assert isinstance(result, list)
        assert len(result) == 5
