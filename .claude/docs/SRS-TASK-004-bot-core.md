# Software Requirements Specification

**Document ID**: SRS-TASK-004-bot-core
**Version**: 1.0
**Date**: 2026-03-09
**Status**: approved
**Author**: Claude (Requirements Analyst)
**PRD Reference**: PRD Section 9.2, 9.3, 9.5, 10, 11

---

## 1. Purpose and Scope

### 1.1 Purpose
Specifies requirements for AutoApply Phase 3 (Bot Core): job searching, filtering/scoring, browser automation, application submission, and the main bot loop with live feed events.

### 1.2 Scope
The system SHALL provide: job search on LinkedIn and Indeed via Playwright, job scoring/filtering engine, browser session management, LinkedIn Easy Apply and Indeed Quick Apply automation, main bot loop with pause/resume/stop, SocketIO live feed events, and background thread integration with Flask.

The system SHALL NOT provide: Greenhouse/Lever/Workday appliers (Phase 6), CAPTCHA solving (Phase 6), scheduling/cron (Phase 5), error recovery/retry (Phase 5).

### 1.3 Definitions
| Term | Definition |
|------|-----------|
| RawJob | Unscored job listing scraped from a platform |
| ScoredJob | RawJob after scoring — includes match score and pass/fail verdict |
| Easy Apply | LinkedIn's in-platform application flow (no external redirect) |
| Quick Apply | Indeed's in-platform application flow |
| ATS | Applicant Tracking System — external portal (Greenhouse, Lever, etc.) |
| Feed event | Real-time SocketIO message about bot activity |
| Persistent context | Playwright browser profile preserving login cookies between sessions |

---

## 2. Functional Requirements

### FR-041: Job Search Base Class

**Description**: The system SHALL define a `BaseSearcher` abstract class with a `search(criteria)` method that yields `RawJob` objects.
**Priority**: P0
**Dependencies**: None

**Acceptance Criteria**:
- **AC-041-1**: `RawJob` dataclass has fields: title, company, location, salary (nullable), description, apply_url, platform, external_id, posted_at (nullable).
- **AC-041-2**: `BaseSearcher` is abstract with `search()` method returning `Iterator[RawJob]`.

---

### FR-042: LinkedIn Job Search

**Description**: The system SHALL search LinkedIn jobs using Playwright, navigating to LinkedIn's job search page with criteria as query parameters, extracting job cards with details.
**Priority**: P0
**Dependencies**: FR-041, FR-047

**Acceptance Criteria**:
- **AC-042-1**: Given valid search criteria, When `LinkedInSearcher.search()` is called, Then it navigates to LinkedIn jobs search with title and location as query params.
- **AC-042-2**: Given job cards are visible, When extracting jobs, Then each yielded `RawJob` has all required fields populated from the page.
- **AC-042-3**: Given pagination exists, When searching, Then it follows pagination until `max_results_per_search` is reached or no more pages.
- **AC-042-N1**: Given LinkedIn requires login, When not authenticated, Then the searcher logs a warning and yields no jobs (does not crash).

---

### FR-043: Indeed Job Search

**Description**: The system SHALL search Indeed jobs using Playwright, navigating to Indeed's job search page with criteria as query parameters.
**Priority**: P0
**Dependencies**: FR-041, FR-047

**Acceptance Criteria**:
- **AC-043-1**: Given valid search criteria, When `IndeedSearcher.search()` is called, Then it navigates to Indeed jobs search with title and location as query params.
- **AC-043-2**: Given job listings are visible, When extracting jobs, Then each yielded `RawJob` has all required fields populated.
- **AC-043-N1**: Given Indeed blocks or rate-limits, When accessing the page, Then the searcher logs a warning and yields no jobs.

---

### FR-044: Job Filter & Scoring Engine

**Description**: The system SHALL score each `RawJob` on a 0-100 scale using title match (0-35), salary match (0-20), location match (0-20), and keyword match (0-25), with hard disqualifiers.
**Priority**: P0
**Dependencies**: FR-041

**Acceptance Criteria**:
- **AC-044-1**: Given a job with exact title match, When scored, Then title_match contributes up to 35 points.
- **AC-044-2**: Given a job with salary meeting minimum, When scored, Then salary_match contributes 20 points; unknown salary contributes 10.
- **AC-044-3**: Given a job matching location or remote preference, When scored, Then location_match contributes up to 20 points.
- **AC-044-4**: Given a job containing include keywords, When scored, Then keyword_match contributes +5 per keyword found (max 25).
- **AC-044-5**: Given a job containing an exclude keyword in title or description, When scored, Then score is 0 and `pass_filter` is False with `skip_reason`.
- **AC-044-6**: Given a job from a blacklisted company, When scored, Then score is 0 and `pass_filter` is False.
- **AC-044-7**: Given a job whose `external_id` already exists in the database, When scored, Then score is 0 and `pass_filter` is False (deduplication).
- **AC-044-8**: Given a scored job with score >= `config.bot.min_match_score`, Then `pass_filter` is True.
- **AC-044-N1**: Given a job with score below threshold, Then `pass_filter` is False with `skip_reason` = "Score below threshold".

---

### FR-045: ATS Detection

**Description**: The system SHALL detect the ATS platform from a job's apply URL using domain fingerprints.
**Priority**: P1
**Dependencies**: None

**Acceptance Criteria**:
- **AC-045-1**: Given a URL containing "linkedin.com", When `detect_ats()` is called, Then it returns "linkedin".
- **AC-045-2**: Given a URL containing "indeed.com", Then it returns "indeed".
- **AC-045-3**: Given a URL containing "greenhouse.io", Then it returns "greenhouse".
- **AC-045-4**: Given an unrecognized URL, Then it returns None.

---

### FR-046: Apply Result Model

**Description**: The system SHALL define an `ApplyResult` dataclass with success, error_message, captcha_detected, manual_required, and attempts fields.
**Priority**: P0
**Dependencies**: None

**Acceptance Criteria**:
- **AC-046-1**: `ApplyResult` has fields: success (bool), error_message (str|None), captcha_detected (bool, default False), manual_required (bool, default False), attempts (int, default 1).
- **AC-046-2**: The `attempts` field records how many tries were made before the final result.

---

### FR-047: Browser Manager

**Description**: The system SHALL manage a Playwright persistent browser context that preserves login sessions between bot runs.
**Priority**: P0
**Dependencies**: None

**Acceptance Criteria**:
- **AC-047-1**: Given `BrowserManager` is initialized, When `get_page()` is called, Then it returns a Playwright Page in a persistent context using `~/.autoapply/browser_profile/`.
- **AC-047-2**: Given watch_mode is False, When browser is launched, Then it runs in headless mode.
- **AC-047-3**: Given watch_mode is True, When browser is launched, Then it runs in headed mode (visible).
- **AC-047-4**: Given `close()` is called, Then the browser context and playwright instance are cleaned up.
- **AC-047-N1**: Given Playwright Chromium is not installed, When initializing, Then a clear error is raised.

---

### FR-048: LinkedIn Easy Apply

**Description**: The system SHALL automate LinkedIn Easy Apply by navigating to the job, clicking "Easy Apply", filling form fields, uploading resume, and submitting.
**Priority**: P0
**Dependencies**: FR-046, FR-047

**Acceptance Criteria**:
- **AC-048-1**: Given a LinkedIn Easy Apply job URL and a resume PDF, When `LinkedInApplier.apply()` is called, Then it navigates to the URL, clicks Easy Apply, fills fields, uploads resume, and submits.
- **AC-048-2**: Given the application succeeds, Then it returns `ApplyResult(success=True)`.
- **AC-048-3**: Given a CAPTCHA is detected, Then it returns `ApplyResult(success=False, captcha_detected=True)`.
- **AC-048-N1**: Given the Easy Apply button is not found, Then it returns `ApplyResult(success=False, manual_required=True)`.

---

### FR-049: Indeed Quick Apply

**Description**: The system SHALL automate Indeed Quick Apply by navigating to the job, filling the form, uploading resume, and submitting.
**Priority**: P0
**Dependencies**: FR-046, FR-047

**Acceptance Criteria**:
- **AC-049-1**: Given an Indeed Quick Apply job URL and a resume PDF, When `IndeedApplier.apply()` is called, Then it fills the form, uploads resume, and submits.
- **AC-049-2**: Given the application redirects to an external ATS, Then it returns `ApplyResult(success=False, manual_required=True)`.

---

### FR-050: Main Bot Loop

**Description**: The system SHALL run a bot loop that iterates: search → filter → generate docs → apply → save to DB → emit events, respecting stop_flag and daily limits.
**Priority**: P0
**Dependencies**: FR-041 through FR-049, Phase 2 AI engine

**Acceptance Criteria**:
- **AC-050-1**: Given the bot is started, When `run_bot()` executes, Then it searches each enabled platform, filters jobs, generates documents, and applies.
- **AC-050-2**: Given `state.stop_flag` is True, When the loop checks, Then it exits immediately.
- **AC-050-3**: Given `state.status` is "paused", When the loop checks, Then it sleeps until resumed or stopped.
- **AC-050-4**: Given `applied_today >= max_applications_per_day`, When a new job passes filter, Then it is skipped and the bot waits for the next search interval.
- **AC-050-5**: Given a job is applied to, Then `delay_between_applications_seconds` elapses before the next application.
- **AC-050-6**: Given Claude Code fails, Then the bot uses fallback templates and continues.
- **AC-050-7**: Given an application fails, Then the error is saved to DB and the bot continues to the next job.

---

### FR-051: Live Feed SocketIO Events

**Description**: The system SHALL emit real-time SocketIO events for each bot action: FOUND, FILTERED, GENERATING, APPLYING, APPLIED, ERROR, CAPTCHA.
**Priority**: P0
**Dependencies**: FR-050

**Acceptance Criteria**:
- **AC-051-1**: Given a job is found by search, Then a `feed_event` with type "FOUND" is emitted via SocketIO.
- **AC-051-2**: Given a job fails the filter, Then a `feed_event` with type "FILTERED" and skip_reason is emitted.
- **AC-051-3**: Given document generation starts, Then a `feed_event` with type "GENERATING" is emitted.
- **AC-051-4**: Given application submission starts, Then a `feed_event` with type "APPLYING" is emitted.
- **AC-051-5**: Given application succeeds, Then a `feed_event` with type "APPLIED" is emitted.
- **AC-051-6**: Given application fails, Then a `feed_event` with type "ERROR" is emitted.
- **AC-051-7**: Each feed event includes job_title, company, platform, message, and timestamp.

---

### FR-052: Bot Thread Integration

**Description**: The `POST /api/bot/start` endpoint SHALL spawn `run_bot()` in a background thread. `POST /api/bot/stop` SHALL set the stop flag and wait for the thread to exit.
**Priority**: P0
**Dependencies**: FR-050

**Acceptance Criteria**:
- **AC-052-1**: Given bot is stopped, When `POST /api/bot/start` is called, Then a daemon thread running `run_bot()` is started.
- **AC-052-2**: Given bot is already running, When `POST /api/bot/start` is called again, Then it returns an error (no duplicate thread).
- **AC-052-3**: Given bot is running, When `POST /api/bot/stop` is called, Then the stop flag is set and the bot thread exits within 10 seconds.
- **AC-052-4**: Given bot is running, When `POST /api/bot/pause` is called, Then the bot loop enters a sleep-wait state.

---

## 3. Non-Functional Requirements

### NFR-023: Human-Like Interaction Timing
**Description**: All form interactions SHALL include random delays (30-80ms per keystroke, 0.5-2s between actions) to avoid bot detection.
**Metric**: No interaction faster than 30ms per character.
**Priority**: P0

### NFR-024: Browser Session Persistence
**Description**: Login sessions SHALL persist across bot restarts via Playwright persistent context.
**Metric**: User logs in once, subsequent runs reuse the session.
**Priority**: P0

### NFR-025: Rate Limiting
**Description**: The bot SHALL respect configurable delays between applications (default 45s) and search intervals (default 30 min).
**Metric**: No two applications submitted within `delay_between_applications_seconds` of each other.
**Priority**: P0

### NFR-026: Graceful Degradation
**Description**: Individual job failures (scraping, generation, application) SHALL NOT crash the bot loop. Errors are logged, saved, and the bot continues.
**Metric**: Bot continues running after any single-job failure.
**Priority**: P0

### NFR-027: Daily Application Limit
**Description**: The bot SHALL NOT exceed `max_applications_per_day` applications in a single day.
**Metric**: `applied_today` counter checked before each application attempt.
**Priority**: P0

---

### FR-083: BaseApplier Retry Wrapper

**Description**: The system SHALL implement automatic retry logic in the `BaseApplier.apply()` method, wrapping each subclass's `_do_apply()` with configurable retry count and exponential backoff.
**Priority**: P0
**Dependencies**: FR-046

**Acceptance Criteria**:
- **AC-083-1**: Given `MAX_RETRIES = 2`, When `_do_apply()` fails with a transient error (network timeout, generic exception), Then the system retries up to 2 additional times (3 total attempts).
- **AC-083-2**: Given retries are configured with `RETRY_DELAYS = [3, 8]`, When a retry occurs, Then the system waits the specified delay (3s, then 8s) before the next attempt.
- **AC-083-3**: Given `_do_apply()` returns `captcha_detected=True` or `manual_required=True`, When evaluating the result, Then the system does NOT retry (returns immediately).
- **AC-083-4**: Given `_do_apply()` returns a form validation error (error_message contains "form error", "validation", or "required field"), When evaluating the result, Then the system does NOT retry.
- **AC-083-5**: Given all retry attempts are exhausted, Then `ApplyResult.attempts` reflects the total number of attempts made.
- **AC-083-6**: Each retry attempt is logged at INFO level with platform name, attempt number, and delay.

---

### FR-084: Safe Navigation & Element Waiting

**Description**: The system SHALL provide helper methods in `BaseApplier` for safe page navigation and element waiting with configurable timeouts.
**Priority**: P0
**Dependencies**: FR-046, FR-047

**Acceptance Criteria**:
- **AC-084-1**: `_safe_goto(url)` navigates with `wait_until="domcontentloaded"` and `timeout=NAV_TIMEOUT` (default 30000ms).
- **AC-084-2**: `_wait_and_query(selector, timeout)` waits for the element to become visible within `ELEMENT_TIMEOUT` (default 5000ms), returning the element or None on timeout.
- **AC-084-3**: Both `ELEMENT_TIMEOUT` and `NAV_TIMEOUT` are class-level constants that subclasses can override (e.g., Workday uses 8000ms / 45000ms).
- **AC-084-4**: `_wait_and_query()` catches all exceptions during wait and returns None (never raises).

---

### FR-085: Safe Form Interaction Helpers

**Description**: The system SHALL provide helper methods in `BaseApplier` for safe form filling, file upload, and element clicking with built-in error handling.
**Priority**: P0
**Dependencies**: FR-046, FR-047

**Acceptance Criteria**:
- **AC-085-1**: `_safe_fill(selector, value, clear_first)` finds the element, clears it if `clear_first=True` and it has a different value, then fills using `_human_type()`. Returns True if filled, False if element not found or already has the correct value.
- **AC-085-2**: `_safe_upload(resume_path, selectors)` tries multiple selectors in order, uploading the file via the first matching file input. Logs warnings on failure. Returns True if uploaded.
- **AC-085-3**: `_safe_click(selector, timeout)` waits for the element using `_wait_and_query()`, then clicks if visible. Returns True if clicked.
- **AC-085-4**: All helper methods handle exceptions gracefully (log and return False, never raise).

---

### NFR-028: Applier Timeout Configuration

**Description**: Each applier platform SHALL have configurable timeout values for element waits and navigation, allowing platform-specific tuning for slow-rendering SPAs.
**Priority**: P1
**Metric**: Workday uses ELEMENT_TIMEOUT=8000ms and NAV_TIMEOUT=45000ms; all others use defaults (5000ms / 30000ms).

---

### FR-086: Portal Credential Vault

**Description**: The system SHALL store and retrieve portal login credentials using an OS keyring (preferred) with SQLite database fallback, keyed by extracted domain.
**Priority**: P0
**Dependencies**: FR-004

**Acceptance Criteria**:
- **AC-086-1**: Given a domain, username, and password, When `store_credential()` is called, Then the username is stored in the DB and the password is stored in the OS keyring (if available) or DB (fallback).
- **AC-086-2**: Given a stored credential, When `get_credential(domain)` is called, Then it returns `(username, password)` retrieving the password from keyring first, DB second.
- **AC-086-3**: Given a stored credential, When `delete_credential(domain)` is called, Then it removes the credential from both keyring and DB.
- **AC-086-4**: Given multiple stored credentials, When `list_credentials()` is called, Then it returns all credentials with passwords masked (not included).
- **AC-086-5**: Domain extraction SHALL use hostname for standard sites, and `hostname/company` for shared-domain ATS portals (Greenhouse, Lever, Ashby).
- **AC-086-6**: Storing a credential for an existing domain SHALL upsert (update, not duplicate).
- **AC-086-7**: Login attempts (success/failure) SHALL be tracked per domain with counters and timestamps.

---

### FR-087: Login Detection

**Description**: The system SHALL detect login/signup walls on ATS portal pages using URL pattern matching (tier 1) and DOM element inspection (tier 2).
**Priority**: P0
**Dependencies**: FR-047

**Acceptance Criteria**:
- **AC-087-1**: Given a page URL containing login-related path segments (`login`, `signin`, `auth`, `sso`, etc.), When `detect_login_wall(page)` is called, Then it returns True.
- **AC-087-2**: Given a page with a visible `input[type="password"]` element, When `detect_login_wall(page)` is called, Then it returns True.
- **AC-087-3**: Given a page with Workday-specific sign-in selectors (`data-automation-id="signIn-email"`), When `detect_login_wall(page)` is called, Then it returns True.
- **AC-087-4**: Given a normal application page with no login indicators, Then `detect_login_wall()` returns False.
- **AC-087-N1**: Given any exception during detection, Then the method returns False (never raises).

---

### FR-088: Auto-Login

**Description**: The system SHALL attempt automatic login using stored credentials, with platform-specific strategies (generic form fill and Workday-specific selectors).
**Priority**: P0
**Dependencies**: FR-086, FR-087, FR-047

**Acceptance Criteria**:
- **AC-088-1**: Given stored credentials for a domain, When `try_auto_login()` is called, Then it fills email/username and password fields with human-like typing (30–80ms per character).
- **AC-088-2**: Given a Workday portal, When auto-login is attempted, Then it uses `data-automation-id` selectors; if those fail, it falls back to generic login.
- **AC-088-3**: Given login succeeds (no longer on login wall after submit), Then the method returns True and records a success attempt.
- **AC-088-4**: Given login fails (still on login wall after submit), Then the method returns False and records a failure attempt.
- **AC-088-5**: Given no stored credentials for a domain, Then `try_auto_login()` returns False immediately.

---

### FR-089: Browser Handoff Login Gate

**Description**: The system SHALL pause the bot when a login wall is detected and auto-login fails (or no credentials exist), emitting a `LOGIN_REQUIRED` SocketIO event and blocking until the user responds with "done" (logged in) or "skip".
**Priority**: P0
**Dependencies**: FR-086, FR-087, FR-088, FR-050

**Acceptance Criteria**:
- **AC-089-1**: Given a login wall detected and no stored credentials, When the bot encounters the wall, Then it emits a `LOGIN_REQUIRED` feed event with domain, portal_type, and URL.
- **AC-089-2**: Given a `LOGIN_REQUIRED` state, When the bot thread calls `wait_for_login()`, Then it blocks until the user sets a decision via `set_login_decision()`.
- **AC-089-3**: Given the user responds "done" with credentials, When the decision is set, Then the credentials are saved to the vault and the bot retries the application.
- **AC-089-4**: Given the user responds "skip", When the decision is set, Then the job is saved with status `login_required` for later retry.
- **AC-089-5**: Given the bot is stopped while waiting at the login gate, Then `wait_for_login()` returns "stop" immediately.
- **AC-089-6**: `BotState.get_status_dict()` SHALL include `awaiting_login` (bool) and `login_context` (dict with domain, portal_type, url).
- **AC-089-7**: The `POST /api/portal-auth/login-decision` endpoint SHALL accept `{"decision": "done"|"skip"}` and unblock the bot thread.

---

## 4. Out of Scope

- **CAPTCHA solving** — Phase 6 (detected and reported, not solved)
- **Screening question AI answers** — Future
