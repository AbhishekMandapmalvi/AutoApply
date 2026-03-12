# AutoApply

**Automated job application platform that searches, scores, and applies to jobs on your behalf.**

AutoApply searches LinkedIn and Indeed, scores each job against your preferences, generates tailored resumes and cover letters using AI, and submits applications — all running locally on your machine. Your data never leaves your computer.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1385%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- **Multi-platform search** — LinkedIn and Indeed, with configurable job titles, locations, and keywords
- **Smart scoring** — Each job scored 0–100 based on title match, salary, location, experience level, and keyword relevance
- **AI-powered documents** — Generates tailored resumes (PDF) and cover letters per job using your choice of AI provider (Anthropic, OpenAI, Google, or DeepSeek)
- **Knowledge Base** — Upload career documents (PDF, DOCX, TXT, MD) once, reuse categorized entries across applications. TF-IDF scoring ranks entries by job relevance
- **Automated applications** — Fills forms, uploads documents, and submits on LinkedIn Easy Apply, Indeed Quick Apply, Greenhouse, Lever, Workday, and Ashby
- **Review mode** — Optionally review each application before it's submitted
- **Dashboard** — Real-time live feed, application history, analytics, resume library, CSV export
- **Desktop app** — Electron shell with system tray support (minimize to tray, runs in background)
- **Login session persistence** — Log in once, sessions are saved across restarts
- **Scheduling** — Set days and hours for the bot to run automatically
- **Accessible** — WCAG 2.1 AA compliant: keyboard navigation, screen reader support, focus management, reduced motion
- **Internationalization** — Full i18n with JSON locale files, `data-i18n` HTML attributes, and backend `t()` function. Add new languages by copying `static/locales/en.json`
- **Fully local** — No cloud, no accounts, no telemetry. Everything at `~/.autoapply/`

## Quick Start

**Prerequisites**: Python 3.11+, Node.js 18+, and Google Chrome installed.

```bash
# 1. Clone and set up
git clone https://github.com/AbhishekMandapmalvi/AutoApply.git
cd AutoApply
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
python setup_env.py

# 2. Install Playwright browser (for job searching/applying)
playwright install chromium

# 3. Launch the desktop app
cd electron
npm install
npm start
```

A native app window opens with the dashboard. A setup wizard walks you through configuration on first launch.

## Building Installers

To create standalone installers (no Python/Node.js required on the target machine):

```bash
cd electron
npm install
npm run dist:win          # Windows NSIS installer (.exe)
npm run dist:mac          # macOS disk image (.dmg)
npm run dist:linux        # Linux portable (.AppImage)
```

The build process automatically syncs the version from `pyproject.toml`, generates app icons, downloads an embedded Python runtime, and bundles all dependencies. Output goes to `electron/build/`.

For CI-based releases, push a `v*` tag (e.g., `v1.9.0`) to trigger the GitHub Actions workflow that builds all three platforms and creates a GitHub Release.

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
                                                                Workday, Ashby
```

1. **Search** — Playwright-based scrapers find jobs on enabled platforms
2. **Score** — Each job rated against your preferences (title, location, salary, keywords)
3. **Filter** — Jobs below your minimum score or on the blacklist are skipped
4. **Generate** — AI creates a tailored resume and cover letter using your experience files
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
| **Application Answers** | Pre-fill screening questions (work auth, visa, experience, salary, EEO) |
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
│   ├── ai_engine.py        # Multi-provider LLM API for document generation
│   ├── filter.py           # Job scoring and ATS detection
│   ├── resume_renderer.py  # PDF resume generation (ReportLab)
│   ├── scheduler.py        # Time-based bot scheduling
│   ├── knowledge_base.py   # KB CRUD, LLM extraction, resume ingestion
│   ├── document_parser.py  # PDF/DOCX/TXT/MD text extraction
│   ├── resume_parser.py    # Markdown resume → KB entries
│   ├── resume_scorer.py    # TF-IDF cosine similarity scoring
│   ├── jd_analyzer.py      # JD keyword extraction, section detection
│   ├── experience_calculator.py  # Domain-specific years from roles
│   ├── resume_assembler.py # Score, select, render, compile resumes from KB
│   ├── latex_compiler.py   # LaTeX → PDF compilation (TinyTeX/pdflatex)
│   ├── ats_scorer.py       # ATS compatibility scoring (6 platforms)
│   ├── ats_profiles.py     # ATS platform-specific scoring profiles
│   └── kb_migrator.py      # Auto-migrate legacy .txt/.md files to KB
├── bot/
│   ├── bot.py              # Main bot loop (search → filter → generate → apply)
│   ├── browser.py          # Playwright browser manager
│   ├── search/             # LinkedIn and Indeed scrapers
│   └── apply/              # Platform-specific appliers (LinkedIn, Indeed, Greenhouse, Lever, Workday, Ashby)
├── templates/index.html    # Single-page dashboard (HTML shell)
├── static/
│   ├── css/main.css        # Extracted stylesheet
│   ├── js/                 # 17 ES modules (app.js entry point)
│   └── locales/en.json     # i18n string catalog (430+ keys, 25 sections)
├── routes/                 # 8 Flask Blueprints (bot, applications, config, profile, login, analytics, lifecycle, knowledge_base)
├── electron/               # Electron desktop shell
│   ├── main.js             # App window, tray, lifecycle
│   ├── python-backend.js   # Python process management
│   ├── icons/              # Generated app icons (PNG, ICO, ICNS)
│   └── scripts/            # Build scripts (version sync, icon gen, Python bundling)
├── tests/                  # 1385 tests (pytest)
└── docs/                   # User and developer documentation
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Setup & Installation](docs/guides/setup.md) | Install, first launch, platform login |
| [How the Bot Works](docs/guides/how-the-bot-works.md) | Full pipeline — searching, scoring, applying |
| [Writing Experience Files](docs/guides/experience-files.md) | Describe your background for better AI-generated resumes |
| [How AI Generation Works](docs/guides/ai-generation.md) | What happens when AutoApply creates your documents |
| [Application Flow](docs/architecture/application-flow.md) | Flowcharts for the full bot pipeline |
| [Configuration](docs/guides/configuration.md) | All settings explained |
| [Knowledge Base](docs/guides/knowledge-base.md) | Upload documents, build KB, assemble resumes with zero API calls |
| [Troubleshooting](docs/guides/troubleshooting.md) | Common problems and fixes |
| [API Reference](docs/api/endpoints.md) | REST API for developers |
| [Changelog](CHANGELOG.md) | Version history |

## Your Data

Everything stays on your machine at `~/.autoapply/`:

```
~/.autoapply/
├── config.json              # Your settings
├── autoapply.db             # Application history + Knowledge Base (SQLite)
├── profile/
│   ├── experiences/         # Your background (.txt files fed to AI)
│   ├── uploads/             # Uploaded career documents (PDF, DOCX, TXT, MD)
│   ├── resumes/             # Generated resumes (PDF)
│   ├── cover_letters/       # Generated cover letters
│   └── job_descriptions/    # Saved job postings (HTML)
├── browser_profile/         # Chrome login sessions (persisted)
└── backend.log              # Server logs
```

## Testing

```bash
python -m pytest tests/ -v
```

1385 tests covering settings, database, API endpoints, bot logic, AI engine, scoring/filtering, resume rendering, scheduling, login flow, applier modules, i18n, accessibility, security hardening, resilience, analytics, resume versioning, knowledge base, TF-IDF scoring, LaTeX compilation, ATS scoring, resume assembly, performance, intelligence, and migration.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask, Flask-SocketIO, gevent |
| Database | SQLite (stdlib `sqlite3`) |
| Browser automation | Playwright (persistent context, system Chrome) |
| AI | Multi-provider LLM API (Anthropic, OpenAI, Google, DeepSeek) |
| PDF generation | ReportLab (fallback), LaTeX via Jinja2 templates (KB assembly) |
| Config | Pydantic v2 |
| Desktop | Electron |
| Frontend | Vanilla JS SPA (17 ES modules, no build step) |
| i18n | JSON locale files (`static/locales/`) with `t()` translation function |
| Accessibility | WCAG 2.1 AA (ARIA, keyboard nav, focus management, reduced motion) |
| Tests | pytest (1385 tests, 97% coverage on core modules) |

## Disclaimer

> **This software is provided for educational and personal-use purposes only.**
>
> - AutoApply automates interactions with third-party platforms (LinkedIn, Indeed, Greenhouse, Lever, Workday, Ashby). **Using automated tools may violate the Terms of Service of these platforms.** You are solely responsible for ensuring your use complies with all applicable terms, policies, and laws.
> - The authors and contributors are **not responsible** for any consequences arising from the use of this software, including but not limited to: account suspension or termination, legal action from platform providers, rejected or misattributed job applications, or any other damages.
> - This software is provided **"as is"** without warranty of any kind. Use it **at your own risk**.
> - The authors do not endorse or encourage violation of any platform's Terms of Service.

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes and add tests
4. Run `python -m pytest tests/ -v` to verify
5. Submit a pull request

## License

MIT License. See [LICENSE](LICENSE) for details.
