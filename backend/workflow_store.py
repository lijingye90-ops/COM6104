"""Persistence helpers for the demo-first 3-agent workflow."""
from __future__ import annotations

import json
import sqlite3

import db

STAGE_ORDER = [
    "started",
    "search_done",
    "match_done",
    "materials_done",
    "apply_done",
    "error",
]


def _connect() -> sqlite3.Connection:
    db.DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(db.DB_PATH)


def init_workflow_store() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_state (
            conversation_id       TEXT PRIMARY KEY,
            goal                  TEXT DEFAULT '',
            status                TEXT DEFAULT 'running',
            current_stage         TEXT DEFAULT 'started',
            input_resume_path     TEXT DEFAULT '',
            search_results_json   TEXT DEFAULT '',
            recommended_job_json  TEXT DEFAULT '',
            resume_file_path      TEXT DEFAULT '',
            cover_letter_path     TEXT DEFAULT '',
            apply_result_json     TEXT DEFAULT '',
            last_error            TEXT DEFAULT '',
            created_at            TEXT DEFAULT (datetime('now')),
            updated_at            TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


def _loads(raw: str) -> object | None:
    if not raw:
        return None
    return json.loads(raw)


def _dumps(value: object | None) -> str:
    if value in (None, "", []):
        return ""
    return json.dumps(value, ensure_ascii=False)


def _row_to_state(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["search_results"] = _loads(item.pop("search_results_json", ""))
    item["recommended_job"] = _loads(item.pop("recommended_job_json", ""))
    item["apply_result"] = _loads(item.pop("apply_result_json", ""))
    return item


def _validate_transition(previous: str, current: str) -> None:
    if previous not in STAGE_ORDER or current not in STAGE_ORDER:
        return
    previous_index = STAGE_ORDER.index(previous)
    current_index = STAGE_ORDER.index(current)
    if current == "error":
        return
    if current_index < previous_index:
        raise ValueError(f"Invalid workflow stage transition: {previous} -> {current}")


def create_or_reset_workflow_state(
    conversation_id: str,
    goal: str,
    input_resume_path: str = "",
) -> dict:
    init_workflow_store()
    conn = _connect()
    conn.execute(
        """
        INSERT INTO workflow_state (
            conversation_id,
            goal,
            status,
            current_stage,
            input_resume_path,
            search_results_json,
            recommended_job_json,
            resume_file_path,
            cover_letter_path,
            apply_result_json,
            last_error,
            updated_at
        )
        VALUES (?, ?, 'running', 'started', ?, '', '', '', '', '', '', datetime('now'))
        ON CONFLICT(conversation_id) DO UPDATE SET
            goal=excluded.goal,
            status='running',
            current_stage='started',
            input_resume_path=excluded.input_resume_path,
            search_results_json='',
            recommended_job_json='',
            resume_file_path='',
            cover_letter_path='',
            apply_result_json='',
            last_error='',
            updated_at=datetime('now')
        """,
        (conversation_id, goal, input_resume_path),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM workflow_state WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    conn.close()
    return _row_to_state(row) or {}


def get_workflow_state(conversation_id: str) -> dict | None:
    init_workflow_store()
    conn = _connect()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM workflow_state WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    conn.close()
    return _row_to_state(row)


def update_workflow_state(
    conversation_id: str,
    *,
    goal: str | None = None,
    status: str | None = None,
    current_stage: str | None = None,
    input_resume_path: str | None = None,
    search_results: list[dict] | None = None,
    recommended_job: dict | None = None,
    resume_file_path: str | None = None,
    cover_letter_path: str | None = None,
    apply_result: dict | None = None,
    last_error: str | None = None,
) -> dict:
    init_workflow_store()
    existing = get_workflow_state(conversation_id)
    if not existing:
        existing = create_or_reset_workflow_state(conversation_id, goal or "", input_resume_path or "")

    next_stage = current_stage or existing["current_stage"]
    _validate_transition(existing["current_stage"], next_stage)

    merged = {
        "goal": goal if goal is not None else existing["goal"],
        "status": status if status is not None else existing["status"],
        "current_stage": next_stage,
        "input_resume_path": (
            input_resume_path if input_resume_path is not None else existing["input_resume_path"]
        ),
        "search_results": search_results if search_results is not None else existing.get("search_results"),
        "recommended_job": (
            recommended_job if recommended_job is not None else existing.get("recommended_job")
        ),
        "resume_file_path": (
            resume_file_path if resume_file_path is not None else existing.get("resume_file_path", "")
        ),
        "cover_letter_path": (
            cover_letter_path if cover_letter_path is not None else existing.get("cover_letter_path", "")
        ),
        "apply_result": apply_result if apply_result is not None else existing.get("apply_result"),
        "last_error": last_error if last_error is not None else existing.get("last_error", ""),
    }

    conn = _connect()
    conn.execute(
        """
        INSERT INTO workflow_state (
            conversation_id,
            goal,
            status,
            current_stage,
            input_resume_path,
            search_results_json,
            recommended_job_json,
            resume_file_path,
            cover_letter_path,
            apply_result_json,
            last_error,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(conversation_id) DO UPDATE SET
            goal=excluded.goal,
            status=excluded.status,
            current_stage=excluded.current_stage,
            input_resume_path=excluded.input_resume_path,
            search_results_json=excluded.search_results_json,
            recommended_job_json=excluded.recommended_job_json,
            resume_file_path=excluded.resume_file_path,
            cover_letter_path=excluded.cover_letter_path,
            apply_result_json=excluded.apply_result_json,
            last_error=excluded.last_error,
            updated_at=datetime('now')
        """,
        (
            conversation_id,
            merged["goal"],
            merged["status"],
            merged["current_stage"],
            merged["input_resume_path"],
            _dumps(merged["search_results"]),
            _dumps(merged["recommended_job"]),
            merged["resume_file_path"],
            merged["cover_letter_path"],
            _dumps(merged["apply_result"]),
            merged["last_error"],
        ),
    )
    conn.commit()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM workflow_state WHERE conversation_id=?",
        (conversation_id,),
    ).fetchone()
    conn.close()
    return _row_to_state(row) or {}
