"""Tests for db.py — SQLite application tracking layer."""
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture: redirect DB_PATH to a temporary file so tests are isolated
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _tmp_db(monkeypatch, tmp_path):
    """Monkeypatch db.DB_PATH to a fresh temp database for every test."""
    tmp_db_path = tmp_path / "test_jobs.db"
    import db as db_module

    monkeypatch.setattr(db_module, "DB_PATH", tmp_db_path)
    yield tmp_db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitDB:
    def test_init_db_creates_table(self, _tmp_db):
        """init_db should create the applications table without error."""
        from db import init_db

        init_db()

        conn = sqlite3.connect(_tmp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='applications'"
        )
        tables = cursor.fetchall()
        conn.close()

        assert len(tables) == 1
        assert tables[0][0] == "applications"

    def test_init_db_is_idempotent(self, _tmp_db):
        """Calling init_db twice should not raise."""
        from db import init_db

        init_db()
        init_db()  # second call should be harmless


class TestSeedDB:
    def test_seed_db_inserts_two_records(self, _tmp_db):
        """seed_db is now a no-op kept only for backward compatibility."""
        from db import seed_db

        seed_db()

        conn = sqlite3.connect(_tmp_db)
        rows = conn.execute("SELECT * FROM applications").fetchall()
        conn.close()

        assert len(rows) == 0

    def test_seed_db_is_idempotent(self, _tmp_db):
        """Running seed_db twice should still be harmless."""
        from db import seed_db

        seed_db()
        seed_db()

        conn = sqlite3.connect(_tmp_db)
        rows = conn.execute("SELECT * FROM applications").fetchall()
        conn.close()

        assert len(rows) == 0

    def test_seed_db_expected_job_ids(self, _tmp_db):
        """Legacy seed IDs are no longer inserted."""
        from db import seed_db

        seed_db()

        conn = sqlite3.connect(_tmp_db)
        ids = [
            row[0]
            for row in conn.execute("SELECT job_id FROM applications").fetchall()
        ]
        conn.close()

        assert ids == []


class TestTrackApplication:
    def test_track_application_returns_dict(self, _tmp_db):
        """track_application should return a dict with all expected fields."""
        from db import track_application

        result = track_application(
            job_id="app-001",
            title="Python Dev",
            company="TestCo",
            url="https://example.com/job",
            status="saved",
        )

        assert isinstance(result, dict)
        expected_keys = {
            "job_id",
            "title",
            "company",
            "url",
            "status",
            "applied_at",
            "resume_file_path",
            "cover_letter_path",
            "notes",
            "created_at",
        }
        assert expected_keys.issubset(set(result.keys()))
        assert result["job_id"] == "app-001"
        assert result["title"] == "Python Dev"
        assert result["company"] == "TestCo"
        assert result["status"] == "saved"

    def test_track_application_upsert(self, _tmp_db):
        """Inserting with the same job_id should update, not duplicate."""
        from db import track_application

        track_application(
            job_id="app-002",
            title="Old Title",
            company="OldCo",
            url="https://example.com/old",
        )
        updated = track_application(
            job_id="app-002",
            title="New Title",
            company="NewCo",
            url="https://example.com/new",
            status="applied",
        )

        assert updated["title"] == "New Title"
        assert updated["company"] == "NewCo"
        assert updated["status"] == "applied"

        # Confirm only one row with this job_id
        conn = sqlite3.connect(_tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE job_id='app-002'"
        ).fetchone()[0]
        conn.close()
        assert count == 1

    def test_track_application_applied_sets_timestamp(self, _tmp_db):
        """When status is 'applied', applied_at should be set."""
        from db import track_application

        result = track_application(
            job_id="app-003",
            title="Dev",
            company="Co",
            url="https://example.com",
            status="applied",
        )

        assert result["applied_at"] is not None
        assert "T" in result["applied_at"]  # ISO format contains 'T'

    def test_track_application_saved_no_timestamp(self, _tmp_db):
        """When status is 'saved', applied_at should be None."""
        from db import track_application

        result = track_application(
            job_id="app-004",
            title="Dev",
            company="Co",
            url="https://example.com",
            status="saved",
        )

        assert result["applied_at"] is None

    def test_track_application_optional_fields(self, _tmp_db):
        """resume_file_path, cover_letter_path, notes should be stored."""
        from db import track_application

        result = track_application(
            job_id="app-005",
            title="Dev",
            company="Co",
            url="https://example.com",
            resume_file_path="/tmp/resume.md",
            cover_letter_path="/tmp/cover.md",
            notes="Great match",
        )

        assert result["resume_file_path"] == "/tmp/resume.md"
        assert result["cover_letter_path"] == "/tmp/cover.md"
        assert result["notes"] == "Great match"


class TestListApplications:
    def test_list_applications_empty(self, _tmp_db):
        """Fresh database should return an empty list."""
        from db import list_applications

        result = list_applications()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_applications_returns_dicts(self, _tmp_db):
        """Each item in the list should be a dict with expected keys."""
        from db import track_application, list_applications


class TestChatPersistence:
    def test_chat_tables_created(self, _tmp_db):
        from db import init_db

        init_db()

        conn = sqlite3.connect(_tmp_db)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        assert {"conversations", "chat_messages", "memory_items"}.issubset(tables)

    def test_save_and_list_chat_messages(self, _tmp_db):
        from db import list_chat_messages, save_chat_message, upsert_conversation

        upsert_conversation("conv-1", title="test")
        save_chat_message("conv-1", role="user", content="hello", event_type="user")
        save_chat_message("conv-1", role="assistant", content="hi", event_type="done", payload={"message": "hi"})

        messages = list_chat_messages("conv-1")

        assert len(messages) == 2
        assert messages[0]["content"] == "hello"
        assert messages[1]["data"]["message"] == "hi"

    def test_memory_items_round_trip(self, _tmp_db):
        from db import get_memory_items, set_memory_item

        set_memory_item("last_resume_path", "/tmp/resume.pdf")

        memory = get_memory_items()

        assert memory["last_resume_path"] == "/tmp/resume.pdf"

    def test_workflow_state_round_trip(self, _tmp_db):
        from workflow_store import (
            create_or_reset_workflow_state,
            get_workflow_state,
            init_workflow_store,
            update_workflow_state,
        )

        init_workflow_store()
        create_or_reset_workflow_state("conv-wf-1", goal="python backend", input_resume_path="/tmp/resume.pdf")
        update_workflow_state(
            "conv-wf-1",
            current_stage="match_done",
            recommended_job={"job_id": "job-1", "title": "Backend Engineer"},
        )

        state = get_workflow_state("conv-wf-1")

        assert state is not None
        assert state["goal"] == "python backend"
        assert state["current_stage"] == "match_done"
        assert state["recommended_job"]["job_id"] == "job-1"

    def test_workflow_state_rejects_backward_transition(self, _tmp_db):
        from workflow_store import create_or_reset_workflow_state, update_workflow_state

        create_or_reset_workflow_state("conv-wf-2", goal="python backend")
        update_workflow_state("conv-wf-2", current_stage="materials_done")

        with pytest.raises(ValueError):
            update_workflow_state("conv-wf-2", current_stage="search_done")

    def test_list_applications_ordered_by_created_at_desc(self, _tmp_db):
        """Most recently created application should appear first."""
        from db import track_application, list_applications
        import time

        track_application(
            job_id="order-001",
            title="First",
            company="Co1",
            url="https://1.com",
        )
        # Tiny sleep so created_at differs (SQLite datetime('now') has second precision)
        time.sleep(1.1)
        track_application(
            job_id="order-002",
            title="Second",
            company="Co2",
            url="https://2.com",
        )

        result = list_applications()

        assert result[0]["job_id"] == "order-002"
        assert result[1]["job_id"] == "order-001"
