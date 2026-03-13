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
    # User-installed TinyTeX (~/.TinyTeX)
    str(Path.home() / ".TinyTeX" / "bin" / "x86_64-linux" / "pdflatex"),
    str(Path.home() / ".TinyTeX" / "bin" / "universal-darwin" / "pdflatex"),
    str(Path.home() / ".TinyTeX" / "bin" / "windows" / "pdflatex.exe"),
    # TinyTeX via APPDATA (Windows standard install)
    str(Path(os.environ.get("APPDATA", "")) / "TinyTeX" / "bin" / "windows" / "pdflatex.exe"),
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
            - name, email, phone, location, linkedin_url: str
            - summary: str (optional)
            - experience: [{company, location, roles: [{title, dates, bullets: [str]}]}]
            - education: [{institution, location, degree, dates}]
            - skills: [{category, entries}]
            - projects: [{name, bullets: [str]}]
            - certifications: [{text}]

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
    safe_context = _escape_context_dict(context)

    return template.render(**safe_context)


def _escape_context_dict(context: dict) -> dict:
    """Escape all string values in a top-level template context dict."""
    return {k: _escape_value(v) for k, v in context.items()}


def _escape_value(value: object) -> object:
    """Recursively escape all string values in nested structures."""
    if isinstance(value, dict):
        return {k: _escape_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_escape_value(item) for item in value]
    if isinstance(value, str):
        return escape_latex(value)
    return value


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
            pdf_bytes = _run_pdflatex(pdflatex_path, tmpdir, pdf_path, timeout)

            # Auto-install missing packages and retry (up to 3 rounds)
            for attempt in range(3):
                if pdf_bytes is not None:
                    break
                log_path = Path(tmpdir) / "resume.log"
                log_text = log_path.read_text(errors="replace") if log_path.exists() else ""
                missing = _find_missing_packages(log_text)
                if not missing:
                    break
                if not _auto_install_packages(missing, pdflatex_path):
                    break
                logger.info(
                    "Retry %d after installing: %s", attempt + 1, ", ".join(missing),
                )
                pdf_bytes = _run_pdflatex(pdflatex_path, tmpdir, pdf_path, timeout)

            if pdf_bytes is not None:
                logger.info("LaTeX compilation successful: %d bytes", len(pdf_bytes))
                if use_cache:
                    from core.pdf_cache import store

                    store(tex_content, pdf_bytes)
            return pdf_bytes

        except subprocess.TimeoutExpired:
            logger.error("pdflatex compilation timed out after %ds", timeout)
            return None
        except FileNotFoundError:
            logger.error("pdflatex binary not found at: %s", pdflatex_path)
            return None


def _run_pdflatex(
    pdflatex_path: str, tmpdir: str, pdf_path: Path, timeout: int,
) -> bytes | None:
    """Run pdflatex twice and return PDF bytes or None."""
    for run in range(2):
        result = subprocess.run(
            [pdflatex_path, "-interaction=nonstopmode", "-halt-on-error", "resume.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0 and run == 1:
            logger.error(
                "pdflatex compilation failed (run %d):\n%s",
                run + 1,
                result.stdout[-2000:] if result.stdout else "no output",
            )
            return None

    if pdf_path.exists():
        return pdf_path.read_bytes()

    logger.error("pdflatex did not produce PDF output")
    return None


def _find_missing_packages(log_text: str) -> list[str]:
    """Parse pdflatex log to find missing .sty/.def/.cls files."""
    # Patterns: "File `foo.sty' not found", "Encoding file `ly1enc.def' not found"
    pattern = re.compile(r"File `([^']+\.(?:sty|def|cls))' not found")
    matches = pattern.findall(log_text)
    # Also catch babel language errors
    babel_re = re.compile(r"Unknown option '(\w+)'.*babel", re.DOTALL)
    babel_matches = babel_re.findall(log_text)
    # Strip extension — tlmgr uses package names
    pkgs: list[str] = []
    for m in matches:
        name = re.sub(r"\.(sty|def|cls)$", "", m)
        # Common renames: ly1enc → ly1, etc.
        name = re.sub(r"enc$", "", name) or name
        pkgs.append(name)
    for lang in babel_matches:
        pkgs.append(f"babel-{lang}")
        pkgs.append(f"hyphen-{lang}")
    return list(dict.fromkeys(pkgs))


def _auto_install_packages(packages: list[str], pdflatex_path: str) -> bool:
    """Auto-install missing LaTeX packages via tlmgr (TinyTeX)."""
    # Find tlmgr relative to pdflatex
    pdflatex_dir = Path(pdflatex_path).parent
    tlmgr = pdflatex_dir / "tlmgr.bat"
    if not tlmgr.exists():
        tlmgr = pdflatex_dir / "tlmgr"
    if not tlmgr.exists():
        logger.warning("tlmgr not found — cannot auto-install packages")
        return False

    logger.info("Auto-installing LaTeX packages: %s", ", ".join(packages))
    try:
        result = subprocess.run(
            [str(tlmgr), "install"] + packages,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # tlmgr returns non-zero if some packages weren't found, but may
        # have installed others successfully — still consider it a success
        installed_any = "install:" in (result.stdout or "")
        if result.returncode == 0 or installed_any:
            logger.info("Installed packages (exit %d): %s", result.returncode, ", ".join(packages))
            # Rebuild formats if hyphen/babel packages were installed
            if any(p.startswith(("hyphen-", "babel-")) for p in packages):
                _rebuild_formats(pdflatex_dir)
            return True
        logger.error("tlmgr install failed: %s", result.stderr[-500:])
        return False
    except Exception as e:
        logger.error("tlmgr install error: %s", e)
        return False


def _rebuild_formats(pdflatex_dir: Path) -> None:
    """Rebuild LaTeX formats after installing hyphenation packages."""
    fmtutil = pdflatex_dir / "fmtutil-sys.exe"
    if not fmtutil.exists():
        fmtutil = pdflatex_dir / "fmtutil-sys"
    if not fmtutil.exists():
        return
    try:
        env = os.environ.copy()
        env["PATH"] = str(pdflatex_dir) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            [str(fmtutil), "--all"],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        logger.info("LaTeX formats rebuilt successfully")
    except Exception as e:
        logger.warning("Format rebuild failed: %s", e)


def render_custom_template(
    tex_source: str,
    context: dict,
) -> str:
    """Render a user-provided LaTeX template string with the given context.

    Uses the same Jinja2 delimiters and escaping as built-in templates.

    Args:
        tex_source: Raw .tex content with Jinja2 delimiters.
        context: Same context dict as render_template().

    Returns:
        Rendered .tex content as string.
    """
    env = jinja2.Environment(
        loader=jinja2.BaseLoader(),
        block_start_string=r"\BLOCK{",
        block_end_string="}",
        variable_start_string=r"\VAR{",
        variable_end_string="}",
        comment_start_string=r"\#{",
        comment_end_string="}",
        autoescape=False,
    )
    env.filters["escape_latex"] = escape_latex
    template = env.from_string(tex_source)
    safe_context = _escape_context_dict(context)
    return template.render(**safe_context)


def compile_resume(
    template_name: str,
    context: dict,
    pdflatex_path: str | None = None,
    custom_tex: str | None = None,
) -> bytes | None:
    """Render template and compile to PDF in one step.

    Args:
        template_name: Template name (e.g., "classic") or custom template name.
        context: Template context dict.
        pdflatex_path: Optional pdflatex path override.
        custom_tex: If provided, use this raw .tex source instead of built-in.

    Returns:
        PDF bytes, or None if rendering or compilation fails.
    """
    try:
        if custom_tex:
            tex_content = render_custom_template(custom_tex, context)
        else:
            tex_content = render_template(template_name, context)
    except (ValueError, jinja2.TemplateNotFound) as e:
        logger.error("Template rendering failed: %s", e)
        return None

    return compile_latex(tex_content, pdflatex_path=pdflatex_path)
