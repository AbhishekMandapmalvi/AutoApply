"""Tests for KB-related database schema and methods — TASK-030 M1.

Tests knowledge_base, uploaded_documents, roles tables and their CRUD methods.
"""

import json

import pytest

from db.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


class TestKBSchema:
    """Tests for KB table creation and schema."""

    def test_tables_created(self, db):
        """All KB tables exist after init."""
        conn = db._connect()
        tables = {
            row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert "knowledge_base" in tables
        assert "uploaded_documents" in tables
        assert "roles" in tables

    def test_resume_versions_has_reuse_columns(self, db):
        """resume_versions table has reuse_source and source_entry_ids columns."""
        conn = db._connect()
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(resume_versions)").fetchall()
        }
        conn.close()
        assert "reuse_source" in columns
        assert "source_entry_ids" in columns


class TestUploadedDocuments:
    """Tests for uploaded_documents CRUD."""

    def test_save_and_get(self, db):
        """Insert and retrieve an uploaded document."""
        doc_id = db.save_uploaded_document(
            filename="resume.pdf",
            file_type="pdf",
            file_path="/path/to/resume.pdf",
            raw_text="John Smith, Senior Engineer...",
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
        )
        assert doc_id > 0

        doc = db.get_uploaded_document(doc_id)
        assert doc is not None
        assert doc["filename"] == "resume.pdf"
        assert doc["raw_text"] == "John Smith, Senior Engineer..."
        assert doc["processed_at"] is not None  # set because llm_provider given

    def test_save_without_processing(self, db):
        """Document without LLM info has processed_at as NULL."""
        doc_id = db.save_uploaded_document(
            filename="notes.txt",
            file_type="txt",
            file_path="/path/to/notes.txt",
        )
        doc = db.get_uploaded_document(doc_id)
        assert doc["processed_at"] is None

    def test_list_documents(self, db):
        """List all uploaded documents."""
        db.save_uploaded_document("a.txt", "txt", "/a.txt")
        db.save_uploaded_document("b.pdf", "pdf", "/b.pdf")
        docs = db.get_uploaded_documents()
        assert len(docs) == 2

    def test_delete_document_cascades_kb(self, db):
        """Deleting a document removes its KB entries."""
        doc_id = db.save_uploaded_document("test.txt", "txt", "/test.txt")
        db.save_kb_entry(category="experience", text="Entry 1", source_doc_id=doc_id)
        db.save_kb_entry(category="skill", text="Entry 2", source_doc_id=doc_id)

        db.delete_uploaded_document(doc_id)

        assert db.get_uploaded_document(doc_id) is None
        entries = db.get_kb_entries()
        assert len(entries) == 0

    def test_get_nonexistent(self, db):
        """Getting a non-existent document returns None."""
        assert db.get_uploaded_document(9999) is None


class TestKBEntries:
    """Tests for knowledge_base CRUD."""

    def test_save_entry(self, db):
        """Insert a KB entry."""
        entry_id = db.save_kb_entry(
            category="experience",
            text="Built microservices with Go",
            subsection="Senior Dev — Acme",
            job_types=json.dumps(["backend"]),
            tags=json.dumps(["go", "microservices"]),
        )
        assert entry_id is not None
        assert entry_id > 0

    def test_dedup_constraint(self, db):
        """Duplicate (category, text) returns None."""
        db.save_kb_entry(category="skill", text="Python")
        result = db.save_kb_entry(category="skill", text="Python")
        assert result is None

    def test_get_entry(self, db):
        """Retrieve a single entry by ID."""
        entry_id = db.save_kb_entry(
            category="education",
            text="BS CompSci — MIT",
        )
        entry = db.get_kb_entry(entry_id)
        assert entry["category"] == "education"
        assert entry["is_active"] == 1

    def test_get_entries_filter_active(self, db):
        """Active filter excludes soft-deleted entries."""
        id1 = db.save_kb_entry(category="experience", text="Active entry")
        id2 = db.save_kb_entry(category="experience", text="Deleted entry")
        db.soft_delete_kb_entry(id2)

        active = db.get_kb_entries(active_only=True)
        assert len(active) == 1
        assert active[0]["id"] == id1

        all_entries = db.get_kb_entries(active_only=False)
        assert len(all_entries) == 2

    def test_get_entries_by_ids(self, db):
        """Fetch entries by specific IDs."""
        db.save_kb_entry(category="experience", text="A")
        id2 = db.save_kb_entry(category="skill", text="B")
        id3 = db.save_kb_entry(category="education", text="C")

        entries = db.get_kb_entries_by_ids([id2, id3])
        assert len(entries) == 2
        assert entries[0]["id"] == id2
        assert entries[1]["id"] == id3

    def test_update_entry(self, db):
        """Update entry fields."""
        entry_id = db.save_kb_entry(category="experience", text="Old text")
        result = db.update_kb_entry(entry_id, text="New text")
        assert result is True

        entry = db.get_kb_entry(entry_id)
        assert entry["text"] == "New text"
        assert entry["updated_at"] is not None

    def test_soft_delete(self, db):
        """Soft delete sets is_active=0."""
        entry_id = db.save_kb_entry(category="skill", text="Python")
        result = db.soft_delete_kb_entry(entry_id)
        assert result is True

        entry = db.get_kb_entry(entry_id)
        assert entry["is_active"] == 0

    def test_kb_stats(self, db):
        """Stats returns correct counts."""
        db.save_kb_entry(category="experience", text="E1")
        db.save_kb_entry(category="experience", text="E2")
        db.save_kb_entry(category="skill", text="S1")
        # Soft-deleted should not count
        id4 = db.save_kb_entry(category="experience", text="E3")
        db.soft_delete_kb_entry(id4)

        stats = db.get_kb_stats()
        assert stats["total"] == 3
        assert stats["by_category"]["experience"] == 2
        assert stats["by_category"]["skill"] == 1

    def test_search_by_text(self, db):
        """Search matches text content."""
        db.save_kb_entry(category="experience", text="Built microservices")
        db.save_kb_entry(category="experience", text="Led team meetings")

        results = db.get_kb_entries(search="microservices")
        assert len(results) == 1

    def test_search_by_tags(self, db):
        """Search matches tags."""
        db.save_kb_entry(category="skill", text="Programming", tags='["python","go"]')
        db.save_kb_entry(category="skill", text="Design", tags='["figma"]')

        results = db.get_kb_entries(search="python")
        assert len(results) == 1


class TestRoles:
    """Tests for roles CRUD."""

    def test_save_role(self, db):
        """Insert a role."""
        role_id = db.save_role(
            title="Senior Engineer",
            company="Acme Corp",
            start_date="2020-01",
            end_date="2023-01",
            domain="backend",
        )
        assert role_id is not None

    def test_dedup_role(self, db):
        """Duplicate (title, company, start_date) returns None."""
        db.save_role(title="Dev", company="Acme", start_date="2020-01")
        result = db.save_role(title="Dev", company="Acme", start_date="2020-01")
        assert result is None

    def test_get_roles(self, db):
        """List all roles ordered by start_date."""
        db.save_role(title="Junior", company="A", start_date="2018-01")
        db.save_role(title="Senior", company="B", start_date="2020-01")
        roles = db.get_roles()
        assert len(roles) == 2
        assert roles[0]["title"] == "Senior"  # most recent first


class TestMigration:
    """Tests for schema migration on existing DBs."""

    def test_migration_adds_reuse_columns(self, tmp_path):
        """Migration adds reuse columns to existing resume_versions table."""
        import sqlite3
        db_path = tmp_path / "old.db"

        # Create a DB with the OLD schema (no reuse columns)
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE applications (
                id INTEGER PRIMARY KEY, external_id TEXT, platform TEXT,
                job_title TEXT, company TEXT, location TEXT, salary TEXT,
                apply_url TEXT, match_score INTEGER, resume_path TEXT,
                cover_letter_path TEXT, cover_letter_text TEXT,
                description_path TEXT, status TEXT DEFAULT 'applied',
                error_message TEXT, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, notes TEXT
            );
            CREATE TABLE resume_versions (
                id INTEGER PRIMARY KEY, application_id INTEGER,
                job_title TEXT, company TEXT, resume_md_path TEXT,
                resume_pdf_path TEXT, match_score INTEGER,
                llm_provider TEXT, llm_model TEXT,
                is_favorite INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE feed_events (
                id INTEGER PRIMARY KEY, event_type TEXT,
                job_title TEXT, company TEXT, platform TEXT, message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.close()

        # Open with Database class — should migrate
        db = Database(db_path)
        conn = db._connect()
        rv_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(resume_versions)").fetchall()
        }
        conn.close()
        assert "reuse_source" in rv_cols
        assert "source_entry_ids" in rv_cols
