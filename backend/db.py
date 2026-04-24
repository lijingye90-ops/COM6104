"""SQLite helpers for application tracking and chat persistence."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "jobs.db"


def init_db() -> None:
    """Create table if not exists (idempotent)."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            job_id              TEXT PRIMARY KEY,
            title               TEXT,
            company             TEXT,
            url                 TEXT,
            status              TEXT DEFAULT 'saved',
            applied_at          TEXT,
            resume_file_path    TEXT DEFAULT '',
            cover_letter_path   TEXT DEFAULT '',
            notes               TEXT DEFAULT '',
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id     TEXT PRIMARY KEY,
            title               TEXT DEFAULT '',
            last_resume_path    TEXT DEFAULT '',
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id     TEXT NOT NULL,
            role                TEXT NOT NULL,
            event_type          TEXT DEFAULT '',
            content             TEXT DEFAULT '',
            payload_json        TEXT DEFAULT '',
            created_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_items (
            key                 TEXT PRIMARY KEY,
            value               TEXT DEFAULT '',
            updated_at          TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def seed_db() -> None:
    """Backward-compatible no-op after removing demo seed data."""
    init_db()


def track_application(
    job_id: str,
    title: str,
    company: str,
    url: str,
    status: str = "saved",
    resume_file_path: str = "",
    cover_letter_path: str = "",
    notes: str = "",
) -> dict:
    """Upsert an application record. Returns the saved record."""
    init_db()
    applied_at = datetime.now(timezone.utc).isoformat() if status == "applied" else None
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO applications
           (job_id, title, company, url, status, applied_at, resume_file_path, cover_letter_path, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, title, company, url, status, applied_at, resume_file_path, cover_letter_path, notes),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM applications WHERE job_id=?", (job_id,)
    ).fetchone()
    conn.close()
    cols = ["job_id", "title", "company", "url", "status", "applied_at",
            "resume_file_path", "cover_letter_path", "notes", "created_at"]
    return dict(zip(cols, row)) if row else {}


def list_applications() -> list[dict]:
    """Return all applications ordered by created_at desc."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM applications ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_conversation(
    conversation_id: str,
    title: str = "",
    last_resume_path: str = "",
) -> dict:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT title, last_resume_path FROM conversations WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    resolved_title = title or (existing[0] if existing else "")
    resolved_resume_path = last_resume_path or (existing[1] if existing else "")
    conn.execute(
        """INSERT INTO conversations (conversation_id, title, last_resume_path, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(conversation_id) DO UPDATE SET
             title=excluded.title,
             last_resume_path=excluded.last_resume_path,
             updated_at=datetime('now')""",
        (conversation_id, resolved_title, resolved_resume_path),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM conversations WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def save_chat_message(
    conversation_id: str,
    role: str,
    content: str = "",
    event_type: str = "",
    payload: dict | list | None = None,
) -> dict:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO chat_messages (conversation_id, role, event_type, content, payload_json)
           VALUES (?, ?, ?, ?, ?)""",
        (
            conversation_id,
            role,
            event_type,
            content,
            json.dumps(payload, ensure_ascii=False) if payload is not None else "",
        ),
    )
    conn.execute(
        "UPDATE conversations SET updated_at=datetime('now') WHERE conversation_id=?",
        (conversation_id,),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM chat_messages WHERE id = last_insert_rowid()"
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def list_chat_messages(conversation_id: str) -> list[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT id, conversation_id, role, event_type, content, payload_json, created_at
           FROM chat_messages
           WHERE conversation_id=?
           ORDER BY id ASC""",
        (conversation_id,),
    ).fetchall()
    conn.close()
    messages: list[dict] = []
    for row in rows:
        item = dict(row)
        payload_json = item.pop("payload_json", "")
        item["data"] = json.loads(payload_json) if payload_json else None
        messages.append(item)
    return messages


def get_conversation_context(conversation_id: str, limit: int = 8) -> list[dict]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT role, content
           FROM chat_messages
           WHERE conversation_id=?
             AND role IN ('user', 'assistant')
             AND content != ''
           ORDER BY id DESC
           LIMIT ?""",
        (conversation_id, limit),
    ).fetchall()
    conn.close()
    ordered = list(reversed(rows))
    return [{"role": row["role"], "content": row["content"]} for row in ordered]


def set_memory_item(key: str, value: str) -> None:
    if not value:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO memory_items (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
             value=excluded.value,
             updated_at=datetime('now')""",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_memory_items() -> dict[str, str]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT key, value FROM memory_items ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return {key: value for key, value in rows}
