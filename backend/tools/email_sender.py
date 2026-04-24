"""Email sender for assisted job applications."""
from __future__ import annotations

import base64
import mimetypes
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_URL = "https://api.resend.com/emails"


def _get_resend_api_key() -> str:
    return os.getenv("RESEND_API_KEY", "").strip()


def _get_resend_from_email() -> str:
    return os.getenv("RESEND_FROM_EMAIL", "").strip()


def _get_smtp_host() -> str:
    return os.getenv("SMTP_HOST", "").strip()


def _get_smtp_port() -> int:
    raw = os.getenv("SMTP_PORT", "587").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("smtp_invalid_port") from exc


def _get_smtp_username() -> str:
    return os.getenv("SMTP_USERNAME", "").strip()


def _get_smtp_password() -> str:
    return os.getenv("SMTP_PASSWORD", "").strip()


def _get_smtp_from_email() -> str:
    return os.getenv("SMTP_FROM_EMAIL", "").strip()


def _get_smtp_use_tls() -> bool:
    return os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no"}


def smtp_is_configured() -> bool:
    return all(
        [
            _get_smtp_host(),
            _get_smtp_username(),
            _get_smtp_password(),
            _get_smtp_from_email(),
        ]
    )


def resend_is_configured() -> bool:
    return bool(_get_resend_api_key() and _get_resend_from_email())


def _attachment_payload(path: str) -> dict | None:
    if not path or not Path(path).exists():
        return None

    content = Path(path).read_bytes()
    return {
        "filename": Path(path).name,
        "content": base64.b64encode(content).decode("ascii"),
    }


def _iter_attachment_paths(resume_path: str = "", cover_letter_path: str = "") -> list[str]:
    paths: list[str] = []
    if resume_path and Path(resume_path).exists():
        paths.append(resume_path)
    if cover_letter_path and Path(cover_letter_path).exists():
        paths.append(cover_letter_path)
    return paths


def _build_email_message(
    *,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
    cover_letter_path: str = "",
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    for path in _iter_attachment_paths(resume_path, cover_letter_path):
        mime_type, _ = mimetypes.guess_type(path)
        if mime_type:
            maintype, subtype = mime_type.split("/", 1)
        else:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(
            Path(path).read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=Path(path).name,
        )
    return message


def send_email_via_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
    cover_letter_path: str = "",
    max_attempts: int = 3,
) -> dict:
    host = _get_smtp_host()
    port = _get_smtp_port()
    username = _get_smtp_username()
    password = _get_smtp_password()
    from_email = _get_smtp_from_email()
    use_tls = _get_smtp_use_tls()

    if not all([host, username, password, from_email]):
        raise ValueError("smtp_not_configured")

    message = _build_email_message(
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        body=body,
        resume_path=resume_path,
        cover_letter_path=cover_letter_path,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if use_tls:
                with smtplib.SMTP(host, port, timeout=20) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(username, password)
                    server.send_message(message)
            else:
                with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as server:
                    server.login(username, password)
                    server.send_message(message)
            return {
                "status": "sent",
                "provider": "smtp",
                "message_id": message.get("Message-Id", ""),
            }
        except smtplib.SMTPException as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            time.sleep(attempt)

    raise RuntimeError(f"smtp_send_failed: {last_error}")


def send_email_via_resend(
    *,
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
    cover_letter_path: str = "",
    max_attempts: int = 3,
) -> dict:
    api_key = _get_resend_api_key()
    from_email = _get_resend_from_email()

    if not api_key or not from_email:
        raise ValueError("resend_not_configured")

    attachments = [
        attachment
        for attachment in [
            _attachment_payload(resume_path),
            _attachment_payload(cover_letter_path),
        ]
        if attachment is not None
    ]

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if attachments:
        payload["attachments"] = attachments

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(
                RESEND_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "status": "sent",
                "provider": "resend",
                "message_id": data.get("id", ""),
            }
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            time.sleep(attempt)

    raise RuntimeError(f"resend_send_failed: {last_error}")


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    resume_path: str = "",
    cover_letter_path: str = "",
    max_attempts: int = 3,
) -> dict:
    if smtp_is_configured():
        return send_email_via_smtp(
            to_email=to_email,
            subject=subject,
            body=body,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            max_attempts=max_attempts,
        )
    if resend_is_configured():
        return send_email_via_resend(
            to_email=to_email,
            subject=subject,
            body=body,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            max_attempts=max_attempts,
        )
    raise ValueError("email_sender_not_configured")
