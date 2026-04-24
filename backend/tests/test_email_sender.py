import sys
import types
from pathlib import Path
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


class _FakeSMTP:
    sent_messages = []
    login_args = None

    def __init__(self, host, port, timeout=20):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return None

    def starttls(self, context=None):
        return None

    def login(self, username, password):
        _FakeSMTP.login_args = (username, password)

    def send_message(self, message):
        _FakeSMTP.sent_messages.append(message)


class TestEmailSender:
    @patch("tools.email_sender.smtplib.SMTP", _FakeSMTP)
    def test_send_email_prefers_smtp_when_configured(self, monkeypatch, tmp_path):
        from tools.email_sender import send_email

        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4 fake")

        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USERNAME", "user@gmail.com")
        monkeypatch.setenv("SMTP_PASSWORD", "gmail-app-password")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "user@gmail.com")
        monkeypatch.setenv("SMTP_USE_TLS", "true")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)

        _FakeSMTP.sent_messages.clear()
        _FakeSMTP.login_args = None

        result = send_email(
            to_email="jobs@example.com",
            subject="Application",
            body="Hello",
            resume_path=str(resume),
        )

        assert result["status"] == "sent"
        assert result["provider"] == "smtp"
        assert _FakeSMTP.login_args == ("user@gmail.com", "gmail-app-password")
        assert len(_FakeSMTP.sent_messages) == 1
        message = _FakeSMTP.sent_messages[0]
        assert message["To"] == "jobs@example.com"
        assert message["From"] == "user@gmail.com"

    def test_send_email_requires_provider_configuration(self, monkeypatch):
        from tools.email_sender import send_email

        for key in [
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "SMTP_FROM_EMAIL",
            "SMTP_USE_TLS",
            "RESEND_API_KEY",
            "RESEND_FROM_EMAIL",
        ]:
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(ValueError, match="email_sender_not_configured"):
            send_email(
                to_email="jobs@example.com",
                subject="Application",
                body="Hello",
            )
