"""Tests for TASK-030 M10 — Migration + Polish.

Covers: core/kb_migrator.py (auto-migration of .txt and .md files),
        core/latex_compiler.py (backslash escaping hardening).
"""

from __future__ import annotations

import json

import pytest

from db.database import Database

# ---------------------------------------------------------------------------
# KB Migrator tests
# ---------------------------------------------------------------------------


class TestMigrationMarker:
    """Tests for migration state tracking."""

    def test_needs_migration_first_run(self, tmp_path):
        from core.kb_migrator import needs_migration

        assert needs_migration(tmp_path) is True

    def test_needs_migration_after_mark(self, tmp_path):
        from core.kb_migrator import mark_migrated, needs_migration

        mark_migrated(tmp_path)
        assert needs_migration(tmp_path) is False

    def test_marker_file_created(self, tmp_path):
        from core.kb_migrator import mark_migrated

        mark_migrated(tmp_path)
        assert (tmp_path / ".kb_migrated").exists()


class TestMigrateExperienceFiles:
    """Tests for .txt experience file migration."""

    @pytest.fixture()
    def kb(self, tmp_path):
        from core.knowledge_base import KnowledgeBase

        db = Database(tmp_path / "test.db")
        return KnowledgeBase(db)

    def test_no_directory(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        count = migrate_experience_files(tmp_path / "nonexistent", kb)
        assert count == 0

    def test_empty_directory(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        exp_dir = tmp_path / "experiences"
        exp_dir.mkdir()
        count = migrate_experience_files(exp_dir, kb)
        assert count == 0

    def test_readme_skipped(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        exp_dir = tmp_path / "experiences"
        exp_dir.mkdir()
        (exp_dir / "README.txt").write_text("This is a readme", encoding="utf-8")

        count = migrate_experience_files(exp_dir, kb)
        assert count == 0

    def test_single_file_migration(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        exp_dir = tmp_path / "experiences"
        exp_dir.mkdir()
        (exp_dir / "backend.txt").write_text(
            "- Built REST APIs serving 10k requests per second\n"
            "- Designed PostgreSQL schema for user analytics\n"
            "- Led migration from monolith to microservices\n",
            encoding="utf-8",
        )

        count = migrate_experience_files(exp_dir, kb)
        assert count == 3

    def test_multiple_files(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        exp_dir = tmp_path / "experiences"
        exp_dir.mkdir()
        (exp_dir / "dev.txt").write_text(
            "- Built REST APIs in Python\n- Deployed to AWS\n",
            encoding="utf-8",
        )
        (exp_dir / "skills.txt").write_text(
            "Python programming language\nJavaScript and React\n",
            encoding="utf-8",
        )

        count = migrate_experience_files(exp_dir, kb)
        assert count >= 3

    def test_short_lines_skipped(self, kb, tmp_path):
        from core.kb_migrator import migrate_experience_files

        exp_dir = tmp_path / "experiences"
        exp_dir.mkdir()
        (exp_dir / "test.txt").write_text(
            "Hi\n\n- Built REST APIs in Python\n",
            encoding="utf-8",
        )

        count = migrate_experience_files(exp_dir, kb)
        assert count == 1  # Only the long line


class TestMigrateResumeFiles:
    """Tests for .md resume file migration."""

    @pytest.fixture()
    def kb(self, tmp_path):
        from core.knowledge_base import KnowledgeBase

        db = Database(tmp_path / "test.db")
        return KnowledgeBase(db)

    def test_no_directory(self, kb, tmp_path):
        from core.kb_migrator import migrate_resume_files

        count = migrate_resume_files(tmp_path / "nonexistent", kb)
        assert count == 0

    def test_empty_directory(self, kb, tmp_path):
        from core.kb_migrator import migrate_resume_files

        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        count = migrate_resume_files(resumes_dir, kb)
        assert count == 0

    def test_md_file_migration(self, kb, tmp_path):
        from core.kb_migrator import migrate_resume_files

        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        (resumes_dir / "resume_acme.md").write_text(
            "## Experience\n"
            "### Senior Developer — Acme Corp\n"
            "- Built scalable REST APIs serving 10k+ rps\n"
            "- Led team of 5 engineers on platform rewrite\n"
            "\n"
            "## Skills\n"
            "- Python, Django, PostgreSQL, Redis\n",
            encoding="utf-8",
        )

        count = migrate_resume_files(resumes_dir, kb)
        assert count >= 2  # At least experience + skills

    def test_entries_tagged_migrated(self, kb, tmp_path):
        from core.kb_migrator import migrate_resume_files

        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        (resumes_dir / "resume.md").write_text(
            "## Experience\n"
            "### Dev — Corp\n"
            "- Built APIs for analytics platform\n",
            encoding="utf-8",
        )

        migrate_resume_files(resumes_dir, kb)
        entries = kb.get_all_entries()
        for entry in entries:
            tags = entry.get("tags")
            if tags:
                tag_list = json.loads(tags)
                assert "migrated" in tag_list


class TestRunMigration:
    """Tests for the full migration pipeline."""

    @pytest.fixture()
    def kb(self, tmp_path):
        from core.knowledge_base import KnowledgeBase

        db = Database(tmp_path / "test.db")
        return KnowledgeBase(db)

    def test_skip_if_already_migrated(self, kb, tmp_path):
        from core.kb_migrator import mark_migrated, run_migration

        mark_migrated(tmp_path)
        result = run_migration(tmp_path, kb)
        assert result["migrated"] is False
        assert result["skipped_reason"] == "already_migrated"

    def test_full_migration(self, kb, tmp_path):
        from core.kb_migrator import run_migration

        exp_dir = tmp_path / "profile" / "experiences"
        exp_dir.mkdir(parents=True)
        (exp_dir / "work.txt").write_text(
            "- Built REST APIs in Python\n",
            encoding="utf-8",
        )

        resumes_dir = tmp_path / "resumes"
        resumes_dir.mkdir()
        (resumes_dir / "resume.md").write_text(
            "## Experience\n### Dev — Corp\n- Led team of 5 engineers\n",
            encoding="utf-8",
        )

        result = run_migration(tmp_path, kb)
        assert result["migrated"] is True
        assert result["txt_entries"] >= 1
        assert result["md_entries"] >= 1

    def test_migration_creates_marker(self, kb, tmp_path):
        from core.kb_migrator import needs_migration, run_migration

        run_migration(tmp_path, kb)
        assert needs_migration(tmp_path) is False

    def test_migration_empty_dirs(self, kb, tmp_path):
        from core.kb_migrator import run_migration

        result = run_migration(tmp_path, kb)
        assert result["migrated"] is True
        assert result.get("txt_entries", 0) == 0
        assert result.get("md_entries", 0) == 0


class TestCategoryGuessing:
    """Tests for _guess_category heuristic."""

    def test_experience_default(self):
        from core.kb_migrator import _guess_category

        assert _guess_category("Built REST APIs serving 10k requests") == "experience"

    def test_skill_detection(self):
        from core.kb_migrator import _guess_category

        assert _guess_category("Proficient in Python and JavaScript") == "skill"

    def test_education_detection(self):
        from core.kb_migrator import _guess_category

        assert _guess_category("Bachelor of Science in Computer Science") == "education"

    def test_certification_detection(self):
        from core.kb_migrator import _guess_category

        assert _guess_category("AWS Certified Solutions Architect") == "certification"


# ---------------------------------------------------------------------------
# LaTeX Escaping Hardening
# ---------------------------------------------------------------------------


class TestLatexEscapingHardening:
    """Tests for backslash escaping in escape_latex()."""

    def test_backslash_escaped(self):
        from core.latex_compiler import escape_latex

        result = escape_latex(r"C:\Users\name\path")
        assert r"\textbackslash{}" in result
        assert "\\" not in result or r"\textbackslash{}" in result

    def test_backslash_before_special_chars(self):
        from core.latex_compiler import escape_latex

        result = escape_latex("cost is 100% & tax $5")
        assert r"\%" in result
        assert r"\&" in result
        assert r"\$" in result

    def test_empty_string(self):
        from core.latex_compiler import escape_latex

        assert escape_latex("") == ""

    def test_no_special_chars(self):
        from core.latex_compiler import escape_latex

        assert escape_latex("Hello World") == "Hello World"

    def test_all_special_chars(self):
        from core.latex_compiler import escape_latex

        result = escape_latex("& % $ # _ { } ~ ^")
        assert r"\&" in result
        assert r"\%" in result
        assert r"\$" in result
        assert r"\#" in result
        assert r"\_" in result
        assert r"\{" in result
        assert r"\}" in result
        assert r"\textasciitilde{}" in result
        assert r"\textasciicircum{}" in result

    def test_backslash_does_not_double_escape(self):
        from core.latex_compiler import escape_latex

        # A single backslash should produce exactly one \textbackslash{}
        result = escape_latex("\\")
        assert result == r"\textbackslash{}"

    def test_mixed_backslash_and_special(self):
        from core.latex_compiler import escape_latex

        result = escape_latex("10\\% off")
        # Should be: 10\textbackslash{}\% off
        assert r"\textbackslash{}" in result
        assert r"\%" in result
