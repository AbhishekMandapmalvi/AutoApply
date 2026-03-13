# System Architecture Document

**Document ID**: SAD-TASK-004-bot-core
**Version**: 1.0
**Date**: 2026-03-09
**Status**: approved (retroactive)
**Author**: Claude (System Engineer)
**SRS Reference**: SRS-TASK-004-bot-core

---

## 1. Executive Summary

This architecture delivers the Bot Core (Phase 3, v1.3.0) — the autonomous job application engine at the heart of AutoApply. It introduces seven new modules spanning browser management, job searching, scoring/filtering, and application submission, orchestrated by a main bot loop that emits real-time feed events via SocketIO.

The design follows a **pipeline architecture**: search --> score --> generate --> apply --> save. Each stage is isolated behind abstract base classes, enabling new platforms and ATS integrations to be added without modifying the pipeline itself. A persistent Playwright browser context preserves login sessions across runs, and human-like interaction timing reduces detection risk.

Key components: `BrowserManager` (persistent Playwright context), `LinkedInSearcher` / `IndeedSearcher` (job discovery), `score_job()` / `detect_ats()` (filtering engine), `LinkedInApplier` / `IndeedApplier` (application automation), `BotState` (thread-safe state machine), and `run_bot()` (main loop orchestrator).

---

## 2. Architecture Overview

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            app.py (Flask API)                               │
│   POST /api/bot/start ──▶ spawns daemon thread                             │
│   POST /api/bot/stop  ──▶ sets stop_flag                                   │
│   POST /api/bot/pause ──▶ sets paused status                               │
│   GET  /api/bot/status ──▶ reads BotState                                  │
└───────────┬─────────────────────────────────────────────────────────────────┘
            │ (daemon thread)
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         bot/bot.py — run_bot()                              │
│                     Main Loop Orchestrator                                  │
│                                                                             │
│   ┌─────────────┐    ┌──────────────┐    ┌───────────────┐                 │
│   │  SEARCHERS   │    │  core/filter  │    │  core/ai_     │                 │
│   │  registry    │───▶│  score_job()  │───▶│  engine.py    │                 │
│   │  (dict)      │    │  detect_ats() │    │  generate_    │                 │
│   └──────┬───────┘    └──────────────┘    │  documents()  │                 │
│          │                                 └───────┬───────┘                 │
│          │                                         │                         │
│          ▼                                         ▼                         │
│   ┌──────────────┐                         ┌───────────────┐                │
│   │  APPLIERS     │◀────── platform ───────│  ApplyResult   │                │
│   │  registry     │        routing          │  (dataclass)   │                │
│   │  (dict)       │                         └───────────────┘                │
│   └──────┬───────┘                                                          │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────┐    ┌──────────────┐    ┌───────────────┐                │
│   │  Database     │    │  BotState     │    │  SocketIO      │                │
│   │  save_app()   │    │  (counters)   │    │  emit_func()   │                │
│   └──────────────┘    └──────────────┘    └───────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      bot/browser.py — BrowserManager                        │
│                                                                             │
│   Playwright Persistent Context ──▶ ~/.autoapply/browser_profile/           │
│   ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐             │
│   │ _find_system_  │  │ get_page()     │  │ close()          │             │
│   │ chrome()       │  │ (lazy init)    │  │ (cleanup)        │             │
│   └────────────────┘  └────────────────┘  └──────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────┐  ┌──────────────────────────────┐
│  bot/search/base.py          │  │  bot/apply/base.py           │
│  ┌──────────┐ ┌───────────┐ │  │  ┌───────────┐ ┌──────────┐ │
│  │ RawJob   │ │BaseSearcher│ │  │  │ApplyResult│ │BaseApplier│ │
│  │(dataclass│ │  (ABC)     │ │  │  │(dataclass)│ │  (ABC)   │ │
│  └──────────┘ └───────────┘ │  │  └───────────┘ └──────────┘ │
│        ▲            ▲        │  │       ▲            ▲        │
│        │            │        │  │       │            │        │
│  ┌─────┴────┐ ┌────┴─────┐  │  │ ┌─────┴────┐ ┌────┴─────┐  │
│  │LinkedIn  │ │Indeed     │  │  │ │LinkedIn  │ │Indeed     │  │
│  │Searcher  │ │Searcher   │  │  │ │Applier   │ │Applier    │  │
│  └──────────┘ └──────────┘  │  │ └──────────┘ └──────────┘  │
└──────────────────────────────┘  └──────────────────────────────┘
```

### 2.2 Data Flow

The bot operates as a five-stage pipeline executed in a continuous loop:

```
          ┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌─────────┐
          │ 1.SEARCH │────▶│ 2.SCORE │────▶│3.GENERATE│────▶│ 4.APPLY │────▶│ 5.SAVE  │
          └─────────┘     └─────────┘     └──────────┘     └─────────┘     └─────────┘
               │               │               │                │               │
          Iterator[RawJob] ScoredJob      (resume,cl)      ApplyResult     DB record
               │               │               │                │               │
               ▼               ▼               ▼                ▼               ▼
          emit FOUND      emit FILTERED   emit GENERATING  emit APPLYING   emit APPLIED
                          (if filtered)                                    or ERROR
```

**Detailed flow**:

1. **Search**: Each enabled `BaseSearcher` yields `RawJob` objects one at a time via Playwright browser automation. Searchers iterate over `criteria.job_titles x criteria.locations` combinations.

2. **Score**: `score_job(raw_job, config, db)` applies hard disqualifiers (dedup, blacklist, exclude keywords) then scores 0-100 across four dimensions. Jobs below `min_match_score` are filtered out.

3. **Generate**: `_generate_docs()` calls Phase 2's `generate_documents()` to produce a tailored resume PDF and cover letter via Claude Code. On failure, falls back to static templates.

4. **Apply**: `_apply_to_job()` uses `detect_ats()` to resolve the platform, looks up the applier class in `APPLIERS` registry, instantiates it with the shared `page`, and calls `applier.apply()`.

5. **Save**: `_save_application()` persists the application record to SQLite with status, paths, score, and error details.

Between each application, the bot sleeps for `delay_between_applications_seconds`. After all searchers complete a cycle, it sleeps for `search_interval_seconds` before the next cycle.

### 2.3 Layer Architecture

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| API | `app.py` | HTTP/WebSocket endpoints for bot start/stop/pause/status |
| Orchestration | `bot/bot.py` | Main loop, pipeline coordination, event emission |
| State | `bot/state.py` | Thread-safe bot status, counters, review gate |
| Search | `bot/search/*.py` | Platform-specific job discovery via Playwright |
| Filter | `core/filter.py` | Scoring engine, ATS detection, hard disqualifiers |
| AI | `core/ai_engine.py` | Document generation (Phase 2, consumed by bot) |
| Apply | `bot/apply/*.py` | Platform-specific form automation via Playwright |
| Browser | `bot/browser.py` | Persistent Playwright context management |
| Data | `db/database.py` | SQLite persistence for applications and feed events |
| Config | `config/settings.py` | Pydantic models for all configuration |

---

## 3. Component Catalog

### 3.1 bot/bot.py — Main Loop Orchestrator

**Purpose**: Coordinates the search-score-generate-apply-save pipeline in a continuous loop.

**Key Elements**:
- `SEARCHERS` dict: maps platform name to searcher class (`{"linkedin": LinkedInSearcher, "indeed": IndeedSearcher}`)
- `APPLIERS` dict: maps platform name to applier class (6 entries: linkedin, indeed, greenhouse, lever, workday, ashby)
- `run_bot()`: main entry point, runs in a daemon thread
- `_wait_while_paused()`: blocks while `state.status == "paused"`
- `_interruptible_sleep()`: sleeps in 1-second increments, checking `stop_flag`
- `_wait_for_review()`: blocks until user makes review decision
- `_generate_docs()`: wraps Phase 2 AI engine with fallback
- `_apply_to_job()`: resolves platform via `detect_ats()`, dispatches to applier
- `_save_application()`: persists result to database
- `_save_job_description()`: saves job description as HTML for interview prep

### 3.2 bot/browser.py — BrowserManager

**Purpose**: Manages a Playwright persistent browser context that preserves login cookies.

**Key Elements**:
- `_find_system_chrome()`: locates system Chrome on Windows/macOS/Linux
- `BrowserManager.__init__(config)`: configures headless mode from `apply_mode`, creates profile dir
- `BrowserManager.get_page()`: lazy-initializes Playwright, launches persistent context, returns `Page`
- `BrowserManager.close()`: cleans up context and Playwright instance

**Configuration**:
- Profile directory: `~/.autoapply/browser_profile/`
- Headless: True except when `apply_mode == "watch"`
- Viewport: 1280x800
- Anti-detection args: `--disable-blink-features=AutomationControlled`, `--enable-automation` removed

### 3.3 bot/search/base.py — Search Abstractions

**Purpose**: Defines the `RawJob` data model and `BaseSearcher` abstract interface.

### 3.4 bot/search/linkedin.py — LinkedInSearcher

**Purpose**: Searches LinkedIn jobs via browser automation.

**Flow**: Navigate to search URL with query params --> extract job cards --> click each card to load detail panel --> extract title, company, location, salary, description, job ID --> yield `RawJob` --> follow pagination.

**Login detection**: If URL contains "login" or "authwall", logs warning and returns (no crash).

### 3.5 bot/search/indeed.py — IndeedSearcher

**Purpose**: Searches Indeed jobs via browser automation.

**Flow**: Navigate to search URL with query params --> extract job cards --> click title link to load details --> extract fields --> yield `RawJob` --> follow pagination.

### 3.6 core/filter.py — Scoring & ATS Detection

**Purpose**: Scores jobs 0-100 and detects ATS platforms from URLs.

**Scoring breakdown**:
| Dimension | Max Points | Logic |
|-----------|-----------|-------|
| Title match | 35 | Exact substring = 35; 50%+ word overlap = 20 |
| Salary match | 20 | Meets minimum = 20; unknown = 10; no requirement = 20 |
| Location match | 20 | Exact location match = 20; same country = 10; remote match = 20 |
| Keyword match | 25 | +5 per include keyword found, capped at 25 |

**Hard disqualifiers** (score = 0, `pass_filter = False`):
- Job `external_id` already in database (deduplication)
- Company in `config.company_blacklist`
- Exclude keyword found in title or description

**ATS Fingerprints** (9 entries):
| URL Substring | Platform |
|---------------|----------|
| `greenhouse.io` | greenhouse |
| `lever.co` | lever |
| `myworkdayjobs.com` | workday |
| `ashbyhq.com` | ashby |
| `taleo.net` | taleo |
| `icims.com` | icims |
| `linkedin.com/jobs` | linkedin |
| `linkedin.com` | linkedin |
| `indeed.com` | indeed |

### 3.7 bot/apply/base.py — Applier Abstractions

**Purpose**: Defines `ApplyResult` data model, `BaseApplier` ABC with retry wrapper, and shared safe interaction helpers.

**Class Constants** (overridable per subclass):
- `ELEMENT_TIMEOUT: int = 5000` — default timeout (ms) for waiting on elements
- `NAV_TIMEOUT: int = 30000` — default timeout (ms) for page navigation

**Module Constants**:
- `MAX_RETRIES = 2` — maximum retry attempts on transient failures
- `RETRY_DELAYS = [3, 8]` — seconds to wait before each retry

**Retry Wrapper** (`apply()` method):
The base class `apply()` method wraps each subclass's `_do_apply()` with automatic retry logic:
1. Calls `_do_apply()` up to `MAX_RETRIES + 1` times (3 total)
2. Returns immediately on success, CAPTCHA detection, or manual_required
3. Returns immediately on form validation errors (non-retryable)
4. On transient failures (network errors, timeouts, generic exceptions), waits `RETRY_DELAYS[i]` seconds then retries
5. Sets `ApplyResult.attempts` to the total number of attempts made
6. Logs each retry at INFO level with platform name, attempt number, and delay

**Abstract Method**:
- `_do_apply(job, resume_pdf_path, cover_letter_text, profile) -> ApplyResult`: core application logic, implemented by each platform-specific applier

**Safe Interaction Helpers**:
- `_safe_goto(url, **kwargs)`: navigates with `wait_until="domcontentloaded"` and `timeout=NAV_TIMEOUT`; kwargs override defaults
- `_wait_and_query(selector, timeout)`: waits for element visibility within timeout (default `ELEMENT_TIMEOUT`), returns element or None; never raises
- `_safe_fill(selector, value, clear_first=True)`: finds element, clears if different value present, fills with `_human_type()`; returns True if filled
- `_safe_upload(resume_path, selectors)`: tries multiple file input selectors in order, uploads via first match; logs warnings on failure; returns True if uploaded
- `_safe_click(selector, timeout)`: waits for element via `_wait_and_query()`, clicks if visible; returns True if clicked

**Human-Like Interaction Utilities**:
- `_human_type(locator, text)`: types character-by-character with 30-80ms random delay
- `_random_pause(min_s, max_s)`: sleeps 0.5-2.0s (default) between actions
- `_detect_captcha()`: checks for reCAPTCHA iframes, `#captcha`, `.g-recaptcha`, `[data-sitekey]`

### 3.8 bot/apply/linkedin.py — LinkedInApplier

**Purpose**: Automates LinkedIn Easy Apply multi-step modal.

**Flow**: Navigate to job URL --> detect CAPTCHA --> click "Easy Apply" button --> loop up to 10 steps: fill form fields, upload resume, fill cover letter, check for Submit/Next/Review buttons --> verify confirmation.

**Fallback**: If Easy Apply button not found, returns `manual_required=True`.

### 3.9 bot/apply/indeed.py — IndeedApplier

**Purpose**: Automates Indeed Quick Apply flow.

**Flow**: Navigate to job URL --> detect CAPTCHA --> click "Apply now" button --> loop up to 8 steps: fill name/email/phone, upload resume, check for Submit/Continue --> return result.

**Fallback**: If redirected to external ATS, returns `manual_required=True`.

### 3.10 bot/state.py — BotState

**Purpose**: Thread-safe state container for the bot, shared between the Flask API thread and the bot daemon thread.

**Fields** (all guarded by `threading.Lock`):
- `_status`: `"stopped"` | `"running"` | `"paused"`
- `_stop_flag`: bool
- `_jobs_found_today`: int
- `_applied_today`: int
- `_errors_today`: int
- `_start_time`: datetime | None
- `_awaiting_review`: bool
- `_review_event`: `threading.Event` (blocks bot thread during review)
- `_review_decision`: `"approve"` | `"skip"` | `"edit"` | None
- `_review_edits`: str | None (edited cover letter)
- `_awaiting_login`: bool (FR-089 login gate)
- `_login_event`: `threading.Event` (blocks bot thread during login gate)
- `_login_decision`: `"done"` | `"skip"` | None
- `_login_context`: dict (domain, portal_type, url) | None

### 3.11 core/portal_auth.py — PortalAuthManager

**Purpose**: Manages portal credentials, login detection, and auto-login for ATS portals (FR-086–FR-089).

**Key classes**:
- `PortalAuthManager(db)` — credential vault, login detection, auto-login orchestration

**Domain extraction** (`extract_domain(url)`):
- Shared-domain ATS (Greenhouse, Lever, Ashby): returns `hostname/company`
- Standard sites (Workday subdomains, custom career sites): returns `hostname`
- Case-insensitive (all lowercased)

**Credential vault** (`store_credential`, `get_credential`, `delete_credential`, `list_credentials`):
- OS keyring preferred (via `config.settings._check_keyring()`), DB fallback
- Passwords stored in keyring with prefix `portal_` under service `autoapply`
- UPSERT on conflict (same domain updates credential)
- Login attempt tracking via `db.record_login_attempt()`

**Login detection** (`detect_login_wall(page)`):
- Tier 1: URL path segment matching (login, signin, auth, sso, etc.)
- Tier 2: DOM selector matching (password inputs, login forms, Workday selectors)
- Returns False on any exception (never raises)

**Auto-login** (`try_auto_login(page, domain, portal_type)`):
- Generic: finds email/username + password fields, fills with human-like typing, clicks submit
- Workday-specific: uses `data-automation-id` selectors, falls back to generic
- Records attempt outcome to DB

### 3.12 routes/portal_auth.py — Portal Auth API Routes

**Purpose**: REST API for credential vault CRUD and login gate decisions (FR-086, FR-089).

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portal-credentials` | List all credentials (masked) |
| POST | `/api/portal-credentials` | Store/update a credential |
| DELETE | `/api/portal-credentials/<domain>` | Delete a credential |
| POST | `/api/portal-auth/login-decision` | Set login gate decision (done/skip) |
| GET | `/api/portal-auth/login-status` | Get current login gate status |
| POST | `/api/portal-auth/extract-domain` | Extract domain from URL (utility) |

---

## 4. Interface Contracts

### 4.1 bot.bot.run_bot(state, config, db, emit_func)

**Purpose**: Main bot loop — search, filter, generate, apply, save.
**Category**: saga (long-running, side-effectful)

**Signature**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| state | `BotState` | yes | Thread-safe bot state (status, counters, stop flag) |
| config | `AppConfig` | yes | Application configuration |
| db | `Database` | yes | Database for saving applications and dedup checks |
| emit_func | `Callable[[str, dict], None] \| None` | no | SocketIO event emitter. Signature: `emit_func(event_name, data_dict)` |

**Output**: `None` (runs until `state.stop_flag` is set).

**Side Effects**: Launches browser, navigates web pages, submits applications, writes to database, emits SocketIO events, saves HTML/PDF/TXT files to disk.

**Thread Safety**: Designed to run in a single daemon thread. Communicates with main thread via `BotState`.

**Error Handling**: Top-level try/except ensures browser cleanup in `finally`. Individual job failures are caught, logged, and emitted as ERROR events without stopping the loop.

---

### 4.2 core.filter.score_job(raw_job, config, db)

**Purpose**: Score a job 0-100 and determine pass/fail.
**Category**: query (pure computation + one DB read for dedup)

**Signature**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| raw_job | `RawJob` | yes | -- | Unscored job listing |
| config | `AppConfig` | yes | -- | Configuration with search criteria, blacklist, bot settings |
| db | `Database \| None` | no | `None` | Database for deduplication check |

**Output**:
| Field | Type | Description |
|-------|------|-------------|
| return | `ScoredJob` | Contains `id` (UUID), `raw`, `score` (0-100), `pass_filter` (bool), `skip_reason` (str|None) |

**Errors**: None raised -- all computation is fault-tolerant.

**Thread Safety**: Safe -- no shared mutable state.

---

### 4.3 core.filter.detect_ats(url)

**Purpose**: Detect ATS platform from a job URL.
**Category**: query (pure function)

**Signature**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| url | `str` | yes | The apply URL to check |

**Output**:
| Field | Type | Description |
|-------|------|-------------|
| return | `str \| None` | ATS name string (e.g., "greenhouse") or None if unrecognized |

---

### 4.4 BrowserManager.get_page()

**Purpose**: Get or create a Playwright Page in a persistent context.
**Category**: command (launches browser if needed)

**Signature**: No parameters.

**Output**:
| Field | Type | Description |
|-------|------|-------------|
| return | `Page` | Playwright Page instance |

**Errors**:
| Condition | Error Type | Detail |
|-----------|-----------|--------|
| Playwright not installed | `RuntimeError` | "Playwright is required but not installed" |
| Chromium not installed | `RuntimeError` | "Playwright Chromium not installed" |

**Side Effects**: On first call, starts Playwright, launches Chromium persistent context, creates new page. Subsequent calls return the existing page if not closed.

---

### 4.5 BrowserManager.close()

**Purpose**: Close browser context and cleanup Playwright.
**Category**: command

**Signature**: No parameters.
**Output**: None.
**Errors**: None raised -- all exceptions caught internally.

---

### 4.6 BaseSearcher.search(criteria, page)

**Purpose**: Yield job listings matching search criteria.
**Category**: generator (lazy evaluation)

**Signature**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| criteria | `SearchCriteria` | yes | Search parameters (job_titles, locations, filters) |
| page | `Page \| None` | no | Playwright Page for browser-based searching |

**Output**:
| Field | Type | Description |
|-------|------|-------------|
| yield | `Iterator[RawJob]` | Job listings discovered one at a time |

---

### 4.7 BaseApplier.apply(job, resume_pdf_path, cover_letter_text, profile)

**Purpose**: Submit a job application on a specific platform with automatic retry on transient failures.
**Category**: command (web automation side effect)

**Signature**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job | `ScoredJob` | yes | The scored job to apply to |
| resume_pdf_path | `Path \| None` | yes | Path to the tailored resume PDF |
| cover_letter_text | `str` | yes | Cover letter text to paste |
| profile | `UserProfile` | yes | User profile with personal info |

**Output**:
| Field | Type | Description |
|-------|------|-------------|
| return | `ApplyResult` | Success/failure with error details and attempt count |

**Retry Behavior**:
- Wraps subclass `_do_apply()` with retry logic (up to `MAX_RETRIES + 1` total attempts)
- Retries on: network errors, timeouts, generic exceptions
- Does NOT retry on: success, CAPTCHA detected, manual_required, form validation errors
- Backoff: `RETRY_DELAYS[i]` seconds between retries (default [3, 8])
- `ApplyResult.attempts` reflects total attempts made

**Subclass Contract**:
Subclasses implement `_do_apply()` (same signature as `apply()`) with platform-specific form automation. They should use the base class helpers (`_safe_goto`, `_wait_and_query`, `_safe_fill`, `_safe_upload`, `_safe_click`) for reliable element interaction.

---

### 4.8 BotState Methods

| Method | Category | Description |
|--------|----------|-------------|
| `start()` | command | Sets status="running", clears stop_flag, records start_time |
| `stop()` | command | Sets status="stopped", sets stop_flag, unblocks review gate |
| `pause()` | command | Sets status="paused" |
| `resume()` | command | Sets status="running" |
| `increment_found()` | command | Atomically increments jobs_found_today |
| `increment_applied()` | command | Atomically increments applied_today |
| `increment_errors()` | command | Atomically increments errors_today |
| `reset_daily()` | command | Resets all daily counters to 0 |
| `begin_review()` | command | Clears review event, sets awaiting_review=True |
| `set_review_decision(decision, edits)` | command | Sets decision, unblocks bot thread |
| `wait_for_review()` | blocking | Blocks until decision set or stop requested; returns `(decision, edited_cl)` |
| `begin_login_gate(domain, portal_type, url)` | command | Clears login event, sets awaiting_login=True, stores login_context (FR-089) |
| `set_login_decision(decision)` | command | Sets login decision ("done"/"skip"), unblocks bot thread (FR-089) |
| `wait_for_login()` | blocking | Blocks until login decision set or stop requested; returns decision string (FR-089) |
| `get_status_dict()` | query | Returns dict snapshot of all state for API response (includes awaiting_login, login_context) |

---

## 5. Data Model

### 5.1 RawJob (dataclass)

**Location**: `bot/search/base.py`

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| title | `str` | no | Job title |
| company | `str` | no | Company name |
| location | `str` | no | Job location |
| salary | `str \| None` | yes | Salary text if shown |
| description | `str` | no | Full job description text |
| apply_url | `str` | no | URL to apply |
| platform | `str` | no | Source platform ("linkedin" \| "indeed") |
| external_id | `str` | no | Platform-specific ID for deduplication (e.g., "linkedin-12345") |
| posted_at | `str \| None` | yes | When the job was posted |

### 5.2 ScoredJob (dataclass)

**Location**: `core/filter.py`

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | `str` | no | UUID for filename generation |
| raw | `RawJob` | no | Original job listing |
| score | `int` | no | Match score 0-100 |
| pass_filter | `bool` | no | True if score >= min_match_score and no disqualifiers |
| skip_reason | `str \| None` | yes | Reason for filtering (None if passed) |

### 5.3 ApplyResult (dataclass)

**Location**: `bot/apply/base.py`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| success | `bool` | -- | Whether application was submitted |
| error_message | `str \| None` | `None` | Error detail on failure |
| captcha_detected | `bool` | `False` | Whether a CAPTCHA blocked the application |
| manual_required | `bool` | `False` | Whether the user must apply manually (no automation path) |
| login_required | `bool` | `False` | Whether a login wall was detected (FR-089) |
| login_domain | `str \| None` | `None` | Domain where login is needed (FR-089) |
| login_portal_type | `str \| None` | `None` | ATS type of login portal (FR-089) |
| attempts | `int` | `1` | Number of attempts made (1 = first try, 2+ = retried) |

---

## 6. State Machine

### 6.1 Bot States

```
                    POST /api/bot/start
                           │
                           ▼
    ┌──────────┐    ┌──────────────┐    ┌──────────────────┐
    │ STOPPED  │───▶│   RUNNING    │───▶│ AWAITING_REVIEW  │
    │          │    │              │◀───│ (review/watch     │
    └──────────┘    └──────┬───────┘    │  mode only)      │
         ▲                 │            └──────────────────┘
         │                 │                    │
         │            pause│               approve/skip/
         │                 ▼               edit/manual
         │          ┌──────────────┐            │
         │          │   PAUSED     │            │
         │          └──────┬───────┘            │
         │                 │ resume              │
         │                 ▼                     │
         │          ┌──────────────┐             │
         └──────────│   RUNNING    │◀────────────┘
            stop    └──────────────┘
```

### 6.2 State Transitions

| From | Trigger | To | Side Effects |
|------|---------|-----|-------------|
| stopped | `state.start()` | running | Records start_time, clears stop_flag |
| running | `state.pause()` | paused | Bot loop enters `_wait_while_paused()` |
| paused | `state.resume()` | running | Bot loop unblocks |
| running | `state.begin_review()` | awaiting_review | Bot thread blocks on `_review_event` |
| awaiting_review | `state.set_review_decision()` | running | Bot thread unblocks, processes decision |
| running | `state.begin_login_gate()` | awaiting_login | Bot thread blocks on `_login_event` (FR-089) |
| awaiting_login | `state.set_login_decision()` | running | Bot thread unblocks, retries or skips (FR-089) |
| any | `state.stop()` | stopped | Sets stop_flag, unblocks review + login gates, clears start_time |

### 6.3 Thread Interaction Model

```
┌────────────────────────────┐          ┌────────────────────────────┐
│      Flask API Thread      │          │      Bot Daemon Thread     │
│                            │          │                            │
│  POST /bot/start ──────────┼──start──▶│  run_bot() loop            │
│  POST /bot/stop  ──────────┼──stop───▶│  checks stop_flag          │
│  POST /bot/pause ──────────┼──pause──▶│  _wait_while_paused()      │
│  POST /bot/resume ─────────┼─resume──▶│  unblocks from pause       │
│  POST /bot/review ─────────┼─decision▶│  wait_for_review() returns │
│  POST /portal-auth/login──┼─decision▶│  wait_for_login() returns  │
│  GET  /bot/status ◀────────┼──read────│  get_status_dict()         │
│                            │          │                            │
│  Shared: BotState (lock)   │          │  Shared: BotState (lock)   │
└────────────────────────────┘          └────────────────────────────┘
```

All state access goes through `BotState` which uses `threading.Lock` for atomicity. The review gate uses `threading.Event` to block the bot thread without busy-waiting.

---

## 7. Error Handling Strategy

| Scenario | Handling | User Impact |
|----------|----------|-------------|
| Playwright not installed | `RuntimeError` from `get_page()` | Bot fails to start; error in API response |
| Chromium not installed | `RuntimeError` from `get_page()` | Bot fails to start; error in API response |
| LinkedIn requires login | Searcher logs warning, yields no jobs | No jobs from LinkedIn; user sees empty feed |
| Indeed blocks/rate-limits | Searcher logs warning, yields no jobs | No jobs from Indeed; continues to next platform |
| Job card extraction fails | Individual card skipped (`logger.debug`) | One fewer job in results; bot continues |
| Dedup check (already applied) | `pass_filter=False`, skip_reason set | Job silently filtered; FILTERED event emitted |
| Score below threshold | `pass_filter=False`, skip_reason set | Job filtered; FILTERED event emitted |
| Claude Code generation fails | Falls back to static templates | Lower quality docs but application proceeds |
| Easy Apply button not found | `ApplyResult(manual_required=True)` | Saved as manual_required; ERROR event emitted |
| External ATS redirect | `ApplyResult(manual_required=True)` | Saved as manual_required; ERROR event emitted |
| CAPTCHA detected | `ApplyResult(captcha_detected=True)` | CAPTCHA event emitted; application skipped |
| No applier for platform | `ApplyResult(manual_required=True)` | Error event; application not attempted |
| Application form step limit | `ApplyResult(success=False)` | ERROR event; saved with error message |
| DB save fails | Caught, logged (`logger.error`) | Application not recorded; bot continues |
| Entire search/apply cycle error | Caught at searcher level, error emitted | Bot continues to next searcher |
| Bot crash (top-level exception) | Caught, browser cleaned up in `finally` | ERROR event emitted; bot loop exits |

**Design principle**: Individual job failures never crash the loop. The only way to stop the bot is via `stop_flag` or an unrecoverable infrastructure failure (e.g., browser process dies).

---

## 8. Architecture Decision Records

### ADR-012: Persistent Browser Context via Playwright

**Status**: accepted
**Context**: The bot must preserve login sessions (LinkedIn, Indeed) across restarts. Options: (a) re-authenticate every run, (b) save/restore cookies manually, (c) Playwright persistent context.
**Decision**: Use `playwright.chromium.launch_persistent_context()` with a user data directory at `~/.autoapply/browser_profile/`.
**Rationale**: Persistent contexts store all browser state (cookies, localStorage, IndexedDB) exactly as a real browser would. No manual cookie management needed. User logs in once via headed mode, and all subsequent runs (headless or headed) reuse the session.
**Consequences**: Profile directory grows over time. Concurrent browser instances on the same profile are not supported. Playwright requires its own Chromium (cannot share with Electron -- see ADR-006 revision).

### ADR-013: Human-Like Interaction Timing

**Status**: accepted
**Context**: Job platforms detect and block bots that interact at inhuman speeds. Need to avoid triggering anti-automation defenses.
**Decision**: All appliers inherit from `BaseApplier` which provides `_human_type()` (30-80ms per character) and `_random_pause()` (0.5-2.0s between actions). Additionally, `delay_between_applications_seconds` (default 45s) spaces out applications.
**Rationale**: Random delays within realistic human ranges make automation less distinguishable from manual usage. The per-character typing delay simulates natural typing speed. The between-application delay prevents burst patterns.
**Consequences**: Automation is slower than it could be. A single application takes 10-30 seconds of form-filling time. Configurable delays allow users to tune the tradeoff.

### ADR-014: Playwright as Browser Automation Framework

**Status**: accepted
**Context**: Need browser automation for searching and applying to jobs. Options: Selenium, Puppeteer (via pyppeteer), Playwright.
**Decision**: Use Playwright for Python (`playwright` package).
**Rationale**: Playwright provides superior auto-waiting, built-in persistent contexts, cross-platform support, better selector engine, and `--disable-blink-features=AutomationControlled` support. Its sync API integrates naturally with the bot's synchronous loop. The `ignore_default_args=["--enable-automation"]` feature helps avoid detection.
**Consequences**: Requires separate Chromium installation (`playwright install chromium`). Binary size ~150MB. System Chrome is preferred when available (`_find_system_chrome()`).

### ADR-015: Applier Registry Pattern

**Status**: accepted
**Context**: Need to dispatch application automation to the correct handler based on detected platform. Must support adding new platforms without modifying the dispatch logic.
**Decision**: Two module-level dictionaries (`SEARCHERS`, `APPLIERS`) map platform name strings to class objects. `detect_ats()` resolves the platform from the URL, and the class is looked up and instantiated at dispatch time.
**Rationale**: Simple, explicit, no dynamic import magic. New platforms are added by (1) creating a new applier class extending `BaseApplier`, (2) adding one entry to `APPLIERS` dict, (3) optionally adding URL fingerprint to `ATS_FINGERPRINTS`. The pattern follows the Strategy pattern with a registry.
**Consequences**: All applier imports happen at module load time. Adding a platform requires editing `bot.py` imports and the `APPLIERS` dict. This is acceptable given the low number of platforms (<20).

---

## 9. Design Traceability Matrix

| Requirement | Type | Design Component | Interface / Section | ADR | Source Files |
|-------------|------|-----------------|---------------------|-----|-------------|
| FR-041 | FR | Search abstractions | BaseSearcher.search(), RawJob | -- | bot/search/base.py |
| FR-042 | FR | LinkedIn search | LinkedInSearcher.search() | ADR-014 | bot/search/linkedin.py |
| FR-043 | FR | Indeed search | IndeedSearcher.search() | ADR-014 | bot/search/indeed.py |
| FR-044 | FR | Scoring engine | score_job() | -- | core/filter.py |
| FR-045 | FR | ATS detection | detect_ats(), ATS_FINGERPRINTS | ADR-015 | core/filter.py |
| FR-046 | FR | Apply result model | ApplyResult dataclass | -- | bot/apply/base.py |
| FR-047 | FR | Browser management | BrowserManager.get_page(), close() | ADR-012 | bot/browser.py |
| FR-048 | FR | LinkedIn apply | LinkedInApplier.apply() | ADR-013, ADR-014 | bot/apply/linkedin.py |
| FR-049 | FR | Indeed apply | IndeedApplier.apply() | ADR-013, ADR-014 | bot/apply/indeed.py |
| FR-050 | FR | Main bot loop | run_bot() | ADR-015 | bot/bot.py |
| FR-051 | FR | Live feed events | emit() in run_bot() | -- | bot/bot.py |
| FR-052 | FR | Thread integration | BotState + daemon thread | -- | bot/state.py, bot/bot.py |
| FR-083 | FR | Retry wrapper | BaseApplier.apply() retry logic | -- | bot/apply/base.py |
| FR-084 | FR | Safe navigation/waiting | _safe_goto(), _wait_and_query() | -- | bot/apply/base.py |
| FR-085 | FR | Safe form interaction | _safe_fill(), _safe_upload(), _safe_click() | -- | bot/apply/base.py |
| NFR-028 | NFR | Timeout configuration | ELEMENT_TIMEOUT, NAV_TIMEOUT overrides | -- | bot/apply/base.py, bot/apply/workday.py |
| NFR-023 | NFR | Human-like timing | _human_type(), _random_pause() | ADR-013 | bot/apply/base.py |
| NFR-024 | NFR | Session persistence | Persistent context | ADR-012 | bot/browser.py |
| NFR-025 | NFR | Rate limiting | delay_between_applications_seconds, search_interval_seconds | -- | bot/bot.py |
| NFR-026 | NFR | Graceful degradation | Try/except around each job | -- | bot/bot.py |
| NFR-027 | NFR | Daily limit | applied_today check in loop | -- | bot/bot.py, bot/state.py |
| FR-086 | FR | Portal credential vault | PortalAuthManager.store/get/delete/list_credential() | -- | core/portal_auth.py, routes/portal_auth.py, db/database.py |
| FR-087 | FR | Login detection | PortalAuthManager.detect_login_wall() | -- | core/portal_auth.py |
| FR-088 | FR | Auto-login | PortalAuthManager.try_auto_login(), _login_generic(), _login_workday() | -- | core/portal_auth.py |
| FR-089 | FR | Browser handoff login gate | BotState.begin_login_gate(), wait_for_login(), set_login_decision() | -- | bot/state.py, bot/bot.py, routes/portal_auth.py |

---

## 10. Implementation Plan

This is a retroactive document. All components listed below were implemented and shipped in v1.3.0.

| Order | Task ID | Description | Depends On | Size | FR Coverage |
|-------|---------|-------------|------------|------|-------------|
| 1 | IMPL-016 | Create `bot/search/base.py` with `RawJob` dataclass and `BaseSearcher` ABC | -- | S | FR-041 |
| 2 | IMPL-017 | Create `bot/browser.py` with `BrowserManager`, `_find_system_chrome()` | -- | M | FR-047 |
| 3 | IMPL-018 | Create `bot/search/linkedin.py` with `LinkedInSearcher` | IMPL-016, IMPL-017 | L | FR-042 |
| 4 | IMPL-019 | Create `bot/search/indeed.py` with `IndeedSearcher` | IMPL-016, IMPL-017 | L | FR-043 |
| 5 | IMPL-020 | Create `core/filter.py` with `ScoredJob`, `score_job()`, `detect_ats()`, `ATS_FINGERPRINTS` | IMPL-016 | M | FR-044, FR-045 |
| 6 | IMPL-021 | Create `bot/apply/base.py` with `ApplyResult`, `BaseApplier` ABC | IMPL-017 | S | FR-046 |
| 7 | IMPL-022 | Create `bot/apply/linkedin.py` with `LinkedInApplier` | IMPL-021 | L | FR-048 |
| 8 | IMPL-023 | Create `bot/apply/indeed.py` with `IndeedApplier` | IMPL-021 | L | FR-049 |
| 9 | IMPL-024 | Create `bot/state.py` with `BotState` (thread-safe state + review gate) | -- | M | FR-052 |
| 10 | IMPL-025 | Create `bot/bot.py` with `run_bot()`, registries, pipeline, emit logic | IMPL-016 through IMPL-024 | L | FR-050, FR-051 |
| 11 | IMPL-026 | Wire bot thread into `app.py` (start/stop/pause/status endpoints) | IMPL-025 | M | FR-052 |
