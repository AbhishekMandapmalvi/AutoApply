"""Tests for core/resume_assembler.py — TASK-030 M4.

Tests resume assembly pipeline, entry selection, context building,
bot integration (KB-first flow), LLM ingestion, and save_resume_version
with reuse_source/source_entry_ids columns.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from config.settings import LatexConfig, ResumeReuseConfig
from core.resume_assembler import (
    _build_context,
    _select_entries,
    assemble_resume,
    ingest_llm_resume,
    save_assembled_resume,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_profile():
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0100",
        "location": "San Francisco, CA",
    }


@pytest.fixture
def sample_scored_entries():
    """Scored KB entries with enough per category."""
    entries = []
    for i in range(8):
        entries.append({
            "id": i + 1,
            "text": f"Built feature {i} using Python and Flask",
            "category": "experience",
            "subsection": f"Company {i} — Engineer",
            "score": 0.9 - (i * 0.05),
            "scoring_method": "tfidf",
        })
    for i in range(4):
        entries.append({
            "id": 20 + i,
            "text": f"Python, Flask, Docker, AWS skill set {i}",
            "category": "skill",
            "subsection": "",
            "score": 0.85 - (i * 0.05),
            "scoring_method": "tfidf",
        })
    for i in range(2):
        entries.append({
            "id": 30 + i,
            "text": f"M.S. Computer Science, 202{i}",
            "category": "education",
            "subsection": f"University {i}",
            "score": 0.80 - (i * 0.05),
            "scoring_method": "tfidf",
        })
    return entries


@pytest.fixture
def mock_kb(sample_scored_entries):
    """Mock KnowledgeBase returning sample entries."""
    kb = MagicMock()
    # Return raw entries (without score) for get_all_entries
    raw = [{k: v for k, v in e.items() if k not in ("score", "scoring_method")} for e in sample_scored_entries]
    kb.get_all_entries.return_value = raw
    return kb


# ---------------------------------------------------------------------------
# Entry Selection Tests
# ---------------------------------------------------------------------------


class TestSelectEntries:
    """Tests for _select_entries()."""

    def test_select_sufficient_entries(self, sample_scored_entries):
        cfg = ResumeReuseConfig(min_experience_bullets=3)
        result = _select_entries(sample_scored_entries, cfg)
        assert result is not None
        assert "experience" in result
        assert "skill" in result
        assert "education" in result

    def test_select_respects_max_per_category(self, sample_scored_entries):
        cfg = ResumeReuseConfig(min_experience_bullets=3)
        result = _select_entries(sample_scored_entries, cfg)
        assert result is not None
        assert len(result["experience"]) <= 8
        assert len(result["skill"]) <= 6
        assert len(result["education"]) <= 3

    def test_select_insufficient_experience(self):
        entries = [
            {"id": 1, "text": "One bullet", "category": "experience", "score": 0.9},
            {"id": 2, "text": "Skill", "category": "skill", "score": 0.8},
            {"id": 3, "text": "Skill 2", "category": "skill", "score": 0.7},
            {"id": 4, "text": "Edu", "category": "education", "score": 0.6},
        ]
        cfg = ResumeReuseConfig(min_experience_bullets=6)
        assert _select_entries(entries, cfg) is None

    def test_select_insufficient_skills(self):
        entries = [
            {"id": i, "text": f"Exp {i}", "category": "experience", "score": 0.9}
            for i in range(6)
        ] + [
            {"id": 20, "text": "One skill", "category": "skill", "score": 0.8},
            {"id": 30, "text": "Edu", "category": "education", "score": 0.7},
        ]
        cfg = ResumeReuseConfig(min_experience_bullets=3)
        assert _select_entries(entries, cfg) is None

    def test_select_insufficient_education(self):
        entries = [
            {"id": i, "text": f"Exp {i}", "category": "experience", "score": 0.9}
            for i in range(6)
        ] + [
            {"id": 20, "text": "Skill 1", "category": "skill", "score": 0.8},
            {"id": 21, "text": "Skill 2", "category": "skill", "score": 0.7},
        ]
        cfg = ResumeReuseConfig(min_experience_bullets=3)
        assert _select_entries(entries, cfg) is None


# ---------------------------------------------------------------------------
# Context Building Tests
# ---------------------------------------------------------------------------


class TestBuildContext:
    """Tests for _build_context()."""

    def test_builds_valid_context(self, sample_profile):
        selected = {
            "experience": [{"id": 1, "text": "Built APIs", "subsection": "TechCorp"}],
            "skill": [{"id": 2, "text": "Python, Flask"}],
            "education": [{"id": 3, "text": "M.S. CS", "subsection": "Stanford"}],
        }
        ctx = _build_context(sample_profile, selected)
        assert ctx["name"] == "Jane Doe"
        assert ctx["email"] == "jane@example.com"
        assert len(ctx["experience"]) == 1
        assert ctx["experience"][0]["text"] == "Built APIs"
        assert ctx["skills"][0]["text"] == "Python, Flask"

    def test_context_uses_summary_entry(self, sample_profile):
        selected = {
            "summary": [{"id": 99, "text": "Senior engineer with 10 years experience"}],
            "experience": [],
            "skill": [],
            "education": [],
        }
        ctx = _build_context(sample_profile, selected)
        assert ctx["summary"] == "Senior engineer with 10 years experience"

    def test_context_empty_summary(self, sample_profile):
        selected = {"experience": [], "skill": [], "education": []}
        ctx = _build_context(sample_profile, selected)
        assert ctx["summary"] == ""

    def test_context_empty_optional_sections(self, sample_profile):
        selected = {"experience": [], "skill": [], "education": []}
        ctx = _build_context(sample_profile, selected)
        assert ctx["projects"] == []
        assert ctx["certifications"] == []


# ---------------------------------------------------------------------------
# Full Assembly Tests
# ---------------------------------------------------------------------------


class TestAssembleResume:
    """Tests for assemble_resume()."""

    def test_assembly_success(self, sample_profile, mock_kb):
        fake_pdf = b"%PDF-1.4 assembled"
        cfg = ResumeReuseConfig(min_experience_bullets=3, min_score=0.5)

        with patch("core.resume_assembler.score_kb_entries") as mock_score, \
             patch("core.resume_assembler.find_pdflatex", return_value="/usr/bin/pdflatex"), \
             patch("core.resume_assembler.compile_resume", return_value=fake_pdf):
            # Return scored entries with enough per category
            scored = [
                {"id": i, "text": f"Exp {i}", "category": "experience", "subsection": f"Co {i}", "score": 0.9, "scoring_method": "tfidf"}
                for i in range(8)
            ] + [
                {"id": 20 + i, "text": f"Skill {i}", "category": "skill", "score": 0.8, "scoring_method": "tfidf"}
                for i in range(3)
            ] + [
                {"id": 30, "text": "M.S. CS", "category": "education", "subsection": "Stanford", "score": 0.7, "scoring_method": "tfidf"},
            ]
            mock_score.return_value = scored

            result = assemble_resume("JD text here", sample_profile, mock_kb, cfg)

        assert result is not None
        assert result["pdf_bytes"] == fake_pdf
        assert len(result["entry_ids"]) > 0
        assert result["template"] == "classic"

    def test_assembly_disabled(self, sample_profile, mock_kb):
        cfg = ResumeReuseConfig(enabled=False)
        result = assemble_resume("JD text", sample_profile, mock_kb, cfg)
        assert result is None

    def test_assembly_empty_kb(self, sample_profile):
        kb = MagicMock()
        kb.get_all_entries.return_value = []
        result = assemble_resume("JD text", sample_profile, kb)
        assert result is None

    def test_assembly_no_pdflatex(self, sample_profile, mock_kb):
        cfg = ResumeReuseConfig(min_experience_bullets=3, min_score=0.5)
        scored = [
            {"id": i, "text": f"Exp {i}", "category": "experience", "subsection": "", "score": 0.9, "scoring_method": "tfidf"}
            for i in range(8)
        ] + [
            {"id": 20 + i, "text": f"Skill {i}", "category": "skill", "score": 0.8, "scoring_method": "tfidf"}
            for i in range(3)
        ] + [
            {"id": 30, "text": "Edu", "category": "education", "subsection": "", "score": 0.7, "scoring_method": "tfidf"},
        ]

        with patch("core.resume_assembler.score_kb_entries", return_value=scored), \
             patch("core.resume_assembler.find_pdflatex", return_value=None):
            result = assemble_resume("JD text", sample_profile, mock_kb, cfg)

        assert result is None

    def test_assembly_custom_template(self, sample_profile, mock_kb):
        fake_pdf = b"%PDF-1.4 modern"
        cfg = ResumeReuseConfig(min_experience_bullets=3, min_score=0.5)
        lcfg = LatexConfig(template="modern")
        scored = [
            {"id": i, "text": f"Exp {i}", "category": "experience", "subsection": "", "score": 0.9, "scoring_method": "tfidf"}
            for i in range(8)
        ] + [
            {"id": 20 + i, "text": f"Skill {i}", "category": "skill", "score": 0.8, "scoring_method": "tfidf"}
            for i in range(3)
        ] + [
            {"id": 30, "text": "Edu", "category": "education", "subsection": "", "score": 0.7, "scoring_method": "tfidf"},
        ]

        with patch("core.resume_assembler.score_kb_entries", return_value=scored), \
             patch("core.resume_assembler.find_pdflatex", return_value="/usr/bin/pdflatex"), \
             patch("core.resume_assembler.compile_resume", return_value=fake_pdf) as mock_compile:
            result = assemble_resume("JD text", sample_profile, mock_kb, cfg, lcfg)

        assert result is not None
        assert result["template"] == "modern"
        mock_compile.assert_called_once()
        assert mock_compile.call_args[0][0] == "modern"


# ---------------------------------------------------------------------------
# Save Assembled Resume Tests
# ---------------------------------------------------------------------------


class TestSaveAssembledResume:
    """Tests for save_assembled_resume()."""

    def test_save_creates_file(self, tmp_path):
        pdf = b"%PDF-1.4 test content"
        path = save_assembled_resume(pdf, tmp_path, "TechCorp", "Backend Engineer")
        assert path.exists()
        assert path.read_bytes() == pdf
        assert "TechCorp" in path.name
        assert "Backend" in path.name

    def test_save_sanitizes_filename(self, tmp_path):
        pdf = b"%PDF-1.4 test"
        path = save_assembled_resume(pdf, tmp_path, "O'Brien & Co.", "C# Dev / Lead")
        assert path.exists()
        # Special chars should be stripped
        assert "'" not in path.name
        assert "&" not in path.name

    def test_save_creates_directory(self, tmp_path):
        pdf = b"%PDF-1.4"
        output = tmp_path / "nested" / "dir"
        path = save_assembled_resume(pdf, output, "Test", "Job")
        assert path.exists()
        assert output.exists()


# ---------------------------------------------------------------------------
# LLM Ingestion Tests
# ---------------------------------------------------------------------------


class TestIngestLlmResume:
    """Tests for ingest_llm_resume()."""

    def test_ingest_parses_and_inserts(self):
        kb = MagicMock()
        kb.ingest_entries.return_value = 3

        md = """# Jane Doe

## Experience
- Built APIs using Python and Flask
- Designed CI/CD pipeline

## Skills
- Python, Docker, AWS
"""
        with patch("core.resume_parser.parse_resume_md") as mock_parse:
            mock_parse.return_value = [
                {"category": "experience", "text": "Built APIs using Python and Flask"},
                {"category": "experience", "text": "Designed CI/CD pipeline"},
                {"category": "skill", "text": "Python, Docker, AWS"},
            ]
            count = ingest_llm_resume(md, kb)

        assert count == 3
        kb.ingest_entries.assert_called_once()

    def test_ingest_empty_resume(self):
        kb = MagicMock()
        with patch("core.resume_parser.parse_resume_md", return_value=[]):
            count = ingest_llm_resume("", kb)
        assert count == 0
        kb.ingest_entries.assert_not_called()

    def test_ingest_tags_entries_as_llm_generated(self):
        kb = MagicMock()
        kb.ingest_entries.return_value = 1

        with patch("core.resume_parser.parse_resume_md") as mock_parse:
            mock_parse.return_value = [
                {"category": "experience", "text": "Built APIs"},
            ]
            ingest_llm_resume("# Resume\n## Experience\n- Built APIs", kb)

        # Verify the entries passed to ingest_entries have llm-generated tag
        call_args = kb.ingest_entries.call_args[0][0]
        assert any("llm-generated" in str(e.get("tags", "")) for e in call_args)


# ---------------------------------------------------------------------------
# Database Integration Tests
# ---------------------------------------------------------------------------


class TestSaveResumeVersionReuse:
    """Tests for save_resume_version with reuse_source/source_entry_ids."""

    @staticmethod
    def _create_app(db, ext_id="ext-123", platform="linkedin",
                    title="Engineer", company="TechCorp"):
        """Helper: create a minimal application record."""
        return db.save_application(
            external_id=ext_id, platform=platform,
            job_title=title, company=company,
            location=None, salary=None, apply_url="https://example.com",
            match_score=85, resume_path=None, cover_letter_path=None,
            cover_letter_text=None, status="applied", error_message=None,
        )

    def test_save_with_reuse_source(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        app_id = self._create_app(db)

        version_id = db.save_resume_version(
            application_id=app_id,
            job_title="Engineer",
            company="TechCorp",
            resume_md_path="",
            resume_pdf_path="/path/to/resume.pdf",
            match_score=85,
            llm_provider=None,
            llm_model=None,
            reuse_source="kb_assembly",
            source_entry_ids=json.dumps([1, 2, 3, 4, 5]),
        )

        assert version_id is not None
        version = db.get_resume_version(version_id)
        assert version is not None
        assert version["reuse_source"] == "kb_assembly"
        assert json.loads(version["source_entry_ids"]) == [1, 2, 3, 4, 5]

    def test_save_with_llm_source(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        app_id = self._create_app(db, "ext-456", "indeed", "Developer", "DevCo")

        version_id = db.save_resume_version(
            application_id=app_id,
            job_title="Developer",
            company="DevCo",
            resume_md_path="/path/resume.md",
            resume_pdf_path="/path/resume.pdf",
            match_score=90,
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-20250514",
            reuse_source="llm_generated",
            source_entry_ids=None,
        )

        version = db.get_resume_version(version_id)
        assert version["reuse_source"] == "llm_generated"
        assert version["source_entry_ids"] is None
        assert version["llm_provider"] == "anthropic"

    def test_backward_compat_no_reuse_fields(self, tmp_path):
        """Existing callers that don't pass reuse_source should still work."""
        from db.database import Database

        db = Database(tmp_path / "test.db")
        app_id = self._create_app(db, "ext-789", "greenhouse", "SRE", "CloudCo")

        version_id = db.save_resume_version(
            application_id=app_id,
            job_title="SRE",
            company="CloudCo",
            resume_md_path="/path/resume.md",
            resume_pdf_path="/path/resume.pdf",
            match_score=80,
            llm_provider="openai",
            llm_model="gpt-4o",
        )

        version = db.get_resume_version(version_id)
        assert version["reuse_source"] is None
        assert version["source_entry_ids"] is None
