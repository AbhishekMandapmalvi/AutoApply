"""Integration tests for TASK-030 M1 — cross-component Knowledge Base flows.

Tests the full pipeline: Document Parser → Knowledge Base → Database → Resume Parser
→ Experience Calculator, verifying components work together correctly.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.document_parser import extract_text
from core.experience_calculator import calculate_experience
from core.knowledge_base import KnowledgeBase
from core.resume_parser import parse_resume_md
from db.database import Database


@pytest.fixture
def db(tmp_path):
    """Fresh database for integration tests."""
    return Database(tmp_path / "integ.db")


@pytest.fixture
def kb(db):
    """KnowledgeBase wired to real database."""
    return KnowledgeBase(db)


class TestUploadToKBPipeline:
    """Integration: file → extract_text → LLM → KB entries → query."""

    @patch("core.ai_engine.invoke_llm")
    def test_txt_upload_full_pipeline(self, mock_llm, kb, db, tmp_path):
        """Upload a TXT file, mock LLM extraction, verify entries in DB."""
        # Create a realistic resume file
        resume = tmp_path / "resume.txt"
        resume.write_text(
            "John Doe\n"
            "Senior Backend Engineer with 8 years experience\n\n"
            "Experience:\n"
            "Acme Corp — Senior Engineer (2020-2023)\n"
            "- Led migration to microservices, reducing latency by 40%\n"
            "- Managed team of 5 engineers\n\n"
            "Skills: Python, Go, Docker, Kubernetes, AWS",
            encoding="utf-8",
        )

        # LLM returns structured entries
        mock_llm.return_value = json.dumps([
            {
                "category": "summary",
                "text": "Senior Backend Engineer with 8 years of experience in distributed systems",
                "subsection": None,
                "job_types": ["backend", "fullstack"],
            },
            {
                "category": "experience",
                "text": "Led migration to microservices architecture, reducing API latency by 40%",
                "subsection": "Senior Engineer — Acme Corp (2020-2023)",
                "job_types": ["backend", "devops"],
            },
            {
                "category": "experience",
                "text": "Managed cross-functional team of 5 engineers across 2 time zones",
                "subsection": "Senior Engineer — Acme Corp (2020-2023)",
                "job_types": ["management", "backend"],
            },
            {
                "category": "skill",
                "text": "Python, Go, Docker, Kubernetes, AWS",
                "subsection": None,
                "job_types": ["backend", "devops", "cloud"],
            },
        ])

        # Run full pipeline
        inserted = kb.process_upload(
            resume,
            llm_config=MagicMock(provider="anthropic", model="claude-sonnet-4-20250514"),
        )
        assert inserted == 4

        # Verify entries in DB
        all_entries = kb.get_all_entries()
        assert len(all_entries) == 4

        # Filter by category
        exp_entries = kb.get_all_entries(category="experience")
        assert len(exp_entries) == 2

        skill_entries = kb.get_all_entries(category="skill")
        assert len(skill_entries) == 1

        # Search
        micro_results = kb.get_all_entries(search="microservices")
        assert len(micro_results) == 1

        # Stats
        stats = kb.get_stats()
        assert stats["total"] == 4
        assert stats["by_category"]["experience"] == 2

        # Verify upload document record
        docs = db.get_uploaded_documents()
        assert len(docs) == 1
        assert docs[0]["filename"] == "resume.txt"
        assert "John Doe" in docs[0]["raw_text"]

    @patch("core.ai_engine.invoke_llm")
    def test_upload_then_dedup_on_second_upload(self, mock_llm, kb, tmp_path):
        """Re-uploading same content produces no duplicate entries."""
        llm_response = json.dumps([
            {"category": "skill", "text": "Python, Flask, Django", "subsection": None, "job_types": ["backend"]},
        ])
        mock_llm.return_value = llm_response

        f = tmp_path / "skills.txt"
        f.write_text("Skills: Python, Flask, Django", encoding="utf-8")

        first = kb.process_upload(f, llm_config=MagicMock(provider="openai", model="gpt-4o"))
        assert first == 1

        # Second upload with same LLM response
        mock_llm.return_value = llm_response
        second = kb.process_upload(f, llm_config=MagicMock(provider="openai", model="gpt-4o"))
        assert second == 0  # dedup prevents duplicates

        assert len(kb.get_all_entries()) == 1

    @patch("core.ai_engine.invoke_llm")
    def test_upload_with_copy_to_dir(self, mock_llm, kb, tmp_path):
        """Upload copies file to upload_dir when specified."""
        mock_llm.return_value = json.dumps([
            {"category": "experience", "text": "Built APIs", "subsection": None, "job_types": ["backend"]},
        ])

        source = tmp_path / "source" / "resume.txt"
        source.parent.mkdir()
        source.write_text("Resume content", encoding="utf-8")

        upload_dir = tmp_path / "uploads"
        kb.process_upload(source, llm_config=MagicMock(provider="anthropic", model="test"), upload_dir=upload_dir)

        assert (upload_dir / "resume.txt").exists()


class TestResumeParserToKBPipeline:
    """Integration: parse_resume_md → ingest_entries → DB query."""

    def test_parse_and_ingest_full_resume(self, kb):
        """Parse a markdown resume and ingest all entries into KB."""
        md_text = (
            "# Jane Smith\n"
            "jane@example.com | 555-1234 | San Francisco, CA\n\n"
            "## Summary\n"
            "Experienced backend engineer with 10 years in distributed systems.\n\n"
            "## Experience\n"
            "### Senior Dev — Acme Corp (2020-2023)\n"
            "- Built microservices serving 10M requests/day\n"
            "- Led team of 5 engineers\n\n"
            "### Junior Dev — StartupCo (2018-2020)\n"
            "- Developed REST APIs for mobile app\n\n"
            "## Skills\n"
            "Python, Go, Docker, Kubernetes\n\n"
            "## Education\n"
            "BS Computer Science — MIT (2016)\n"
            "MS Data Science — Stanford (2018)\n\n"
            "## Certifications\n"
            "- AWS Solutions Architect\n"
            "- Google Cloud Professional\n"
        )

        entries = parse_resume_md(md_text)
        assert len(entries) >= 8  # summary + 3 exp + skill + 2 edu + 2 certs

        inserted = kb.ingest_entries(entries)
        assert inserted >= 8

        # Verify via KB queries
        all_entries = kb.get_all_entries()
        assert len(all_entries) >= 8

        categories = {e["category"] for e in all_entries}
        assert "summary" in categories
        assert "experience" in categories
        assert "skill" in categories
        assert "education" in categories
        assert "certification" in categories

        # Subsection preserved for experience
        exp = kb.get_all_entries(category="experience")
        subsections = {e["subsection"] for e in exp if e["subsection"]}
        assert any("Acme" in s for s in subsections)

    def test_ingest_then_dedup_on_reingest(self, kb):
        """Re-ingesting same resume produces no duplicates."""
        md = "## Skills\nPython, Go, Docker"
        entries = parse_resume_md(md)

        first = kb.ingest_entries(entries)
        second = kb.ingest_entries(entries)

        assert first == 1
        assert second == 0
        assert len(kb.get_all_entries()) == 1


class TestExperienceCalculatorIntegration:
    """Integration: roles in DB → calculate_experience."""

    def test_calculate_from_stored_roles(self, db):
        """Calculate experience from roles stored in DB."""
        db.save_role(
            title="Senior Engineer",
            company="Acme Corp",
            start_date="2020-01",
            end_date="2023-06",
            domain="backend",
        )
        db.save_role(
            title="Junior Dev",
            company="StartupCo",
            start_date="2018-01",
            end_date="2019-12",
            domain="fullstack",
        )

        result = calculate_experience(db)
        assert result["total_years"] > 0
        assert "backend" in result["by_domain"]
        assert "fullstack" in result["by_domain"]
        assert result["by_domain"]["backend"] >= 3.0

    def test_roles_dedup(self, db):
        """Duplicate roles are not inserted twice."""
        id1 = db.save_role(
            title="Engineer", company="Acme", start_date="2020-01",
        )
        id2 = db.save_role(
            title="Engineer", company="Acme", start_date="2020-01",
        )
        assert id1 is not None
        assert id2 is None


class TestCRUDLifecycle:
    """Integration: create → read → update → soft-delete → verify."""

    def test_full_entry_lifecycle(self, kb, db):
        """Test complete CRUD lifecycle of a KB entry."""
        # Create
        entry_id = db.save_kb_entry(
            category="experience",
            text="Original: Built REST APIs for mobile app",
            subsection="Dev — StartupCo (2018-2020)",
            job_types=json.dumps(["backend"]),
        )
        assert entry_id is not None

        # Read
        entry = kb.get_entry(entry_id)
        assert entry["text"] == "Original: Built REST APIs for mobile app"

        # Update
        kb.update_entry(
            entry_id,
            text="Improved: Developed and maintained REST APIs serving 1M daily active users",
            tags="api,rest,mobile",
        )
        updated = kb.get_entry(entry_id)
        assert "1M daily active users" in updated["text"]
        assert updated["tags"] == "api,rest,mobile"
        assert updated["updated_at"] is not None

        # Soft delete
        kb.soft_delete_entry(entry_id)

        # Verify excluded from active queries
        active = kb.get_all_entries(active_only=True)
        assert all(e["id"] != entry_id for e in active)

        # Verify included in all queries
        all_entries = kb.get_all_entries(active_only=False)
        deleted = [e for e in all_entries if e["id"] == entry_id]
        assert len(deleted) == 1
        assert deleted[0]["is_active"] == 0


class TestDocumentParserToKB:
    """Integration: extract_text → KB ingestion (without LLM)."""

    def test_extract_md_then_parse_and_ingest(self, kb, tmp_path):
        """Extract text from .md file, parse as resume, ingest into KB."""
        md_file = tmp_path / "resume.md"
        md_file.write_text(
            "## Summary\nExperienced engineer.\n\n"
            "## Experience\n"
            "### Dev — Corp\n"
            "- Built systems\n\n"
            "## Skills\nPython, Go\n",
            encoding="utf-8",
        )

        # Extract text
        text = extract_text(md_file)
        assert "Experienced engineer" in text

        # Parse as resume
        entries = parse_resume_md(text)
        assert len(entries) >= 3

        # Ingest into KB
        inserted = kb.ingest_entries(entries)
        assert inserted >= 3

        # Query back
        stats = kb.get_stats()
        assert stats["total"] >= 3


class TestDatabaseMigration:
    """Integration: verify migration adds new tables/columns to existing DBs."""

    def test_fresh_db_has_all_tables(self, tmp_path):
        """A fresh database has all M1 tables."""
        db = Database(tmp_path / "fresh.db")
        conn = db._connect()

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "knowledge_base" in tables
        assert "uploaded_documents" in tables
        assert "roles" in tables
        assert "resume_versions" in tables

    def test_resume_versions_has_reuse_columns(self, tmp_path):
        """resume_versions table has reuse_source and source_entry_ids columns."""
        db = Database(tmp_path / "cols.db")
        conn = db._connect()

        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(resume_versions)").fetchall()
        }
        assert "reuse_source" in columns
        assert "source_entry_ids" in columns
