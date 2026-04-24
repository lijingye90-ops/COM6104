"""Resend email sender for assisted job applications."""
import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_URL = "https://api.resend.com/emails"


def _get_resend_api_key() -> str:
    return os.getenv("RESEND_API_KEY", "")


def _get_resend_from_email() -> str:
    return os.getenv("RESEND_FROM_EMAIL", "")


def _attachment_payload(path: str) -> dict | None:
    if not path or not Path(path).exists():
        return None

    content = Path(path).read_bytes()
    return {
        "filename": Path(path).name,
        "content": base64.b64encode(content).decode("ascii"),
    }


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
