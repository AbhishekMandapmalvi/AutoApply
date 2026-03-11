"""Tests for core/resume_parser.py — TASK-030 M1.

Tests markdown resume parsing into structured KB entries.
"""

from core.resume_parser import parse_resume_md


class TestParseResumeMd:
    """Tests for parse_resume_md() function."""

    def test_empty_input(self):
        """Empty string returns empty list."""
        assert parse_resume_md("") == []
        assert parse_resume_md("   ") == []

    def test_summary_extraction(self):
        """Summary section is extracted as a single entry."""
        md = "## Summary\nExperienced engineer with 10 years in backend systems."
        entries = parse_resume_md(md)
        assert len(entries) == 1
        assert entries[0]["category"] == "summary"
        assert "10 years" in entries[0]["text"]

    def test_experience_bullets(self):
        """Experience bullets are extracted with subsections."""
        md = (
            "## Experience\n"
            "### Senior Engineer — Acme Corp (2020-2023)\n"
            "- Led migration to microservices, reducing latency by 40%\n"
            "- Managed team of 5 engineers\n"
            "### Junior Dev — StartupCo (2018-2020)\n"
            "- Built REST APIs\n"
        )
        entries = parse_resume_md(md)
        assert len(entries) == 3

        # Check subsections
        acme_entries = [e for e in entries if e.get("subsection") and "Acme" in e["subsection"]]
        assert len(acme_entries) == 2
        startup_entries = [e for e in entries if e.get("subsection") and "Startup" in e["subsection"]]
        assert len(startup_entries) == 1

    def test_skills_extraction(self):
        """Skills section is extracted as a single entry."""
        md = "## Skills\nPython, Go, Docker, Kubernetes, AWS"
        entries = parse_resume_md(md)
        assert len(entries) == 1
        assert entries[0]["category"] == "skill"
        assert "Python" in entries[0]["text"]

    def test_education_extraction(self):
        """Education entries are extracted."""
        md = "## Education\nBS Computer Science — MIT (2016)\nMS Data Science — Stanford (2018)"
        entries = parse_resume_md(md)
        assert len(entries) == 2
        assert all(e["category"] == "education" for e in entries)

    def test_full_resume(self):
        """A complete resume yields entries from all sections."""
        md = (
            "# Jane Smith\n"
            "jane@example.com | 555-1234 | San Francisco, CA\n\n"
            "## Summary\n"
            "Experienced backend engineer.\n\n"
            "## Experience\n"
            "### Senior Dev — Acme (2020-2023)\n"
            "- Built microservices\n"
            "- Led team of 5\n\n"
            "## Skills\n"
            "Python, Go, Docker\n\n"
            "## Education\n"
            "BS CompSci — MIT (2016)\n"
        )
        entries = parse_resume_md(md)
        categories = {e["category"] for e in entries}
        assert "summary" in categories
        assert "experience" in categories
        assert "skill" in categories
        assert "education" in categories
        assert len(entries) >= 5

    def test_certifications_section(self):
        """Certifications section is extracted."""
        md = "## Certifications\n- AWS Solutions Architect\n- Google Cloud Professional"
        entries = parse_resume_md(md)
        assert len(entries) == 2
        assert all(e["category"] == "certification" for e in entries)

    def test_projects_section(self):
        """Projects section is extracted."""
        md = (
            "## Projects\n"
            "### Open Source — FastAPI\n"
            "- Implemented OAuth2 scopes middleware\n"
        )
        entries = parse_resume_md(md)
        assert len(entries) == 1
        assert entries[0]["category"] == "project"

    def test_unknown_section_ignored(self):
        """Unknown section headings are ignored."""
        md = "## Hobbies\n- Playing guitar\n- Hiking"
        entries = parse_resume_md(md)
        assert len(entries) == 0

    def test_all_entries_have_required_fields(self):
        """Every entry has category, text, subsection, job_types."""
        md = "## Experience\n### Dev — Acme\n- Built APIs\n## Skills\nPython"
        entries = parse_resume_md(md)
        for entry in entries:
            assert "category" in entry
            assert "text" in entry
            assert "subsection" in entry
            assert "job_types" in entry

    def test_alternative_headings(self):
        """Alternative section headings map correctly."""
        md = "## Professional Experience\n- Built something\n## Technical Skills\nPython"
        entries = parse_resume_md(md)
        categories = {e["category"] for e in entries}
        assert "experience" in categories
        assert "skill" in categories
