"""SQLite helpers for application tracking."""
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
    conn.commit()
    conn.close()


def seed_db() -> None:
    """Insert 2 demo seed records (idempotent via INSERT OR IGNORE)."""
    init_db()
    seeds = [
        ("seed-001", "Senior Python Engineer", "Acme Corp", "https://example.com/1", "saved"),
        ("seed-002", "Backend Engineer (Remote)", "Startup XYZ", "https://example.com/2", "saved"),
    ]
    conn = sqlite3.connect(DB_PATH)
    for s in seeds:
        conn.execute(
            "INSERT OR IGNORE INTO applications(job_id,title,company,url,status) VALUES(?,?,?,?,?)",
            s,
        )
    conn.commit()
    conn.close()


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
