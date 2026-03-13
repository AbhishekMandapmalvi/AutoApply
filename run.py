from __future__ import annotations

import argparse
import json as _json
import logging
import os
import signal
import socket
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for machine-readable log output.

    Produces one JSON object per line with fields:
    timestamp, level, logger, message, and any extra fields from the LogRecord.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack_info"] = record.stack_info
        return _json.dumps(entry, default=str)


def _configure_logging(data_dir: Path) -> None:
    """Set up application-wide logging with console + rotating file output.

    Set AUTOAPPLY_LOG_FORMAT=json for structured JSON output (D-7).
    Set AUTOAPPLY_DEBUG=1 for DEBUG level.
    """
    level = logging.DEBUG if os.environ.get("AUTOAPPLY_DEBUG") else logging.INFO
    use_json = os.environ.get("AUTOAPPLY_LOG_FORMAT", "").lower() == "json"

    if use_json:
        formatter: logging.Formatter = JsonFormatter()
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path = data_dir / "backend.log"
    file_handler = RotatingFileHandler(
        str(log_path), maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def _find_free_port(start: int = 5000, end: int = 5010) -> int:
    """Try binding to ports in range [start, end]. Return first available."""
    for port in range(start, end + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"All ports {start}-{end} are in use. "
        f"Set AUTOAPPLY_PORT to a free port or close other applications."
    )


def _setup_data_dirs() -> Path:
    """Create data directories and return the data dir path."""
    from config.settings import get_data_dir

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    (data_dir / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
    (data_dir / "profile" / "jobs").mkdir(parents=True, exist_ok=True)
    (data_dir / "profile" / "resumes").mkdir(parents=True, exist_ok=True)
    (data_dir / "profile" / "cover_letters").mkdir(parents=True, exist_ok=True)
    (data_dir / "profile" / "job_descriptions").mkdir(parents=True, exist_ok=True)
    (data_dir / "browser_profile").mkdir(parents=True, exist_ok=True)
    (data_dir / "backups").mkdir(parents=True, exist_ok=True)

    readme_path = data_dir / "profile" / "experiences" / "README.txt"
    if not readme_path.exists():
        readme_path.write_text(
            "HOW TO USE THIS FOLDER\n"
            "=====================\n\n"
            "Add .txt files describing your work experience, skills, and achievements.\n"
            "Write in plain language — the AI will read these to generate tailored\n"
            "resumes and cover letters for each job application.\n\n"
            "Tips:\n"
            "- One file per job/role works well, but any organization is fine\n"
            "- Include specific achievements with numbers where possible\n"
            "- Mention technologies, tools, and methodologies you've used\n"
            "- Describe projects you've led or contributed to\n"
            "- Include education, certifications, and relevant training\n\n"
            "Example files:\n"
            "  senior_engineer_acme.txt\n"
            "  skills_and_tools.txt\n"
            "  education.txt\n"
            "  projects_and_achievements.txt\n",
            encoding="utf-8",
        )

    return data_dir


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="AutoApply — Smart Job Application Bot")
    parser.add_argument(
        "--gui", action="store_true",
        help="Launch with PyWebView desktop GUI",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Start server without opening a browser (headless mode)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    env_port = os.environ.get("AUTOAPPLY_PORT")
    if env_port:
        port = int(env_port)
    else:
        port = _find_free_port()

    data_dir = _setup_data_dirs()
    _configure_logging(data_dir)

    # Default to GUI mode when running as frozen PyInstaller bundle
    is_frozen = getattr(sys, "frozen", False)

    if args.gui or is_frozen:
        # PyWebView desktop mode — Flask starts in a daemon thread
        from shell import launch_gui

        launch_gui(host="127.0.0.1", port=port)
    else:
        # Headless server mode
        from app import app, graceful_shutdown, socketio

        # Register signal handlers for graceful shutdown (NFR-ME8)
        def _signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logging.getLogger(__name__).info("Received %s, shutting down...", sig_name)
            graceful_shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _signal_handler)

        print(f"AutoApply starting at http://localhost:{port}")
        socketio.run(app, host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
