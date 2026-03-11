# AutoApply — Product Requirements Document

> **Version:** 4.0 | **Status:** Active | **Last Updated:** March 2026
> **Purpose of this document:** Complete specification for Claude Code to implement AutoApply end-to-end. Each section is written to be directly actionable. Follow sections in order. Do not skip ahead.

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Goals & Success Metrics](#2-goals--success-metrics)
3. [Platform & Environment](#3-platform--environment)
4. [System Architecture](#4-system-architecture)
5. [Tech Stack](#5-tech-stack)
6. [Project Structure](#6-project-structure)
7. [Profile Folder System](#7-profile-folder-system)
8. [Claude Code AI Engine](#8-claude-code-ai-engine)
9. [Component Specifications](#9-component-specifications)
   - 9.1 [Web Dashboard (UI)](#91-web-dashboard-ui)
   - 9.2 [Job Search Engine](#92-job-search-engine)
   - 9.3 [Filter & Matching Engine](#93-filter--matching-engine)
   - 9.4 [Resume & Cover Letter Generator](#94-resume--cover-letter-generator)
   - 9.5 [Auto-Apply Bot](#95-auto-apply-bot)
   - 9.6 [Tracker Database](#96-tracker-database)
10. [Job Portal Coverage](#10-job-portal-coverage)
11. [Database Schema](#11-database-schema)
12. [API Contracts](#12-api-contracts)
13. [Configuration Schema](#13-configuration-schema)
14. [UI Screens & Behaviour](#14-ui-screens--behaviour)
15. [Error Handling](#15-error-handling)
16. [Risks & Mitigations](#16-risks--mitigations)
17. [Build Phases](#17-build-phases)
18. [Out of Scope (v1.0)](#18-out-of-scope-v10)
19. [Open Questions](#19-open-questions)

---

## 1. Product Overview

AutoApply is a **fully automated, locally-run job application platform**. It runs on the user's own machine and requires no cloud account.

The bot:
- Discovers relevant job postings on LinkedIn, Indeed, and company career portals
- Filters them against the user's criteria
- Reads raw experience files the user has written in plain language from a local `profile/` folder
- Invokes **Claude Code via terminal** to generate a tailored resume and cover letter for each specific job — no separate API key required
- Submits applications through a dedicated Playwright-managed Chromium instance using the generated documents
- Logs every application to a local SQLite database, including **exactly which resume and cover letter were used**

The user interacts exclusively through a **polished web dashboard** served on `localhost`. The automation runs in a Chromium window that the user can observe and override at any point. The bot supports three application modes:

- **Full Auto** — bot applies without pausing (default for high-confidence matches)
- **Review Mode** — bot pauses before each submission and shows the user a preview of the generated resume and cover letter in the dashboard. The user can approve, edit, or skip.
- **Watch Mode** — browser window is visible so the user can see every click and form fill in real time

The user can switch modes at any time, and can always pause/stop the bot mid-application.

---

## 2. Goals & Success Metrics

| Goal | Metric |
|------|--------|
| High application volume | 50+ applications/day when running continuously |
| Accurate matching | 95%+ of submitted applications meet user's stated criteria |
| Tailored documents | Every application has a unique resume and cover letter crafted for that specific job |
| Document traceability | Dashboard shows which resume + cover letter was used for every single application |
| Reliability | Bot runs 8+ hours without manual intervention |
| Portal coverage | LinkedIn + Indeed + Greenhouse + Lever + Workday |
| Dashboard performance | UI loads and responds in <1 second |
| Privacy | Zero data leaves the machine (except job platform traffic) |
| No API key required | Claude Code subscription is sufficient — no separate Anthropic API key needed |

---

## 3. Platform & Environment

### Supported Operating Systems

| OS | Versions | Notes |
|----|----------|-------|
| **macOS** | 12 Monterey and later | Apple Silicon (arm64) and Intel (x86_64) |
| **Windows** | 10 and 11 (64-bit) | PowerShell 5+ required for setup script |
| **Ubuntu** | 20.04 LTS and 22.04 LTS | 64-bit only; may work on other Debian-based distros |

### Runtime Requirements

- Python 3.11 or later
- **Claude Code** installed and authenticated (`claude` command available in PATH)
- Node.js is NOT required (pure Python stack)
- Playwright installs its own bundled Chromium — no system browser dependency
- Internet connection required for job scraping
- Minimum 4 GB RAM, 2 GB free disk space

### Cross-Platform Notes for Implementation

- Use `pathlib.Path` everywhere — never hardcode `/` or `\` path separators
- Use `Path.home()` for the default data directory
- Detect OS with `platform.system()` — returns `"Darwin"`, `"Windows"`, or `"Linux"`
- Credentials storage:
  - macOS: `keyring` library using macOS Keychain
  - Windows: `keyring` library using Windows Credential Manager
  - Ubuntu: `keyring` library using Secret Service (GNOME Keyring / KWallet)
- The setup script must be a single file that works on all three OSes: `setup.py`
- When invoking Claude Code on Windows, fall back to `claude.cmd` if `claude` is not found directly in PATH

---

## 4. System Architecture

```
+-------------------------------------------------------------+
|                    User's Web Browser                        |
|               http://localhost:5000 (Dashboard)              |
+-------------------------+-----------------------------------+
                          | HTTP + WebSocket
+-------------------------v-----------------------------------+
|                 Flask App (app.py)                           |
|       REST API + WebSocket server (Flask-SocketIO)           |
+------+----------+-------------+--------------+--------------+
       |          |             |              |
+------v--+ +-----v----+ +------v------+ +----v--------+
| Job     | | Filter   | | Tracker     | | Profile     |
| Search  | | Engine   | | (SQLite)    | | Watcher     |
| Engine  | |          | |             | |             |
+------+--+ +-----+----+ +-------------+ +----+--------+
       |          |                           |
+------v----------v---------------------------v--------------+
|                 Auto-Apply Bot (bot.py)                     |
|          Playwright + isolated Chromium instance            |
+--------------------------+---------------------------------+
                           | subprocess call
+--------------------------v---------------------------------+
|              Claude Code AI Engine                          |
|   Reads:  profile/experiences/ + job description           |
|   Writes: profile/resumes/ + profile/cover_letters/        |
|   Command: claude --print "..."                            |
+------------------------------------------------------------+
```

### Key Design Decisions

1. **Chromium isolation:** The bot uses Playwright's bundled Chromium with a dedicated browser profile at `~/.autoapply/browser_profile/` — completely separate from the user's personal browsers.
2. **User visibility and control:** The application process is always visible to the user through the dashboard live feed. In Review Mode, the bot pauses before each submission and shows the generated resume and cover letter for approval. In Watch Mode, the Chromium browser is visible. In Full Auto mode, Chromium runs in the background but all activity is still shown in the live feed. The user can override, skip, or edit at any stage.
3. **Single process:** Flask runs in the main thread; the bot runs in a background thread. Use `threading.Thread` with a shared `bot_state` object protected by `threading.Lock`.
4. **Real-time updates:** Flask-SocketIO pushes live updates to the dashboard. Every bot action (search, filter, score, generate, apply) emits a feed event so the user always knows what's happening.
5. **No external database server:** SQLite only at `~/.autoapply/autoapply.db`.
6. **Claude Code as AI engine:** The bot invokes Claude Code via `subprocess` using the `--print` flag. No separate Anthropic API key is needed — only a Claude Code subscription.
7. **Profile folder as source of truth:** All user experience and skills live as plain `.txt` files in `~/.autoapply/profile/experiences/`. The user edits these in any text editor; the bot reads them fresh for every job.

---

## 5. Tech Stack

| Layer | Library / Tool | Version | Purpose |
|-------|---------------|---------|---------|
| Web framework | `flask` | 3.x | Serves dashboard + REST API |
| WebSocket | `flask-socketio` | 5.x | Real-time bot status to UI |
| Browser automation | `playwright` | 1.x | Controls Chromium for scraping + applying |
| AI engine | `claude` (Claude Code CLI) | latest | Generates tailored resumes and cover letters |
| Database | `sqlite3` | stdlib | Local application tracker |
| Credentials | `keyring` | 25.x | Secure credential storage cross-platform |
| Resume export | `reportlab` | latest | Renders generated resume Markdown to PDF |
| Config | `pydantic` | 2.x | Validate and store user configuration |
| Scheduling | `apscheduler` | 3.x | Run job searches on a timer |
| HTTP | `httpx` | latest | Any direct HTTP requests needed |

### Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 6. Project Structure

```
autoapply/
├── setup.py                    # One-time setup: install deps, create dirs, first-run config
├── run.py                      # Entry point: starts Flask + opens browser to localhost:5000
├── requirements.txt
├── README.md
|
├── app.py                      # Flask: routes, SocketIO events, bot thread management
|
├── bot/
|   ├── __init__.py
|   ├── bot.py                  # Main bot loop: search -> filter -> generate -> apply
|   ├── browser.py              # Playwright browser/context management
|   ├── state.py                # Shared BotState (status, counters, stop flag)
|   |
|   ├── search/
|   |   ├── __init__.py
|   |   ├── base.py             # Abstract base class for all search scrapers
|   |   ├── linkedin.py
|   |   └── indeed.py
|   |
|   └── apply/
|       ├── __init__.py
|       ├── base.py             # Abstract base class for all apply scripts
|       ├── linkedin.py
|       ├── indeed.py
|       ├── greenhouse.py
|       ├── lever.py
|       └── workday.py
|
├── core/
|   ├── __init__.py
|   ├── filter.py               # Job scoring and matching engine
|   ├── ai_engine.py            # Claude Code invocation: resume + cover letter generation
|   ├── resume_renderer.py      # Markdown -> PDF via reportlab
|   └── scheduler.py            # APScheduler for timed searches
|
├── db/
|   ├── __init__.py
|   ├── database.py             # SQLite connection, init, all queries
|   └── models.py               # Pydantic models for DB rows
|
├── config/
|   ├── __init__.py
|   └── settings.py             # Pydantic settings; reads/writes ~/.autoapply/config.json
|
├── static/
|   ├── css/app.css
|   ├── js/app.js
|   └── fonts/
|
└── templates/
    └── index.html              # Single-page dashboard (all screens, JS-controlled)
```

### User Data Directory (`~/.autoapply/`)

```
~/.autoapply/
├── config.json
├── autoapply.db
├── browser_profile/            # Playwright persistent Chromium profile
├── backups/                    # Auto daily DB backups
|
└── profile/                    # USER-EDITABLE (see Section 7)
    ├── experiences/            # User writes raw .txt files here
    |   ├── README.txt          # Auto-generated instructions for the user
    |   └── [any .txt files]
    |
    ├── jobs/                   # Bot writes job descriptions here before AI generation
    |   └── [job_id].txt        # Deleted after generation completes
    |
    ├── resumes/                # Claude Code writes generated resumes here
    |   └── [job_id]_[company]_[date].pdf
    |
    └── cover_letters/          # Claude Code writes generated cover letters here
        └── [job_id]_[company]_[date].txt
```

---

## 7. Profile Folder System

This is the core innovation. The user writes about themselves in plain natural language — no forms, no structured templates. Claude Code reads everything and decides what to include for each specific job.

### How the User Populates Their Profile

The `~/.autoapply/profile/experiences/` folder is the user's career brain dump. On first setup the folder is created with a `README.txt` explaining the format.

**One `.txt` file per experience, role, project, or skill topic. Files can be named anything.**

Example folder:
```
experiences/
├── README.txt
├── skills.txt
├── stripe-senior-engineer-2022-2024.txt
├── freelance-projects-2020-2022.txt
├── open-source.txt
├── education.txt
└── personal-projects.txt
```

Example content of `stripe-senior-engineer-2022-2024.txt`:
```
I worked at Stripe from early 2022 to late 2024 as a Senior Frontend Engineer.
My main project was rebuilding the payments dashboard from scratch in React and TypeScript.
The old dashboard was slow and had lots of bugs. I led a team of 4 engineers.
We shipped it in 8 months and it reduced support tickets by 40%.
I also worked on the design system — built about 30 reusable components used across the company.
I got really good at performance optimisation: went from 8 second load times to under 1 second.
Stack: React, TypeScript, GraphQL, Jest, Figma.
```

Example content of `skills.txt`:
```
Frontend: React, TypeScript, Next.js, Vue, CSS, Tailwind, design systems
Backend: Python, Node.js, FastAPI, PostgreSQL, Redis
Cloud: AWS (S3, Lambda, EC2), Vercel, basic Kubernetes
I'm strongest in React and TypeScript. I've been coding for 8 years.
I prefer working on products that users actually touch, not internal tools.
I'm a good communicator and have led small teams.
```

### What the Bot Does With These Files

When a job passes the filter:

1. Bot saves the full job description to `profile/jobs/[job_id].txt`
2. Bot invokes Claude Code (see Section 8) with all experience files + the job description
3. Claude Code outputs:
   - A tailored resume in Markdown format → saved to `profile/resumes/[job_id]_[company]_[date].md`
   - A cover letter in plain text → saved to `profile/cover_letters/[job_id]_[company]_[date].txt`
4. `resume_renderer.py` converts the Markdown resume to a clean ATS-safe PDF
5. Bot uploads the PDF resume and pastes the cover letter text into the application form
6. Database records the exact file paths used for this application

### Profile Folder Rules

- User can add, edit, or delete experience files at any time — changes take effect on the next application
- Files must be `.txt` format; plain English preferred
- No maximum file count; keep individual files under 2000 words for best results
- The `jobs/`, `resumes/`, and `cover_letters/` subfolders are managed automatically — user should not edit them

---

## 8. Claude Code AI Engine

**File:** `core/ai_engine.py`

This module invokes Claude Code via terminal subprocess to generate tailored documents. No API key needed.

### Invoking Claude Code

```python
import subprocess
import shutil
from pathlib import Path

# On Windows, fall back to claude.cmd if claude is not in PATH
CLAUDE_CMD = "claude" if shutil.which("claude") else "claude.cmd"

def invoke_claude_code(prompt: str, timeout_seconds: int = 120) -> str:
    """
    Runs Claude Code non-interactively via --print flag.
    Returns stdout as a string.
    Raises RuntimeError if Claude Code is unavailable or returns non-zero exit code.
    """
    result = subprocess.run(
        [CLAUDE_CMD, "--print", prompt],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code failed (exit {result.returncode}): {result.stderr}")
    return result.stdout.strip()
```

### Resume Generation Prompt

```python
RESUME_PROMPT = """
You are an expert resume writer. Create a tailored, ATS-optimised resume for this specific job.

Instructions:
- Read ALL experience files below carefully
- Select only experiences and skills most relevant to THIS job
- Quantify achievements wherever numbers appear in the raw notes
- Use strong action verbs
- Keep content to one page worth of text
- Do NOT invent or exaggerate anything not present in the experience files

Output format — Markdown only, no preamble, no explanation:

# [Full Name]
[email] | [phone] | [location] | [linkedin if provided] | [portfolio if provided]

## Summary
2-3 sentences tailored specifically to this role and company.

## Experience
### [Job Title] — [Company] ([Start Year] - [End Year or Present])
- Achievement bullet using numbers where available
- Achievement bullet
...

## Skills
Comma-separated, relevant skills only.

## Education
[Degree] — [Institution] ([Year])

Omit any section for which there is no information.

---
EXPERIENCE FILES:
{experience_files_content}

---
JOB DESCRIPTION:
{job_description}

---
APPLICANT:
Name: {full_name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin_url}
Portfolio: {portfolio_url}
"""
```

### Cover Letter Generation Prompt

```python
COVER_LETTER_PROMPT = """
You are an expert career coach. Write a cover letter for this job application.

Instructions:
- 3 paragraphs, professional but not stiff
- Reference specific details from the job description
- Use relevant experiences from the experience files
- Do NOT use filler phrases like "I am excited to apply" or "I am a perfect fit"
- Do NOT repeat the resume — add context and personality
- Match tone to the company culture inferred from the job description
- Output ONLY the cover letter body — no date, no address, no salutation header, no sign-off

---
EXPERIENCE FILES:
{experience_files_content}

---
JOB DESCRIPTION:
{job_description}

---
APPLICANT:
Name: {full_name}
Bio / tone preference: {bio}
"""
```

### Full Generation Flow

```python
from datetime import datetime

def generate_documents(
    job: "ScoredJob",
    profile: "UserProfile",
    experience_dir: Path,
    output_dir_resumes: Path,
    output_dir_cover_letters: Path,
) -> tuple[Path, Path]:
    """
    Reads all .txt files from experience_dir, calls Claude Code twice,
    saves outputs, returns (resume_pdf_path, cover_letter_txt_path).
    """
    experience_content = read_all_experience_files(experience_dir)
    safe_company = job.raw.company.replace(" ", "-").lower()
    date_str = datetime.now().strftime("%Y-%m-%d")
    base_name = f"{job.id}_{safe_company}_{date_str}"

    # Generate resume (Markdown)
    resume_md_text = invoke_claude_code(RESUME_PROMPT.format(
        experience_files_content=experience_content,
        job_description=job.raw.description,
        full_name=profile.full_name,
        email=profile.email,
        phone=profile.phone,
        location=profile.location,
        linkedin_url=profile.linkedin_url or "N/A",
        portfolio_url=profile.portfolio_url or "N/A",
    ))

    # Generate cover letter
    cover_letter_text = invoke_claude_code(COVER_LETTER_PROMPT.format(
        experience_files_content=experience_content,
        job_description=job.raw.description,
        full_name=profile.full_name,
        bio=profile.bio,
    ))

    # Save and render resume
    resume_md_path = output_dir_resumes / f"{base_name}.md"
    resume_pdf_path = output_dir_resumes / f"{base_name}.pdf"
    resume_md_path.write_text(resume_md_text, encoding="utf-8")
    render_resume_to_pdf(resume_md_text, resume_pdf_path)

    # Save cover letter
    cl_path = output_dir_cover_letters / f"{base_name}.txt"
    cl_path.write_text(cover_letter_text, encoding="utf-8")

    return resume_pdf_path, cl_path


def read_all_experience_files(experience_dir: Path) -> str:
    """
    Reads all .txt files in the directory (excluding README.txt).
    Returns them concatenated with clear section separators.
    """
    parts = []
    for f in sorted(experience_dir.glob("*.txt")):
        if f.name.lower() == "readme.txt":
            continue
        parts.append(f"=== {f.name} ===\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)
```

### Checking Claude Code Availability

Run this in `setup.py` and at every bot startup:

```python
def check_claude_code_available() -> bool:
    try:
        result = subprocess.run(
            [CLAUDE_CMD, "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
```

If not available:
- Log a warning
- Fall back to static cover letter template from `config.bot.cover_letter_template`
- Fall back to the uploaded fallback resume PDF from `config.profile.fallback_resume_path`
- Show persistent warning banner in dashboard: "Claude Code not detected — using fallback templates. Install Claude Code for AI-tailored documents."

---

## 9. Component Specifications

### 9.1 Web Dashboard (UI)

**Files:** `templates/index.html`, `static/js/app.js`, `static/css/app.css`

#### Design Requirements

- Modern, dark-themed UI — professional SaaS quality
- Single HTML page; screens shown/hidden with JavaScript (no page reloads)
- REST API + Socket.IO for all backend communication
- Responsive for standard laptop screen sizes
- No external CDN dependencies — all assets bundled or inline

#### Screens

| Screen | Anchor | Description |
|--------|--------|-------------|
| Setup | `#setup` | First-run wizard (see Section 14) |
| Dashboard | `#dashboard` | Bot controls, live feed, today's stats |
| Applications | `#applications` | Full tracker with resume + cover letter per row |
| Profile | `#profile` | View/edit/add experience files |
| Analytics | `#analytics` | Charts: daily applications, status breakdown, platform split |
| Settings | `#settings` | All configuration |

#### Bot Control Bar (always visible at top)

```
[ STATUS BADGE ]   Found today: 47   Applied: 23   [ START ] [ PAUSE ] [ STOP ]
```

Status badge states: IDLE / RUNNING / PAUSED / ERROR

#### Live Feed Event Types

| Event | Colour | Detail shown |
|-------|--------|-------------|
| FOUND | Blue | Job title, company, platform |
| FILTERED | Gray | Score + reason skipped |
| GENERATING | Yellow | "Creating resume + cover letter via Claude Code..." |
| REVIEW | Purple | Job details + preview card with Approve / Edit / Skip buttons (review/watch mode only) |
| APPLYING | Blue | ATS type detected |
| APPLIED | Green | Resume filename used |
| SKIPPED | Gray | User chose to skip during review |
| ERROR | Red | Error message |
| CAPTCHA | Red | Company name + alert |

#### Review Mode UI

When `apply_mode` is `"review"` or `"watch"`, the bot pauses before each submission and emits a `REVIEW` event. The dashboard shows a **Review Card** in the live feed:

```
┌──────────────────────────────────────────────────────────────────┐
│  REVIEW    Senior Engineer @ Stripe    [LinkedIn]    Score: 87  │
│                                                                  │
│  ┌─── Resume Preview ──────────────────────────────────────────┐│
│  │ JOHN DOE                                                    ││
│  │ Software Engineer | 8 years experience                      ││
│  │ ...                                                         ││
│  └─────────────────────────────────────────────────────────────┘│
│  ┌─── Cover Letter ───────────────────────────────────────────┐│
│  │ Dear Hiring Manager,                                        ││
│  │ I am writing to express my interest in the Senior            ││
│  │ Engineer role at Stripe...                                   ││
│  │ (editable textarea)                                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  [ Approve & Apply ]    [ Edit & Apply ]    [ Skip ]             │
└──────────────────────────────────────────────────────────────────┘
```

- **Approve & Apply** — submit with generated documents as-is
- **Edit & Apply** — user modifies cover letter (and optionally resume), then submit
- **Skip** — don't apply to this job, move to next

The bot blocks until the user makes a decision. If the user doesn't respond, the bot stays paused on that job indefinitely (it won't time out and auto-submit).

---

### 9.2 Job Search Engine

**Files:** `bot/search/base.py`, `bot/search/linkedin.py`, `bot/search/indeed.py`

#### Base Class

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

@dataclass
class RawJob:
    title: str
    company: str
    location: str
    salary: str | None
    description: str
    apply_url: str
    platform: str        # "linkedin" | "indeed" | "greenhouse" | etc.
    external_id: str     # Platform-specific ID for deduplication
    posted_at: str | None

class BaseSearcher(ABC):
    @abstractmethod
    def search(self, criteria: "SearchCriteria") -> Iterator[RawJob]:
        """Yield RawJob objects one at a time as discovered."""
        ...
```

#### Search Criteria

```python
@dataclass
class SearchCriteria:
    job_titles: list[str]
    locations: list[str]
    remote_only: bool
    salary_min: int | None
    keywords_include: list[str]
    keywords_exclude: list[str]
    experience_levels: list[str]   # ["mid", "senior", "staff"]
    max_results_per_search: int    # Default: 100
```

#### LinkedIn Searcher

- Navigate to `https://www.linkedin.com/jobs/search/` with criteria as query params
- Extract job cards; click each for full detail panel
- Detect "Easy Apply" badge — mark others as `manual_only=True`
- Handle pagination until `max_results_per_search` reached

#### Indeed Searcher

- Navigate to `https://www.indeed.com/jobs` with query params
- Detect "Easily Apply" badge
- Capture final `apply_url` after any redirect

---

### 9.3 Filter & Matching Engine

**File:** `core/filter.py`

#### Scoring (0–100)

```
title_match:     0–35 pts  (+35 substring match, +20 partial overlap)
salary_match:    0–20 pts  (+20 meets min, +10 if unknown, +0 if below)
location_match:  0–20 pts  (+20 remote match or location match, +10 same country)
keyword_match:   0–25 pts  (+5 per keyword_include found, max 25)

Hard disqualifiers (score = 0):
  - keyword_exclude found in title or description
  - company in company_blacklist
  - external_id already in DB (deduplication)
```

#### Output

```python
@dataclass
class ScoredJob:
    id: str             # UUID — used as base filename for generated documents
    raw: RawJob
    score: int
    pass_filter: bool
    skip_reason: str | None
```

---

### 9.4 Resume & Cover Letter Generator

**Files:** `core/ai_engine.py`, `core/resume_renderer.py`

Full specification in **Section 8**. Summary:

- Reads all `.txt` files from `~/.autoapply/profile/experiences/`
- Calls Claude Code twice via subprocess: resume (Markdown output) + cover letter (plain text)
- Saves outputs to `profile/resumes/` and `profile/cover_letters/`
- `resume_renderer.py` converts the Markdown to an ATS-safe single-column PDF via `reportlab`

#### PDF Rendering Rules (`resume_renderer.py`)

```
Font:            Helvetica only (ATS-safe, universally supported)
Name (H1):       18pt bold
Section headers: 12pt bold + thin rule underneath
Body text:       10pt
Bullet points:   10pt, em-dash prefix
Margins:         0.75 inch all sides
No colours, tables, images, or multi-column layouts — plain text only for ATS compatibility
```

---

### 9.5 Auto-Apply Bot

**Files:** `bot/bot.py`, `bot/browser.py`, `bot/apply/base.py`, `bot/apply/*.py`

#### Main Bot Loop (`bot.py`)

```python
def run_bot(state: BotState, config: AppConfig, db: Database):
    profile_dir = Path.home() / ".autoapply" / "profile"

    while not state.stop_flag:
        for searcher in get_enabled_searchers(config):
            for raw_job in searcher.search(config.search_criteria):
                if state.stop_flag:
                    return

                # 1. Filter
                scored = filter_engine.score(raw_job, config)
                if not scored.pass_filter:
                    emit("feed_event", {"type": "FILTERED", ...})
                    continue

                emit("feed_event", {"type": "GENERATING", ...})

                # 2. Generate documents via Claude Code
                try:
                    resume_path, cl_path = generate_documents(
                        job=scored,
                        profile=config.profile,
                        experience_dir=profile_dir / "experiences",
                        output_dir_resumes=profile_dir / "resumes",
                        output_dir_cover_letters=profile_dir / "cover_letters",
                    )
                    cover_letter_text = cl_path.read_text(encoding="utf-8")
                except RuntimeError:
                    # Claude Code unavailable — use fallbacks
                    resume_path = Path(config.profile.fallback_resume_path) if config.profile.fallback_resume_path else None
                    cover_letter_text = render_fallback_template(config, scored)
                    cl_path = None

                # 3. Review gate (if apply_mode is "review" or "watch")
                if config.bot.apply_mode in ("review", "watch"):
                    emit("feed_event", {"type": "REVIEW", ...})
                    # Emit PENDING_REVIEW event with resume text, cover letter text,
                    # job details, and match score. Dashboard shows a preview card
                    # with Approve / Edit / Skip buttons.
                    # Bot waits (blocks) until user responds via API:
                    #   POST /api/bot/review/approve  — proceed to apply
                    #   POST /api/bot/review/skip     — skip this job
                    #   POST /api/bot/review/edit      — update cover letter text,
                    #                                    then proceed to apply
                    decision = wait_for_review_decision(state)
                    if decision.action == "skip":
                        emit("feed_event", {"type": "SKIPPED", ...})
                        continue
                    if decision.action == "edit":
                        cover_letter_text = decision.edited_cover_letter
                        # If user edited resume, re-render PDF
                        if decision.edited_resume:
                            resume_path = re_render_resume(decision.edited_resume)

                emit("feed_event", {"type": "APPLYING", ...})

                # 4. Apply
                applier = get_applier(detect_ats(raw_job.apply_url), browser)
                result = applier.apply(scored, resume_path, cover_letter_text, config.profile)

                # 5. Save to DB with document references
                db.save_application(scored, resume_path, cl_path, cover_letter_text, result)

                # 6. Emit result
                emit("feed_event", {"type": "APPLIED" if result.success else "ERROR", ...})

                # 7. Rate limit
                time.sleep(config.bot.delay_between_applications_seconds)

        time.sleep(config.bot.search_interval_seconds)
```

#### Browser Manager (`browser.py`)

Use `playwright.chromium.launch_persistent_context(user_data_dir=profile_dir)` to preserve login sessions between runs.

```python
class BrowserManager:
    def __init__(self, config: AppConfig):
        self.headless = not config.bot.watch_mode
        self.profile_dir = Path.home() / ".autoapply" / "browser_profile"

    def get_page(self) -> Page: ...
    def close(self): ...
```

#### Base Applier (`apply/base.py`)

```python
@dataclass
class ApplyResult:
    success: bool
    error_message: str | None
    captcha_detected: bool = False
    manual_required: bool = False

class BaseApplier(ABC):
    def __init__(self, page: Page):
        self.page = page

    @abstractmethod
    def apply(
        self,
        job: ScoredJob,
        resume_pdf_path: Path | None,
        cover_letter_text: str,
        profile: UserProfile,
    ) -> ApplyResult: ...

    def _human_type(self, locator, text: str):
        for char in text:
            locator.type(char)
            time.sleep(random.uniform(0.03, 0.08))

    def _random_pause(self, min_s=0.5, max_s=2.0):
        time.sleep(random.uniform(min_s, max_s))

    def _detect_captcha(self) -> bool: ...
```

#### Portal Applier Behaviour

**LinkedIn (`apply/linkedin.py`):**
1. Navigate to `job.apply_url` → click "Easy Apply"
2. Each step: fill profile fields, upload `resume_pdf_path`, paste cover letter, answer screening questions from `profile.screening_answers`
3. Click Submit → verify confirmation modal → return `ApplyResult(success=True)`

**Indeed (`apply/indeed.py`):**
1. Navigate → fill Quick Apply form → upload resume → submit
2. If redirected to external ATS: return `ApplyResult(manual_required=True)`

**Greenhouse (`apply/greenhouse.py`):**
Fill name/email/phone/location → upload resume → paste cover letter → fill custom questions → submit → verify confirmation text.

**Lever (`apply/lever.py`):**
Same as Greenhouse with Lever-specific CSS selectors.

**Workday (`apply/workday.py`):**
- Call `page.wait_for_load_state("networkidle")` between every step
- Wizard steps: My Information → My Experience → Questions → Self Identify → Review
- Retry once per step on failure; if still failing return `ApplyResult(manual_required=True)`

---

### 9.6 Tracker Database

**Files:** `db/database.py`, `db/models.py`

Never write raw SQL outside the `Database` class.

```python
class Database:
    def __init__(self, db_path: Path): ...
    def init_schema(self): ...
    def save_application(
        self,
        job: ScoredJob,
        resume_path: Path | None,
        cover_letter_path: Path | None,
        cover_letter_text: str,
        result: ApplyResult,
    ) -> int: ...
    def update_status(self, application_id: int, status: str, notes: str = None): ...
    def get_all_applications(self, filters: dict = None) -> list[Application]: ...
    def exists(self, external_id: str, platform: str) -> bool: ...
    def export_csv(self, path: Path): ...
```

---

## 10. Job Portal Coverage

| Phase | Portal | Type | Difficulty | Notable Users |
|-------|--------|------|-----------|--------------|
| 1 | LinkedIn Easy Apply | Search + Apply | Low | Thousands of companies |
| 1 | Indeed Quick Apply | Search + Apply | Low | Small-to-mid companies |
| 2 | Greenhouse | Apply only | Medium | Stripe, Airbnb, Notion, Linear |
| 2 | Lever | Apply only | Medium | Figma, Vercel, many startups |
| 3 | Workday | Apply only | High | Apple, Amazon, Nike, large enterprises |
| 3 | Taleo | Apply only | High | Banks, healthcare, government |
| 4 | iCIMS | Apply only | High | Large retail and insurance |

#### ATS Detection

```python
ATS_FINGERPRINTS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "myworkdayjobs.com": "workday",
    "taleo.net": "taleo",
    "icims.com": "icims",
    "linkedin.com/jobs": "linkedin",
    "indeed.com": "indeed",
}

def detect_ats(url: str) -> str | None:
    for domain, ats in ATS_FINGERPRINTS.items():
        if domain in url:
            return ats
    return None
```

---

## 11. Database Schema

```sql
CREATE TABLE IF NOT EXISTS applications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id         TEXT NOT NULL,
    platform            TEXT NOT NULL,
    job_title           TEXT NOT NULL,
    company             TEXT NOT NULL,
    location            TEXT,
    salary              TEXT,
    apply_url           TEXT NOT NULL,
    match_score         INTEGER NOT NULL,
    resume_path         TEXT,           -- Absolute path to PDF resume used
    cover_letter_path   TEXT,           -- Absolute path to .txt cover letter used
    cover_letter_text   TEXT,           -- Full text copy stored in DB for resilience
    status              TEXT NOT NULL DEFAULT 'applied',
                                        -- applied | interview | offer | rejected | error | manual_required
    error_message       TEXT,
    applied_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes               TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dedup ON applications(external_id, platform);
CREATE INDEX IF NOT EXISTS idx_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applied_at ON applications(applied_at);

CREATE TABLE IF NOT EXISTS feed_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,  -- FOUND | FILTERED | GENERATING | APPLYING | APPLIED | ERROR | CAPTCHA
    job_title   TEXT,
    company     TEXT,
    platform    TEXT,
    message     TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Both `resume_path` and `cover_letter_text` are stored. If the user moves files, the full text remains in the DB; the path remains available for PDF download while the file exists.

---

## 12. API Contracts

All endpoints return JSON. HTTP 200 on success, 4xx/5xx on error.

### Bot Control

| Method | Endpoint | Response |
|--------|----------|----------|
| POST | `/api/bot/start` | `{status: "running"}` |
| POST | `/api/bot/pause` | `{status: "paused"}` |
| POST | `/api/bot/stop` | `{status: "stopped"}` |
| GET | `/api/bot/status` | `{status, jobs_found_today, applied_today, uptime_seconds, claude_code_available}` |

### Applications

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/api/applications` | Query params: `?status=&platform=&search=&limit=&offset=` |
| PATCH | `/api/applications/:id` | Body: `{status, notes}` |
| GET | `/api/applications/:id/cover_letter` | Returns `{cover_letter_text, file_path}` |
| GET | `/api/applications/:id/resume` | Returns PDF file download |
| GET | `/api/applications/export` | Returns CSV file download |

### Profile / Experience Files

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/api/profile/experiences` | Returns `{files: [{name, content, size, modified_at}]}` |
| POST | `/api/profile/experiences` | Body: `{filename, content}` |
| PUT | `/api/profile/experiences/:filename` | Body: `{content}` |
| DELETE | `/api/profile/experiences/:filename` | |
| GET | `/api/profile/status` | Returns `{file_count, total_words, claude_code_available}` |

### Configuration

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/api/config` | Returns full config object |
| PUT | `/api/config` | Body: partial config object |

### Analytics

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/api/analytics/summary` | Returns `{total, by_status, by_platform, response_rate}` |
| GET | `/api/analytics/daily` | Query param: `?days=30` |

### SocketIO Events (Server → Client)

| Event | Payload |
|-------|---------|
| `bot_status` | `{status, jobs_found_today, applied_today}` |
| `feed_event` | `{event_type, job_title, company, platform, message, timestamp}` |
| `captcha_alert` | `{url, job_title, company}` |

---

## 13. Configuration Schema

Stored at `~/.autoapply/config.json`. Managed by `config/settings.py` using Pydantic.

```python
class UserProfile(BaseModel):
    full_name: str
    email: str
    phone: str
    location: str
    bio: str                                # Tone guidance for cover letter generation
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    fallback_resume_path: str | None = None # PDF used when Claude Code is unavailable
    screening_answers: dict = {}            # {"work_authorisation": "Yes", "years_experience": "5"}

class SearchCriteria(BaseModel):
    job_titles: list[str]
    locations: list[str]
    remote_only: bool = False
    salary_min: int | None = None
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []
    experience_levels: list[str] = ["mid", "senior"]

class BotConfig(BaseModel):
    enabled_platforms: list[str] = ["linkedin", "indeed"]
    min_match_score: int = 75
    max_applications_per_day: int = 50
    delay_between_applications_seconds: int = 45
    search_interval_seconds: int = 1800
    apply_mode: str = "review"              # "auto" | "review" | "watch"
    #   auto   — bot applies without pausing, browser hidden
    #   review — bot pauses before submit, shows preview in dashboard for user approval
    #   watch  — browser visible, bot pauses before submit for user approval
    cover_letter_template: str = ""         # Fallback plain text with {job_title}, {company}, {user_name}

class AppConfig(BaseModel):
    profile: UserProfile
    search_criteria: SearchCriteria
    bot: BotConfig
    company_blacklist: list[str] = []
    version: str = "2.0"
```

Credentials (LinkedIn, Indeed passwords) are NEVER stored in `config.json`. Use `keyring.set_password("autoapply", username, password)`.

---

## 14. UI Screens & Behaviour

### Setup Wizard (first-run only, 7 steps)

1. **Welcome** — How AutoApply works; confirms Claude Code is detected; warns if not found
2. **Experience Folder** — Explains the folder; shows the path; opens it in Finder/Explorer/Nautilus; user adds experience files before continuing; shows live file count
3. **Profile** — Full name, email, phone, location, bio, LinkedIn, portfolio
4. **Job Preferences** — Job titles (tag input), locations, remote toggle, salary minimum, include/exclude keywords
5. **Fallback Resume** — Optional file upload (PDF/DOCX) for use when Claude Code is unavailable
6. **Platform Login** — Opens Chromium in headed mode with a label "AutoApply Setup — Please log in"; user logs into LinkedIn and Indeed; sessions saved to browser profile
7. **Done** — Redirect to Dashboard

### Profile Screen

- Lists all files in `~/.autoapply/profile/experiences/`
- Each entry: filename | word count | last modified | first 100 chars preview
- Buttons: Edit (inline modal with text editor), Delete, + New File
- Claude Code status: green tick if available, yellow warning if not

### Applications Screen

Table columns: Company | Job Title | Platform | Match % | Status | Applied Date | Resume | Cover Letter | Actions

- **Resume column:** Filename as download link → clicks download the PDF
- **Cover Letter column:** "View" button → opens modal with full text
- **Actions:** Edit status (dropdown), add notes
- Filters: by status, platform, free-text search
- Export CSV button

### Dashboard Live Feed Detail

Each APPLIED event shows the resume filename used:
```
14:32  APPLIED     Senior Engineer @ Stripe     [LinkedIn]
       Resume: abc123_stripe_2026-03-09.pdf
```

### Application Mode Selector

The dashboard includes an **Application Mode** selector (always visible near the bot controls):

```
Mode: [ Full Auto ▼ ]  ←  dropdown with three options
```

| Mode | Browser | Pauses before submit? | Best for |
|------|---------|----------------------|----------|
| Full Auto | Hidden | No | High-confidence batch applying |
| Review | Hidden | Yes — shows preview card | Default. User approves each application |
| Watch | Visible | Yes — shows preview card | Debugging, first-time setup, learning |

The mode can be changed while the bot is running. If switched from Auto to Review mid-run, the next application will pause for review.

### Override Controls

The user can intervene at any point:
- **Pause** — bot finishes current action, then waits
- **Stop** — bot finishes current action, then shuts down
- **Skip** (during review) — skip this job, move to next
- **Edit** (during review) — modify resume/cover letter before submitting
- The live feed always shows what the bot is doing, even in Full Auto mode

---

## 15. Error Handling

### Claude Code Unavailable

1. `check_claude_code_available()` runs at startup and before each generation
2. If unavailable: show persistent dashboard banner; use fallback resume + cover letter template
3. Mark applications in DB: `cover_letter_path = NULL`, note in `error_message` that fallback was used

### CAPTCHA Detected

1. `state.pause()`
2. Emit `captcha_alert` SocketIO event
3. If browser is hidden (Full Auto or Review mode), switch Chromium to headed mode automatically so user can see the CAPTCHA
4. Dashboard shows alert: "CAPTCHA at [Company] — solve it in the AutoApply browser window, then click Resume"
5. User solves → clicks Resume → `POST /api/bot/start`

### Application Failure

1. Catch exception → log to `feed_events` with `event_type="ERROR"`
2. Save to DB with `status="error"` and `error_message`
3. Continue to next job — no automatic retry

### Rate Limiting

If platform shows "applying too fast" warning: pause for 10 minutes, log, emit to dashboard.

### Graceful Shutdown

On STOP or SIGINT/SIGTERM: set `state.stop_flag = True` → finish current application → close Playwright cleanly → shut down Flask.

---

## 16. Risks & Mitigations

| Challenge | Impact | Mitigation |
|-----------|--------|-----------|
| CAPTCHA detection | High | Pause, alert user, switch to headed mode |
| LinkedIn anti-bot | High | Real Playwright Chromium, human-like typing, randomised delays, persistent sessions |
| Portal UI changes | High | Modular per-portal scripts, independently updatable |
| Workday SPA complexity | Medium | `networkidle` waits, retry once, fallback to `manual_required` |
| Account suspension | Medium | 1 app per 45s rate limit, max 50/day cap |
| Claude Code subprocess timeout | Medium | 120s timeout; graceful fallback to template |
| Poor experience file quality | Medium | README.txt guides user; Claude Code handles messy prose well |
| SQLite corruption | Low | Auto daily backup to `~/.autoapply/backups/` |
| Cross-platform paths | Medium | `pathlib.Path` everywhere, no hardcoded separators |
| Windows Claude Code path | Medium | `shutil.which` check with `claude.cmd` fallback |

---

## 17. Build Phases

Build and fully test each phase before starting the next.

### Phase 1 — Foundation (Week 1)

- [ ] `setup.py` — cross-platform setup; creates full `~/.autoapply/` directory tree; writes `README.txt` into `profile/experiences/`
- [ ] `run.py` — entry point
- [ ] `config/settings.py` — Pydantic config, read/write `config.json`
- [ ] `db/database.py` + `db/models.py` — schema including `resume_path`, `cover_letter_path`, `cover_letter_text`
- [ ] `app.py` — Flask skeleton, all routes stubbed
- [ ] Setup wizard UI (all 7 steps)
- [ ] Profile screen — list/add/edit/delete experience files via API

**Acceptance criteria:** User runs `python run.py`, completes setup wizard, adds experience files, sees them listed in Profile screen.

### Phase 2 — Claude Code AI Engine (Week 2)

- [ ] `core/ai_engine.py` — full `generate_documents()` + `read_all_experience_files()` + `check_claude_code_available()`
- [ ] `core/resume_renderer.py` — Markdown to ATS-safe PDF via reportlab
- [ ] Claude Code availability check + dashboard warning banner
- [ ] Fallback to template when Claude Code unavailable
- [ ] `/api/bot/status` returns `claude_code_available`
- [ ] Unit test: given sample experience files + job description, `generate_documents()` produces a properly formatted PDF and cover letter

**Acceptance criteria:** `generate_documents()` produces professional PDF resume and cover letter .txt. Fallback works when Claude Code is absent.

### Phase 3 — Bot Core (Week 3)

- [ ] `bot/browser.py` — Playwright + persistent Chromium
- [ ] `bot/state.py` — BotState
- [ ] `bot/search/linkedin.py` + `bot/search/indeed.py`
- [ ] `bot/apply/linkedin.py` + `bot/apply/indeed.py`
- [ ] `bot/bot.py` — full loop: search → filter → generate → apply → log
- [ ] SocketIO live feed including GENERATING event with resume filename in APPLIED event

**Acceptance criteria:** Bot finds jobs, generates tailored documents for each, submits Easy Apply applications. Live feed shows resume filename used per application.

### Phase 4 — Dashboard Polish & Review Mode (Week 4)

- [ ] **Application mode selector** — dropdown in bot control bar: Full Auto / Review / Watch
- [ ] **Review mode** — bot pauses before submit, emits REVIEW event with resume + cover letter preview
- [ ] **Review card UI** — preview card in live feed with Approve / Edit / Skip buttons
- [ ] **Review API endpoints** — `POST /api/bot/review/approve`, `/skip`, `/edit`
- [ ] **Bot review gate** — `wait_for_review_decision()` blocks bot thread until user responds
- [ ] **Watch mode** — launches Chromium in headed mode when selected
- [ ] Applications screen: resume PDF download + cover letter modal
- [ ] Analytics screen with Chart.js (daily line, status donut, platform bar)
- [ ] CAPTCHA alert flow — pause bot, show alert, user solves in browser, resumes
- [ ] Full error handling for all failure modes

**Acceptance criteria:** In Review mode, bot pauses before each submission and shows generated documents for user approval. User can approve, edit cover letter, or skip. In Watch mode, browser is visible. Every application in tracker links to its resume and cover letter. All error states handled gracefully.

### Phase 5 — ATS Portals (Week 5)

- [ ] `bot/apply/greenhouse.py` + `bot/apply/lever.py`
- [ ] `detect_ats()` function
- [ ] End-to-end testing on real Greenhouse and Lever postings

**Acceptance criteria:** Bot submits on Greenhouse and Lever using Claude Code-generated resume and cover letter.

### Phase 6 — Workday & Final Polish (Week 6) ✅ COMPLETE

- [x] `bot/apply/workday.py`
- [x] `bot/apply/ashby.py`
- [x] DB auto-backup to `~/.autoapply/backups/`
- [x] Rate limiting + daily cap enforcement
- [x] Cross-platform testing on macOS, Windows, Ubuntu
- [x] README with installation and usage instructions

**Acceptance criteria:** Bot handles Workday. Full cross-platform verification. Ready for daily use.

### Phase 7 — Production Readiness (Completed in v1.8.1–v1.8.3) ✅ COMPLETE

All production-readiness items delivered. Score: 10.0/10. See `.claude/docs/PRODUCTION-READINESS.md`.

- [x] QW-1 through QW-5: SECRET_KEY, swallowed exceptions, logging, race conditions, temp file leak
- [x] ME-1 through ME-9: CI/CD, API auth, input validation, error handlers, Blueprint refactor, test coverage 97%, dep pinning, mypy, graceful shutdown, security hardening
- [x] LE-1: Frontend refactor to 17 ES modules
- [x] LE-2: WCAG 2.1 AA accessibility
- [x] LE-3: Internationalization (460+ strings, backend + frontend i18n infrastructure)
- [x] D-5: SQLite WAL mode + busy timeout
- [x] D-6: LLM retry with exponential backoff
- [x] D-7: Structured JSON logging

### Phase 8 — Distribution & Quality of Life

Goal: Make AutoApply distributable as a standalone installer and complete remaining UX polish.

#### 8.1 — Build Installers (DIST)

- [ ] **DIST-1: App Icons** — Create icon assets: `icon.ico` (Windows, 256x256), `icon.icns` (macOS, 512x512), `icon.png` (Linux, 512x512). Place in `electron/icons/`. *Blocker for all installer builds.*
- [ ] **DIST-2: Version Sync** — Synchronize `electron/package.json` version with Python `pyproject.toml` version (currently 1.0.0 vs 1.8.3). Add script or CI check to enforce version parity.
- [ ] **DIST-3: Windows Installer (.exe)** — Build NSIS installer via `npm run dist:win`. Test: install, launch, apply to a job, uninstall. Verify Python backend bundled correctly in `extraResources`.
- [ ] **DIST-4: macOS Installer (.dmg)** — Build DMG via `npm run dist:mac`. Test: mount, drag to Applications, launch, verify Gatekeeper warning (unsigned). Document code signing steps for future.
- [ ] **DIST-5: Linux Installer (.AppImage)** — Build AppImage via `npm run dist:linux`. Test on Ubuntu 22.04+: launch, apply to a job, verify desktop integration.
- [ ] **DIST-6: Installer CI** — Add GitHub Actions workflow to build installers on push to tags (`v*`). Upload artifacts to GitHub Releases. Platforms: Windows (windows-latest), macOS (macos-latest), Linux (ubuntu-latest).

**Acceptance criteria:** Running `npm run dist:win` (or mac/linux) produces a working installer that bundles the Python backend. User installs, launches, completes wizard, and can start applying — no Python or Node.js required on their machine.

**Dependencies:** DIST-1 (icons) blocks DIST-3/4/5. DIST-2 (version sync) should be done first.

#### 8.2 — Frontend i18n Migration (QOL)

- [ ] **QOL-1: Migrate JS Strings** — Replace ~26 hardcoded English strings across 7 JS files (`bot-control.js`, `applications.js`, `settings.js`, `profile.js`, `login.js`, `wizard.js`, `feed.js`) with `t()` calls. Add any missing keys to `static/locales/en.json`.
- [ ] **QOL-2: Migrate HTML Strings** — Replace ~150 hardcoded English strings in `templates/index.html` (form labels, button text, headings, placeholders, dropdown options, table headers) with data attributes or JS-driven `t()` calls on page load.
- [ ] **QOL-3: Locale Switcher UI** — Add language selector dropdown to Settings tab. Calls `setLocale()` and refreshes UI strings without page reload.
- [ ] **QOL-4: Sample Translation** — Create `static/locales/es.json` (Spanish) as proof that the i18n system works end-to-end. Translate at least the nav, buttons, and error sections (~80 strings).

**Acceptance criteria:** All user-visible strings in the frontend come from locale JSON files. Switching locale in Settings immediately updates all text. Spanish translation renders correctly.

#### 8.3 — Dark/Light Theme (QOL)

- [ ] **QOL-5: Theme Toggle** — Add theme toggle (sun/moon icon) to the navbar or Settings. Persist preference in `localStorage`. Default: dark (current theme).
- [ ] **QOL-6: Light Theme CSS** — Create CSS custom properties (`--bg-primary`, `--text-primary`, `--accent`, etc.) in `static/css/main.css`. Refactor existing dark theme to use variables. Add `[data-theme="light"]` overrides.

**Acceptance criteria:** User can switch between dark and light themes. Preference persists across sessions. All UI elements readable in both themes.

#### 8.4 — E2E Tests (QOL)

- [ ] **QOL-7: Playwright E2E Setup** — Add Playwright test config for the Electron app. Test harness starts Flask backend + Electron, runs tests against the live app.
- [ ] **QOL-8: Core E2E Scenarios** — Write E2E tests for: wizard completion, bot start/stop, application table rendering, settings save, profile file CRUD, theme toggle, locale switch. Covers the 13 remaining ⚠️ items in the traceability matrix.

**Acceptance criteria:** `npx playwright test` runs 8+ E2E scenarios against the live Electron app. All pass. Traceability matrix ⚠️ items reduced from 13 to ≤5.

---

## 18. Out of Scope (v2.0)

- Cloud hosting or remote server execution
- Mobile app or mobile dashboard
- Automated interview scheduling
- Multi-user or team accounts
- Salary negotiation assistance
- Video or async interview responses
- Taleo and iCIMS automation (covered in a future version)
- Browser extension
- ~~Direct Anthropic API integration~~ — **DONE** (v1.8.1, multi-provider LLM API)
- Code signing + notarization (D-4, requires certificates)
- Auto-update via electron-updater (D-1, requires D-4)
- Crash reporting / Sentry (D-2, requires consent flow)
- Telemetry / usage analytics (D-3, requires consent flow)

---

## 19. Open Questions

### Resolved (Phases 1–7)

1. **Daily cap enforcement:** Hard limit — bot stops at `max_applications_per_day`. ✅
2. **Multiple resume styles:** Single format (ATS-safe Helvetica PDF). ✅
3. **Screening question handling:** Pre-configured in setup wizard + Settings UI (`screening_answers` dict). ✅
4. **Cover letter length:** AI-determined based on job description. ✅
5. **Failed application retry:** No auto-retry. User can re-apply manually. ✅
6. **Experience file completeness feedback:** Not implemented — low priority. Deferred.
7. **Windows Claude Code path:** Superseded — Claude Code CLI replaced by direct LLM API. ✅

### Open (Phase 8)

8. **Icon design:** Use a simple placeholder icon or commission a proper logo before first public installer release?
9. **Python bundling strategy:** Should installers bundle a full Python interpreter (PyInstaller/cx_Freeze), or require Python pre-installed? Current approach relies on user having Python.
10. **Frontend i18n granularity:** Migrate all ~150 HTML strings to `t()`, or only the dynamic/JS-set ones (~26)?

---

*End of document. All sections are directly implementable by Claude Code without further clarification, except the open questions in Section 19.*
