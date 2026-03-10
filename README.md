# AutoApply

**Automated job application platform that searches, scores, and applies to jobs on your behalf.**

AutoApply searches LinkedIn and Indeed, scores each job against your preferences, generates tailored resumes and cover letters using AI, and submits applications — all running locally on your machine. Your data never leaves your computer.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-205%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **Multi-platform search** — LinkedIn and Indeed, with configurable job titles, locations, and keywords
- **Smart scoring** — Each job scored 0–100 based on title match, salary, location, experience level, and keyword relevance
- **AI-powered documents** — Generates tailored resumes (PDF) and cover letters per job using [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- **Automated applications** — Fills forms, uploads documents, and submits on LinkedIn Easy Apply, Indeed Quick Apply, Greenhouse, and Lever
- **Review mode** — Optionally review each application before it's submitted
- **Dashboard** — Real-time live feed, application history, analytics, CSV export
- **Desktop app** — Electron shell with system tray support (minimize to tray, runs in background)
- **Login session persistence** — Log in once, sessions are saved across restarts
- **Scheduling** — Set days and hours for the bot to run automatically
- **Fully local** — No cloud, no accounts, no telemetry. Everything at `~/.autoapply/`

## Quick Start

**Prerequisites**: Python 3.11+ and Google Chrome installed.

```bash
# 1. Clone and set up
git clone https://github.com/AbhishekMandapmalvi/AutoApply.git
cd AutoApply
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
python setup.py

# 2. Install Playwright browser (for job searching/applying)
playwright install chromium

# 3. Run
python run.py
```

The dashboard opens at `http://localhost:5000`. A setup wizard walks you through configuration on first launch.

### Desktop App (Electron)

For a native desktop experience with system tray support:

```bash
cd electron
npm install
npx electron .
```

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Search     │────▶│   Score &    │────▶│  Generate    │────▶│   Apply      │
│  LinkedIn    │     │   Filter     │     │  Resume + CL │     │  Auto-fill   │
│  Indeed      │     │  (0-100)     │     │  (Claude AI) │     │  & Submit    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │                     │
       ▼                    ▼                    ▼                     ▼
  Configurable        Min score gate       Tailored per job     LinkedIn Easy Apply
  titles, locations,  + keyword filters    with your experience Indeed Quick Apply
  salary, keywords                         files as context     Greenhouse, Lever
```

1. **Search** — Playwright-based scrapers find jobs on enabled platforms
2. **Score** — Each job rated against your preferences (title, location, salary, keywords)
3. **Filter** — Jobs below your minimum score or on the blacklist are skipped
4. **Generate** — Claude Code creates a tailored resume and cover letter using your experience files
5. **Apply** — Bot fills out application forms, uploads documents, and submits
6. **Track** — Every application saved to SQLite with status, score, and generated documents

## Configuration

All settings are managed through the dashboard UI. Key options:

| Setting | Description |
|---------|-------------|
| **Job Titles** | Roles to search for (e.g., "Software Engineer", "Program Manager") |
| **Locations** | Where to search (e.g., "Remote", "New York, NY") |
| **Min Match Score** | Only apply to jobs scoring above this threshold (default: 75) |
| **Apply Mode** | `full_auto` (hands-free), `review` (approve each), or `watch` (observe only) |
| **Max Applications/Day** | Daily cap to avoid rate limiting (default: 50) |
| **Schedule** | Days and hours for automatic operation |
| **Company Blacklist** | Companies to always skip |

## Project Structure

```
AutoApply/
├── app.py                  # Flask + SocketIO backend (API, WebSocket events)
├── run.py                  # Entry point (port detection, server launch)
├── config/settings.py      # Pydantic config models
├── db/database.py          # SQLite database layer
├── core/
│   ├── ai_engine.py        # Claude Code integration for document generation
│   ├── filter.py           # Job scoring and ATS detection
│   ├── resume_renderer.py  # PDF resume generation (ReportLab)
│   └── scheduler.py        # Time-based bot scheduling
├── bot/
│   ├── bot.py              # Main bot loop (search → filter → generate → apply)
│   ├── browser.py          # Playwright browser manager
│   ├── search/             # LinkedIn and Indeed scrapers
│   └── apply/              # Platform-specific appliers (LinkedIn, Indeed, Greenhouse, Lever)
├── templates/index.html    # Single-page dashboard (vanilla JS)
├── electron/               # Electron desktop shell
│   ├── main.js             # App window, tray, lifecycle
│   └── python-backend.js   # Python process management
├── tests/                  # 205 tests (pytest)
└── docs/                   # User and developer documentation
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup & Installation](docs/guides/setup.md) | Install, first launch, platform login |
| [How the Bot Works](docs/guides/how-the-bot-works.md) | Full pipeline — searching, scoring, applying |
| [Writing Experience Files](docs/guides/experience-files.md) | Describe your background for better AI-generated resumes |
| [How AI Generation Works](docs/guides/ai-generation.md) | What happens when AutoApply creates your documents |
| [Configuration](docs/guides/configuration.md) | All settings explained |
| [Troubleshooting](docs/guides/troubleshooting.md) | Common problems and fixes |
| [API Reference](docs/api/endpoints.md) | REST API for developers |
| [Changelog](CHANGELOG.md) | Version history |

## Your Data

Everything stays on your machine at `~/.autoapply/`:

```
~/.autoapply/
├── config.json              # Your settings
├── autoapply.db             # Application history (SQLite)
├── profile/
│   ├── experiences/         # Your background (.txt files fed to AI)
│   ├── resumes/             # Generated resumes (PDF)
│   └── cover_letters/       # Generated cover letters
├── browser_profile/         # Chrome login sessions (persisted)
└── backend.log              # Server logs
```

## Testing

```bash
python -m pytest tests/ -v
```

205 tests covering settings, database, API endpoints, bot logic, AI engine, scoring/filtering, resume rendering, scheduling, login flow, and applier modules.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask, Flask-SocketIO, gevent |
| Database | SQLite (stdlib `sqlite3`) |
| Browser automation | Playwright (persistent context, system Chrome) |
| AI | Claude Code CLI (subprocess) |
| PDF generation | ReportLab |
| Config | Pydantic v2 |
| Desktop | Electron |
| Frontend | Vanilla JS SPA (single `index.html`) |
| Tests | pytest |

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes and add tests
4. Run `python -m pytest tests/ -v` to verify
5. Submit a pull request

## License

MIT License. See [LICENSE](LICENSE) for details.
