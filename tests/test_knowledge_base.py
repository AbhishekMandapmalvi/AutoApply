"""Tests for core/knowledge_base.py — TASK-030 M1.

Tests KB CRUD, LLM extraction, dedup, resume ingestion, and stats.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.knowledge_base import VALID_CATEGORIES, KnowledgeBase
from db.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def kb(db):
    """Create a KnowledgeBase instance."""
    return KnowledgeBase(db)


class TestKBCrud:
    """Tests for KB entry CRUD operations."""

    def test_save_and_get_entry(self, kb, db):
        """Insert and retrieve a KB entry."""
        entry_id = db.save_kb_entry(
            category="experience",
            text="Led migration to microservices, reducing latency by 40%",
            subsection="Senior Engineer — Acme Corp (2020-2023)",
            job_types=json.dumps(["backend", "devops"]),
        )
        assert entry_id is not None

        entry = kb.get_entry(entry_id)
        assert entry is not None
        assert entry["category"] == "experience"
        assert "microservices" in entry["text"]
        assert entry["subsection"] == "Senior Engineer — Acme Corp (2020-2023)"

    def test_dedup_on_insert(self, db):
        """Duplicate (category, text) entries return None."""
        id1 = db.save_kb_entry(category="skill", text="Python, Flask, Django")
        id2 = db.save_kb_entry(category="skill", text="Python, Flask, Django")
        assert id1 is not None
        assert id2 is None  # duplicate

    def test_different_category_same_text(self, db):
        """Same text in different categories is NOT a duplicate."""
        id1 = db.save_kb_entry(category="experience", text="Managed team of 5 engineers")
        id2 = db.save_kb_entry(category="summary", text="Managed team of 5 engineers")
        assert id1 is not None
        assert id2 is not None

    def test_get_all_entries(self, kb, db):
        """Retrieve all active entries."""
        db.save_kb_entry(category="experience", text="Built REST APIs")
        db.save_kb_entry(category="skill", text="Python, Go")
        db.save_kb_entry(category="education", text="BS Computer Science — MIT")

        entries = kb.get_all_entries()
        assert len(entries) == 3

    def test_filter_by_category(self, kb, db):
        """Filter entries by category."""
        db.save_kb_entry(category="experience", text="Entry 1")
        db.save_kb_entry(category="skill", text="Entry 2")

        exp = kb.get_all_entries(category="experience")
        assert len(exp) == 1
        assert exp[0]["category"] == "experience"

    def test_search_filter(self, kb, db):
        """Search filters by text content."""
        db.save_kb_entry(category="experience", text="Built microservices with Go")
        db.save_kb_entry(category="experience", text="Managed Python automation")

        results = kb.get_all_entries(search="microservices")
        assert len(results) == 1
        assert "microservices" in results[0]["text"]

    def test_update_entry(self, kb, db):
        """Update entry text and tags."""
        entry_id = db.save_kb_entry(category="experience", text="Old text")
        result = kb.update_entry(entry_id, text="New text", tags='["python"]')
        assert result is True

        entry = kb.get_entry(entry_id)
        assert entry["text"] == "New text"
        assert entry["tags"] == '["python"]'

    def test_update_nonexistent(self, kb):
        """Update on non-existent entry returns False."""
        assert kb.update_entry(9999, text="anything") is False

    def test_soft_delete(self, kb, db):
        """Soft-deleted entries are excluded from active queries."""
        entry_id = db.save_kb_entry(category="experience", text="To delete")
        assert kb.soft_delete_entry(entry_id) is True

        # Active query excludes it
        entries = kb.get_all_entries(active_only=True)
        assert len(entries) == 0

        # Include inactive shows it
        entries = kb.get_all_entries(active_only=False)
        assert len(entries) == 1
        assert entries[0]["is_active"] == 0

    def test_get_entries_by_ids(self, kb, db):
        """Fetch entries by specific IDs, preserving order."""
        id1 = db.save_kb_entry(category="experience", text="Entry A")
        _id2 = db.save_kb_entry(category="skill", text="Entry B")
        id3 = db.save_kb_entry(category="education", text="Entry C")

        # Request in reverse order
        entries = kb.get_entries_by_ids([id3, id1])
        assert len(entries) == 2
        assert entries[0]["id"] == id3
        assert entries[1]["id"] == id1

    def test_get_entries_by_ids_empty(self, kb):
        """Empty ID list returns empty list."""
        assert kb.get_entries_by_ids([]) == []

    def test_get_stats(self, kb, db):
        """KB stats returns total and by_category counts."""
        db.save_kb_entry(category="experience", text="E1")
        db.save_kb_entry(category="experience", text="E2")
        db.save_kb_entry(category="skill", text="S1")

        stats = kb.get_stats()
        assert stats["total"] == 3
        assert stats["by_category"]["experience"] == 2
        assert stats["by_category"]["skill"] == 1


class TestKBIngestion:
    """Tests for entry ingestion (from resume parser or manual)."""

    def test_ingest_entries(self, kb):
        """Ingest pre-parsed entries into KB."""
        entries = [
            {"category": "experience", "text": "Built APIs"},
            {"category": "skill", "text": "Python, Go"},
            {"category": "invalid_cat", "text": "Should be skipped"},
            {"category": "experience", "text": ""},  # empty text, skipped
        ]
        inserted = kb.ingest_entries(entries)
        assert inserted == 2

    def test_ingest_generated_resume(self, kb, tmp_path):
        """Ingest an LLM-generated markdown resume."""
        md = tmp_path / "resume.md"
        md.write_text(
            "# Jane Smith\n"
            "## Summary\nExperienced backend engineer.\n"
            "## Experience\n### Senior Dev — Acme (2020-2023)\n"
            "- Built microservices\n- Led team of 5\n"
            "## Skills\nPython, Go, Docker\n",
            encoding="utf-8",
        )
        inserted = kb.ingest_generated_resume(md)
        assert inserted >= 3  # summary + 2 experience + skills

    def test_ingest_nonexistent_resume(self, kb, tmp_path):
        """Non-existent resume file returns 0."""
        result = kb.ingest_generated_resume(tmp_path / "missing.md")
        assert result == 0


class TestKBLLMExtraction:
    """Tests for LLM-based extraction."""

    @patch("core.ai_engine.invoke_llm")
    def test_extract_via_llm_success(self, mock_llm, kb, db, tmp_path):
        """Successful LLM extraction parses JSON and inserts entries."""
        mock_llm.return_value = json.dumps([
            {
                "category": "experience",
                "text": "Built REST APIs serving 10M requests/day",
                "subsection": "Senior Dev — Acme Corp (2020-2023)",
                "job_types": ["backend"],
            },
            {
                "category": "skill",
                "text": "Python, Flask, Django, PostgreSQL",
                "subsection": None,
                "job_types": ["backend", "fullstack"],
            },
        ])

        f = tmp_path / "resume.txt"
        f.write_text("I worked at Acme Corp...", encoding="utf-8")

        inserted = kb.process_upload(f, llm_config=MagicMock(provider="anthropic", model="test"))
        assert inserted == 2

        entries = kb.get_all_entries()
        assert len(entries) == 2

    @patch("core.ai_engine.invoke_llm")
    def test_extract_via_llm_markdown_fences(self, mock_llm, kb, db, tmp_path):
        """LLM response wrapped in markdown code fences is handled."""
        mock_llm.return_value = '```json\n[{"category":"skill","text":"Python"}]\n```'

        f = tmp_path / "doc.txt"
        f.write_text("Skills: Python", encoding="utf-8")

        inserted = kb.process_upload(f, llm_config=MagicMock(provider="openai", model="test"))
        assert inserted == 1

    @patch("core.ai_engine.invoke_llm")
    def test_extract_via_llm_invalid_json(self, mock_llm, kb, tmp_path):
        """Invalid JSON response returns 0 entries."""
        mock_llm.return_value = "Not valid JSON at all"

        f = tmp_path / "doc.txt"
        f.write_text("Some content", encoding="utf-8")

        inserted = kb.process_upload(f, llm_config=MagicMock(provider="anthropic", model="test"))
        assert inserted == 0

    @patch("core.ai_engine.invoke_llm")
    def test_extract_filters_invalid_categories(self, mock_llm, kb, tmp_path):
        """Invalid categories in LLM response are filtered out."""
        mock_llm.return_value = json.dumps([
            {"category": "experience", "text": "Valid entry"},
            {"category": "hobbies", "text": "Playing guitar"},  # invalid
        ])

        f = tmp_path / "doc.txt"
        f.write_text("Content", encoding="utf-8")

        inserted = kb.process_upload(f, llm_config=MagicMock(provider="anthropic", model="test"))
        assert inserted == 1

    def test_process_upload_empty_file(self, kb, tmp_path):
        """Empty file returns 0 entries without LLM call."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = kb.process_upload(f, llm_config=MagicMock())
        assert result == 0


class TestValidCategories:
    """Tests for VALID_CATEGORIES constant."""

    def test_expected_categories(self):
        """All expected categories are present."""
        assert "experience" in VALID_CATEGORIES
        assert "skill" in VALID_CATEGORIES
        assert "education" in VALID_CATEGORIES
        assert "project" in VALID_CATEGORIES
        assert "summary" in VALID_CATEGORIES
        assert "certification" in VALID_CATEGORIES

    def test_invalid_category_not_present(self):
        """Random strings are not valid categories."""
        assert "hobbies" not in VALID_CATEGORIES
        assert "interests" not in VALID_CATEGORIES
