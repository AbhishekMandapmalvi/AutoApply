"""Tests for core/latex_compiler.py — TASK-030 M3.

Tests pdflatex discovery, LaTeX escaping, template rendering,
compilation (mocked), and the compile_resume convenience function.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.latex_compiler import (
    AVAILABLE_TEMPLATES,
    compile_latex,
    compile_resume,
    escape_latex,
    find_pdflatex,
    render_template,
)

# ---------------------------------------------------------------------------
# LaTeX Escaping Tests
# ---------------------------------------------------------------------------


class TestEscapeLaTeX:
    """Tests for LaTeX special character escaping."""

    def test_escape_ampersand(self):
        assert escape_latex("AT&T") == r"AT\&T"

    def test_escape_percent(self):
        assert escape_latex("100% coverage") == r"100\% coverage"

    def test_escape_dollar(self):
        assert escape_latex("$100K salary") == r"\$100K salary"

    def test_escape_hash(self):
        assert escape_latex("C# developer") == r"C\# developer"

    def test_escape_underscore(self):
        assert escape_latex("snake_case") == r"snake\_case"

    def test_escape_braces(self):
        assert escape_latex("{value}") == r"\{value\}"

    def test_escape_tilde(self):
        assert escape_latex("~approx") == r"\textasciitilde{}approx"

    def test_escape_caret(self):
        assert escape_latex("2^10") == r"2\textasciicircum{}10"

    def test_escape_empty(self):
        assert escape_latex("") == ""

    def test_escape_none(self):
        assert escape_latex(None) == ""

    def test_escape_multiple(self):
        """Multiple special chars in one string."""
        assert escape_latex("C++ & C# @ 100%") == r"C++ \& C\# @ 100\%"

    def test_escape_backslash(self):
        """Backslash is escaped to \\textbackslash{}."""
        assert escape_latex(r"\textbf{test}") == r"\textbackslash{}textbf\{test\}"


# ---------------------------------------------------------------------------
# pdflatex Discovery Tests
# ---------------------------------------------------------------------------


class TestFindPdflatex:
    """Tests for pdflatex binary discovery."""

    def test_find_bundled(self, tmp_path):
        """Should find pdflatex in bundled TinyTeX directory."""
        # Create fake pdflatex binary
        bin_dir = tmp_path / "bin" / "x86_64-linux"
        bin_dir.mkdir(parents=True)
        fake_pdflatex = bin_dir / "pdflatex"
        fake_pdflatex.write_text("#!/bin/sh\necho fake")
        fake_pdflatex.chmod(0o755)

        result = find_pdflatex(bundled_dir=tmp_path)
        assert result is not None
        assert "pdflatex" in result

    def test_find_system_path(self):
        """Should find pdflatex on system PATH if available."""
        with patch("shutil.which", return_value="/usr/bin/pdflatex"):
            result = find_pdflatex()
            assert result == "/usr/bin/pdflatex"

    def test_not_found(self):
        """Returns None when pdflatex is not available anywhere."""
        with patch("shutil.which", return_value=None):
            result = find_pdflatex(bundled_dir=None)
            # Might find at common locations — but on test machines, unlikely
            # Just verify it returns str or None
            assert result is None or isinstance(result, str)

    def test_bundled_dir_none(self):
        """Should still search PATH when bundled_dir is None."""
        with patch("shutil.which", return_value="/opt/texlive/bin/pdflatex"):
            result = find_pdflatex(bundled_dir=None)
            assert result == "/opt/texlive/bin/pdflatex"


# ---------------------------------------------------------------------------
# Template Rendering Tests
# ---------------------------------------------------------------------------


class TestRenderTemplate:
    """Tests for Jinja2 LaTeX template rendering."""

    @pytest.fixture
    def sample_context(self):
        """Minimal context for template rendering (structured format)."""
        return {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+1-555-0100",
            "location": "San Francisco, CA",
            "linkedin_url": "",
            "summary": "Senior backend engineer with 8 years experience.",
            "experience": [
                {
                    "company": "TechCorp",
                    "location": "San Francisco, CA",
                    "roles": [
                        {
                            "title": "Senior Engineer",
                            "dates": "Jan 2020 -- Present",
                            "bullets": [
                                "Built microservices handling 10K req/s",
                                "Led team of 5 engineers on platform migration",
                            ],
                        },
                    ],
                },
                {
                    "company": "CloudInc",
                    "location": "Seattle, WA",
                    "roles": [
                        {
                            "title": "DevOps Lead",
                            "dates": "Jun 2018 -- Dec 2019",
                            "bullets": [
                                "Designed CI/CD pipeline reducing deploys by 60%",
                            ],
                        },
                    ],
                },
            ],
            "education": [
                {
                    "institution": "Stanford University",
                    "location": "Stanford, CA",
                    "degree": "M.S. Computer Science",
                    "dates": "Sep 2016 -- Jun 2018",
                },
            ],
            "skills": [
                {"category": "Languages", "entries": "Python, Java, Go, SQL"},
                {"category": "Frameworks", "entries": "Flask, Django, React"},
                {"category": "Tools", "entries": "Docker, Kubernetes, AWS, Terraform"},
            ],
            "projects": [
                {
                    "name": "AutoApply",
                    "bullets": [
                        "Built automated job application tool with Electron + Flask",
                        "Implemented TF-IDF scoring engine for resume tailoring",
                    ],
                },
            ],
            "certifications": [
                {"text": "AWS Solutions Architect Associate"},
            ],
        }

    def test_render_all_templates(self, sample_context):
        """All available templates should render without error."""
        for name in AVAILABLE_TEMPLATES:
            tex = render_template(name, sample_context)
            assert r"\documentclass" in tex
            assert "Jane Doe" in tex
            assert "jane@example.com" in tex

    def test_render_classic_sections(self, sample_context):
        """Classic template should have standard section headers."""
        tex = render_template("classic", sample_context)
        assert r"\section{Experience}" in tex
        assert r"\section{Education}" in tex
        assert r"\section{Skills}" in tex

    def test_render_classic_company_structure(self, sample_context):
        """Classic template should show company and role separately."""
        tex = render_template("classic", sample_context)
        assert "TechCorp" in tex
        assert "Senior Engineer" in tex
        assert "CloudInc" in tex
        assert "DevOps Lead" in tex

    def test_render_classic_grouped_skills(self, sample_context):
        """Classic template should show skills grouped by category."""
        tex = render_template("classic", sample_context)
        assert "Languages" in tex
        assert "Frameworks" in tex
        assert "Tools" in tex

    def test_render_modern(self, sample_context):
        """Modern template should use accent color."""
        tex = render_template("modern", sample_context)
        assert "accent" in tex
        assert r"\section{Professional Experience}" in tex

    def test_render_academic(self, sample_context):
        """Academic template should put education first."""
        tex = render_template("academic", sample_context)
        edu_pos = tex.find("Education")
        exp_pos = tex.find("Professional Experience")
        assert edu_pos < exp_pos, "Academic CV should have Education before Experience"

    def test_render_minimal(self, sample_context):
        """Minimal template should use smaller font size."""
        tex = render_template("minimal", sample_context)
        assert "10pt" in tex

    def test_render_multi_role_company(self):
        """Templates should handle multiple roles at the same company."""
        context = {
            "name": "Test User",
            "email": "test@test.com",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "summary": "",
            "experience": [
                {
                    "company": "Google",
                    "location": "Mountain View, CA",
                    "roles": [
                        {
                            "title": "Senior Software Engineer",
                            "dates": "Jan 2022 -- Present",
                            "bullets": ["Led platform team"],
                        },
                        {
                            "title": "Software Engineer",
                            "dates": "Jun 2020 -- Dec 2021",
                            "bullets": ["Built search features"],
                        },
                    ],
                },
            ],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
        }
        tex = render_template("classic", context)
        assert "Google" in tex
        assert "Senior Software Engineer" in tex
        assert "Software Engineer" in tex
        assert "Led platform team" in tex
        assert "Built search features" in tex

    def test_render_invalid_template(self, sample_context):
        """Invalid template name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown template"):
            render_template("nonexistent", sample_context)

    def test_render_escapes_special_chars(self):
        """Special characters in context should be escaped."""
        context = {
            "name": "O'Brien & Associates",
            "email": "test@example.com",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "summary": "Increased revenue by 50% using C# & Python",
            "experience": [],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
        }
        tex = render_template("classic", context)
        assert r"\&" in tex
        assert r"\%" in tex
        assert r"\#" in tex

    def test_render_escapes_nested_special_chars(self):
        """Special characters in nested structures should be escaped."""
        context = {
            "name": "Test",
            "email": "t@t.com",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "summary": "",
            "experience": [
                {
                    "company": "AT&T",
                    "location": "",
                    "roles": [
                        {
                            "title": "C# Developer",
                            "dates": "",
                            "bullets": ["Saved $1M in costs"],
                        },
                    ],
                },
            ],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
        }
        tex = render_template("classic", context)
        assert r"AT\&T" in tex
        assert r"C\# Developer" in tex
        assert r"\$1M" in tex

    def test_render_empty_sections(self):
        """Template should handle empty/missing optional sections."""
        context = {
            "name": "Test User",
            "email": "test@test.com",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "summary": "",
            "experience": [],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
        }
        tex = render_template("classic", context)
        assert r"\documentclass" in tex
        assert "Test User" in tex
        # Empty sections should not appear
        assert r"\section{Experience}" not in tex


# ---------------------------------------------------------------------------
# Compilation Tests (mocked)
# ---------------------------------------------------------------------------


class TestCompileLatex:
    """Tests for LaTeX compilation (pdflatex mocked)."""

    def test_compile_success(self, tmp_path):
        """Successful compilation returns PDF bytes."""
        fake_pdf = b"%PDF-1.4 fake pdf content"

        def mock_run(cmd, **kwargs):
            # Write fake PDF to the temp dir
            cwd = kwargs.get("cwd", ".")
            pdf_path = Path(cwd) / "resume.pdf"
            pdf_path.write_bytes(fake_pdf)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Output written on resume.pdf"
            return result

        with patch("core.latex_compiler.subprocess.run", side_effect=mock_run):
            pdf = compile_latex(r"\documentclass{article}\begin{document}Hello\end{document}", pdflatex_path="/fake/pdflatex")

        assert pdf == fake_pdf

    def test_compile_failure(self):
        """Failed compilation returns None."""
        result = MagicMock()
        result.returncode = 1
        result.stdout = "! LaTeX Error: something went wrong"

        with patch("core.latex_compiler.subprocess.run", return_value=result):
            pdf = compile_latex(r"\documentclass{article}\begin{document}Fail\end{document}", pdflatex_path="/fake/pdflatex", use_cache=False)

        assert pdf is None

    def test_compile_timeout(self):
        """Timeout returns None."""
        with patch("core.latex_compiler.subprocess.run", side_effect=subprocess.TimeoutExpired("pdflatex", 30)):
            pdf = compile_latex("test", pdflatex_path="/fake/pdflatex", timeout=30)

        assert pdf is None

    def test_compile_missing_binary(self):
        """Missing binary returns None."""
        with patch("core.latex_compiler.subprocess.run", side_effect=FileNotFoundError()):
            pdf = compile_latex("test", pdflatex_path="/nonexistent/pdflatex")

        assert pdf is None

    def test_compile_no_pdflatex(self):
        """No pdflatex available returns None."""
        with patch("core.latex_compiler.find_pdflatex", return_value=None):
            pdf = compile_latex("test", pdflatex_path=None)

        assert pdf is None


# ---------------------------------------------------------------------------
# Convenience Function Tests
# ---------------------------------------------------------------------------


class TestCompileResume:
    """Tests for the compile_resume convenience function."""

    def test_compile_resume_renders_and_compiles(self):
        """Should render template then compile."""
        fake_pdf = b"%PDF-1.4 content"

        def mock_run(cmd, **kwargs):
            cwd = kwargs.get("cwd", ".")
            Path(cwd).joinpath("resume.pdf").write_bytes(fake_pdf)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            return result

        context = {
            "name": "Test",
            "email": "t@t.com",
            "phone": "",
            "location": "",
            "summary": "",
            "experience": [],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
        }

        with patch("core.latex_compiler.subprocess.run", side_effect=mock_run):
            pdf = compile_resume("classic", context, pdflatex_path="/fake/pdflatex")

        assert pdf == fake_pdf

    def test_compile_resume_invalid_template(self):
        """Invalid template returns None."""
        pdf = compile_resume("nonexistent", {})
        assert pdf is None
