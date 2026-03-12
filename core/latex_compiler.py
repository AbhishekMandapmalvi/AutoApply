"""LaTeX Compiler — find pdflatex, render Jinja2 templates, compile to PDF.

Implements: TASK-030 M3 — Renders resume data into LaTeX via Jinja2 templates
and compiles to PDF using pdflatex (bundled TinyTeX or system install).
Falls back to ReportLab when pdflatex is unavailable.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import jinja2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LaTeX special character escaping
# ---------------------------------------------------------------------------

_LATEX_ESCAPE_MAP: dict[str, str] = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_LATEX_ESCAPE_RE = re.compile(
    "|".join(re.escape(k) for k in _LATEX_ESCAPE_MAP),
)


def escape_latex(text: str) -> str:
    r"""Escape LaTeX special characters in text.

    Handles: \ & % $ # _ { } ~ ^
    Backslash is escaped FIRST using a placeholder, other chars are escaped,
    then the placeholder is replaced with \textbackslash{}.
    """
    if not text:
        return ""
    # Replace backslash with placeholder before escaping braces
    text = text.replace("\\", "\x00BACKSLASH\x00")
    text = _LATEX_ESCAPE_RE.sub(lambda m: _LATEX_ESCAPE_MAP[m.group()], text)
    return text.replace("\x00BACKSLASH\x00", r"\textbackslash{}")


# ---------------------------------------------------------------------------
# pdflatex discovery
# ---------------------------------------------------------------------------

# Common pdflatex install locations by platform
_COMMON_PATHS: list[str] = [
    # TinyTeX (bundled inside Electron app)
    "resources/tinytex/bin/x86_64-linux/pdflatex",
    "resources/tinytex/bin/universal-darwin/pdflatex",
    "resources/tinytex/bin/windows/pdflatex.exe",
    # User-installed TinyTeX
    str(Path.home() / ".TinyTeX" / "bin" / "x86_64-linux" / "pdflatex"),
    str(Path.home() / ".TinyTeX" / "bin" / "universal-darwin" / "pdflatex"),
    str(Path.home() / ".TinyTeX" / "bin" / "windows" / "pdflatex.exe"),
    # TeX Live
    "/usr/local/texlive/2024/bin/x86_64-linux/pdflatex",
    "/usr/local/texlive/2024/bin/universal-darwin/pdflatex",
    # MiKTeX (Windows)
    r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
    r"C:\Program Files (x86)\MiKTeX\miktex\bin\x64\pdflatex.exe",
]


def find_pdflatex(bundled_dir: Path | None = None) -> str | None:
    """Find pdflatex binary.

    Search order:
    1. Bundled TinyTeX directory (if provided)
    2. System PATH (via shutil.which)
    3. Common install locations

    Returns:
        Full path to pdflatex, or None if not found.
    """
    # 1. Bundled TinyTeX
    if bundled_dir and bundled_dir.is_dir():
        for candidate in bundled_dir.rglob("pdflatex*"):
            if candidate.is_file() and os.access(str(candidate), os.X_OK):
                logger.info("Found bundled pdflatex: %s", candidate)
                return str(candidate)

    # 2. System PATH
    system_path = shutil.which("pdflatex")
    if system_path:
        logger.info("Found system pdflatex: %s", system_path)
        return system_path

    # 3. Common install locations
    for path in _COMMON_PATHS:
        if Path(path).is_file():
            logger.info("Found pdflatex at common location: %s", path)
            return path

    logger.warning("pdflatex not found — LaTeX compilation unavailable")
    return None


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

# Template directory: templates/latex/ relative to project root
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "latex"

AVAILABLE_TEMPLATES = ("classic", "modern", "academic", "minimal")


def _get_jinja_env() -> jinja2.Environment:
    """Create Jinja2 environment for LaTeX templates."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        autoescape=False,  # LaTeX, not HTML
    )


def render_template(
    template_name: str,
    context: dict,
) -> str:
    """Render a LaTeX template with the given context.

    Args:
        template_name: Template name (e.g., "classic"). Looks for
            templates/latex/{name}.tex.j2
        context: Dict with keys expected by the template:
            - name: str
            - email: str
            - phone: str
            - location: str (optional)
            - summary: str (optional)
            - experience: list[dict] with text, subsection
            - education: list[dict] with text, subsection
            - skills: list[dict] with text
            - projects: list[dict] with text, subsection (optional)
            - certifications: list[dict] with text (optional)

    Returns:
        Rendered .tex content as string.

    Raises:
        ValueError: If template_name is not in AVAILABLE_TEMPLATES.
        jinja2.TemplateNotFound: If template file doesn't exist.
    """
    if template_name not in AVAILABLE_TEMPLATES:
        raise ValueError(
            f"Unknown template '{template_name}'. "
            f"Available: {', '.join(AVAILABLE_TEMPLATES)}"
        )

    env = _get_jinja_env()
    env.filters["escape_latex"] = escape_latex
    template = env.get_template(f"{template_name}.tex.j2")

    # Escape all text values in context
    safe_context = _escape_context(context)

    return template.render(**safe_context)


def _escape_context(context: dict) -> dict:
    """Deep-escape all string values in the template context."""
    result: dict = {}
    for key, value in context.items():
        if isinstance(value, str):
            result[key] = escape_latex(value)
        elif isinstance(value, list):
            result[key] = [_escape_entry(item) for item in value]
        else:
            result[key] = value
    return result


def _escape_entry(entry: dict | str | object) -> dict | str:
    """Escape string values in a list entry."""
    if isinstance(entry, dict):
        return {k: escape_latex(v) if isinstance(v, str) else v for k, v in entry.items()}
    if isinstance(entry, str):
        return escape_latex(entry)
    return str(entry)


# ---------------------------------------------------------------------------
# PDF compilation
# ---------------------------------------------------------------------------


def compile_latex(
    tex_content: str,
    pdflatex_path: str | None = None,
    timeout: int = 30,
    use_cache: bool = True,
) -> bytes | None:
    """Compile LaTeX content to PDF.

    Args:
        tex_content: Full .tex document content.
        pdflatex_path: Path to pdflatex binary. If None, auto-discovers.
        timeout: Compilation timeout in seconds.
        use_cache: If True, check/store in PDF cache (TASK-030 M8).

    Returns:
        PDF file content as bytes, or None if compilation fails.
    """
    # Check cache first (M8)
    if use_cache:
        from core.pdf_cache import get_cached

        cached = get_cached(tex_content)
        if cached is not None:
            return cached

    if pdflatex_path is None:
        pdflatex_path = find_pdflatex()

    if pdflatex_path is None:
        logger.warning("Cannot compile LaTeX: pdflatex not found")
        return None

    with tempfile.TemporaryDirectory(prefix="autoapply_latex_") as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        pdf_path = Path(tmpdir) / "resume.pdf"

        tex_path.write_text(tex_content, encoding="utf-8")

        try:
            # Run pdflatex twice (for references/TOC resolution)
            for run in range(2):
                result = subprocess.run(
                    [pdflatex_path, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode != 0 and run == 1:
                    # Only log error on second run (first run may have unresolved refs)
                    logger.error(
                        "pdflatex compilation failed (run %d):\n%s",
                        run + 1,
                        result.stdout[-2000:] if result.stdout else "no output",
                    )
                    return None

            if pdf_path.exists():
                pdf_bytes = pdf_path.read_bytes()
                logger.info("LaTeX compilation successful: %d bytes", len(pdf_bytes))
                # Store in cache (M8)
                if use_cache:
                    from core.pdf_cache import store

                    store(tex_content, pdf_bytes)
                return pdf_bytes

            logger.error("pdflatex did not produce PDF output")
            return None

        except subprocess.TimeoutExpired:
            logger.error("pdflatex compilation timed out after %ds", timeout)
            return None
        except FileNotFoundError:
            logger.error("pdflatex binary not found at: %s", pdflatex_path)
            return None


def compile_resume(
    template_name: str,
    context: dict,
    pdflatex_path: str | None = None,
) -> bytes | None:
    """Render template and compile to PDF in one step.

    Args:
        template_name: Template name (e.g., "classic").
        context: Template context dict.
        pdflatex_path: Optional pdflatex path override.

    Returns:
        PDF bytes, or None if rendering or compilation fails.
    """
    try:
        tex_content = render_template(template_name, context)
    except (ValueError, jinja2.TemplateNotFound) as e:
        logger.error("Template rendering failed: %s", e)
        return None

    return compile_latex(tex_content, pdflatex_path=pdflatex_path)
