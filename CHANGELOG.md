# Changelog

All notable changes to AutoApply are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.3.0] - 2026-03-12

Smart Resume Reuse with Knowledge Base — upload career documents once, reuse entries across applications with zero API calls per resume.

### Added
- **Analytics Dashboard v2.0 (TASK-017)**: Complete analytics overhaul replacing 3 basic charts with 8 rich visualizations. (FR-090 to FR-101, ADR-021)
  - **Summary metric cards**: Total applications, interview rate, average match score, this week count
  - **Period selector**: Switch between 7d, 30d, 90d, and all-time views
  - **Enhanced trend chart**: Daily application counts with configurable period
  - **Conversion funnel**: Applied → Interview → Offer with percentage rates
  - **Platform performance table**: Per-platform totals, interview rates, avg scores, offer counts
  - **Score distribution histogram**: Match score buckets (0-100) with interview overlay
  - **Weekly summary**: This week vs last week comparison with trend indicators
  - **Top companies table**: Top 10 companies by application count with status breakdown
  - **Response time metrics**: Median and average days to interview/rejection
  - **Single enhanced API endpoint**: `GET /api/analytics/enhanced?days=N` returning all data in one request
  - **42 new tests**: Unit tests (34) + integration tests (8) covering all analytics, including 10K-row performance test
  - **30 new i18n keys**: Full translation coverage for all analytics labels
  - **WCAG 2.1 AA accessible**: ARIA regions, keyboard-navigable period selector, semantic tables
- **GitHub repo & PR rules in CLAUDE.md**: Section 9 codifies branch naming, commit format, PR process, CI checks, and merge strategy (CLAUDE.md v4.1)
- **Resume Versioning v2.1.0 (TASK-018)**: Track, browse, and compare AI-generated resume versions. (FR-110 to FR-119, ADR-022, ADR-023)
  - **Resume library screen**: New navigation tab with searchable, sortable, paginated table of all resume versions
  - **Resume detail view**: Metadata panel (company, job title, score, AI provider/model, date, status) with rendered markdown content
  - **PDF preview & download**: Inline PDF viewing via iframe embed, plus download button
  - **Effectiveness metrics**: Summary cards showing tailored vs fallback interview rates, average scores by outcome, per-provider breakdown
  - **Version recording**: `generate_documents()` now captures LLM provider/model metadata; bot saves `resume_versions` record per application
  - **New `resume_versions` table**: Additive schema — no changes to existing `applications` table
  - **4 new API endpoints**: `GET /api/resumes` (paginated list), `GET /api/resumes/<id>` (detail + markdown), `GET /api/resumes/<id>/pdf` (PDF serve), `GET /api/resumes/metrics` (aggregate metrics)
  - **Path traversal protection**: All file-serving endpoints validate paths against data directory
  - **37 new tests**: Unit tests (19) + integration tests (16) + version meta tests (2) covering all endpoints and edge cases
  - **33 new i18n keys**: Full translation coverage for resume library UI
  - **WCAG 2.1 AA accessible**: ARIA roles/labels, keyboard navigation, semantic HTML, responsive grid layout
- **Resume Comparison & Favorites v2.2.0 (TASK-019)**: Compare resumes side-by-side and mark favorites. (FR-120 to FR-125, ADR-024)
  - **Favorite toggle**: Star icon on each resume row; `PUT /api/resumes/<id>/favorite` toggles `is_favorite` boolean
  - **Sort by favorites**: "Favorites first" option in sort dropdown brings starred resumes to top
  - **Comparison selection**: Checkboxes on resume rows (max 2); oldest auto-deselected on 3rd click
  - **Compare overlay**: Side-by-side header with company/title/date, plus unified line diff view
  - **Client-side line diff**: LCS-based diff algorithm renders added/removed/unchanged lines with color coding
  - **2 new API endpoints**: `GET /api/resumes/compare?left=X&right=Y` (comparison data), `PUT /api/resumes/<id>/favorite` (toggle)
  - **14 new tests**: Favorite DB (6), favorite API (3), comparison API (5) — total 51 resume tests
  - **12 new i18n keys**: compare, favorite, unfavorite, diff_added/removed/unchanged, etc.
  - **WCAG 2.1 AA accessible**: ARIA labels on stars/checkboxes, diff region roles, keyboard-navigable
- **Code Signing & Notarization (TASK-021, D-4)**: Configure electron-builder for platform code signing. (FR-126 to FR-130, ADR-025, ADR-026)
  - **Windows signing**: NSIS installer signed via `WIN_CSC_LINK` / `WIN_CSC_KEY_PASSWORD` secrets
  - **macOS signing + notarization**: DMG signed with Developer ID, notarized via `@electron/notarize`
  - **Hardened runtime**: macOS entitlements for JIT + unsigned memory (Electron/Node.js/Python)
  - **CI integration**: Release workflow passes 7 signing secrets as env vars (opt-in, graceful skip)
  - **Setup guide**: `docs/guides/code-signing.md` with step-by-step instructions for both platforms
  - **No breaking changes**: Unsigned builds continue to work when secrets are not configured
- **Locale Switcher UI (TASK-022, QOL-3)**: Language dropdown in Settings to switch UI locale. (FR-131 to FR-134)
  - **Settings dropdown**: Language section at top of Settings screen with all available locales
  - **Human-readable names**: Dropdown shows "English", "Español", "Français", etc. instead of codes
  - **localStorage persistence**: Selected locale survives page reloads (FR-132)
  - **Backend sync**: `PUT /api/locale` endpoint updates backend `set_locale()` for translated error messages (FR-133)
  - **12 new tests**: 5 endpoint tests + 7 frontend code tests — total 33 i18n tests
  - **WCAG 2.1 AA accessible**: Proper `<label>` and `aria-label` on dropdown
- **Sample Spanish Translation (TASK-023, QOL-4)**: Complete `es.json` locale file with all 385+ keys translated. (FR-135, FR-136)
  - **Full parity**: Every key in `en.json` has a corresponding Spanish translation
  - **Placeholder preservation**: All `{placeholder}` tokens preserved for interpolation
  - **Localized placeholders**: Spanish example data (e.g., "María García", "Madrid", "+34")
  - **8 new tests**: File validation, key parity, no-extra-keys, untranslated spot check, placeholder preservation, API integration
  - **End-to-end**: Locale switcher dropdown now shows "English" and "Español"
- **Frontend Rendering Tests (TASK-024, #13)**: 32 new tests validating DOM rendering for 6 previously untested requirements.
  - **FR-012**: SocketIO script, feed container, bot status, stat counters
  - **FR-014**: Dashboard screen, bot controls, stats panel, mode selector, activity feed
  - **FR-017**: Settings screen, all profile fields, save button, locale dropdown
  - **FR-039**: AI warning banner existence and content
  - **FR-064**: Schedule toggle, 7 day checkboxes, time inputs, status badge
  - **FR-077**: LLM provider/model/key inputs, provider options, validate button
  - **Accessibility**: HTML lang, skip-to-content, main/nav landmarks, ARIA labels
  - **Traceability**: 6 items upgraded from ⚠️ to ✅ (FR-012, FR-014, FR-017, FR-039, FR-064, FR-077)
- **Electron Module Tests (TASK-025, #12)**: 60 new tests validating Electron source code patterns for 7 previously untested requirements.
- **Analytics UI Tests (TASK-026, #31)**: 32 new tests for analytics period selector, chart containers, accessibility, and chart performance patterns. Clears FR-100, NFR-017-03, NFR-017-06.
- **Resume Library UI Tests (TASK-027, #32)**: 26 new tests for resume library screen, detail view, navigation, app detail link, and accessibility. Clears FR-115, FR-116, FR-117, FR-119, NFR-018-04.
- **Resume Comparison UI Tests (TASK-028, #33)**: 23 new tests for star icon toggle, comparison overlay, LCS diff algorithm, and accessibility. Clears FR-121, FR-124, FR-125, NFR-019-02.
- **Electron Distribution Tests (TASK-029, #34)**: 19 new tests validating electron-only packaging config, build targets, bundled Python, and platform installers. Clears FR-081.
  - **FR-019**: App launch — BrowserWindow, dimensions, single instance, context isolation, preload
  - **FR-020**: Backend lifecycle — findPython, venv/bundled/system fallback, spawn, windowsHide
  - **FR-021**: Health check — /api/health polling, 30s timeout, 500ms interval, status 200
  - **FR-022**: Splash screen — logo, spinner, status, frameless, always-on-top, lifecycle ordering
  - **FR-023**: Graceful shutdown — /api/shutdown POST, 3s timeout, taskkill/SIGKILL fallback, cleanup
  - **FR-024**: System tray — icon, tooltip, context menu (Show/Quit), minimize-to-tray, click handler
  - **FR-030**: Log capture — backend.log, 10MB rotation, stdout/stderr piping, append mode
  - **Traceability**: 7 items upgraded from ⚠️ to ✅

- **Smart Resume Reuse M1: KB Foundation (TASK-030)**: Backend data layer for smart resume reuse pipeline. (FR-030-01 to FR-030-12, NFR-030-01 to NFR-030-06, ADR-027, ADR-028)
  - **Document parser**: Extract text from PDF, DOCX, TXT, and MD files via `core/document_parser.py`
  - **Knowledge Base**: LLM-based extraction of categorized entries, CRUD with dedup, soft-delete, stats
  - **Resume parser**: Parse markdown resumes into KB entries for migration and ingestion
  - **Experience calculator**: Domain-specific years calculation from roles table
  - **Config models**: `ResumeReuseConfig` and `LatexConfig` Pydantic models with backward-compatible defaults
  - **DB schema**: 3 new tables (knowledge_base, uploaded_documents, roles) + 2 new columns on resume_versions
  - **i18n**: 46 new keys (33 kb + 13 reuse) in en.json and es.json
  - **89 unit tests + 11 integration tests**: Full coverage of all M1 modules
- **Smart Resume Reuse M2: Scoring Engine (TASK-030)**: TF-IDF scoring engine and JD analyzer. (FR-030-13 to FR-030-19, NFR-030-07 to NFR-030-10, ADR-029, ADR-030)
  - **TF-IDF scorer**: Hand-rolled cosine similarity using only stdlib (collections.Counter, math, re)
  - **JD analyzer**: Keyword extraction, section detection, 100+ tech terms, 40+ synonym aliases, n-gram extraction
  - **Keyword boosting**: Required (+0.15 max), preferred (+0.05 max), tech term (+0.05 max) bonuses
  - **ONNX interface**: Optional embedding blending (0.3*TF-IDF + 0.7*ONNX), TF-IDF fallback when unavailable
  - **38 new tests**: JD analysis (10), TF-IDF internals (13), scoring (8), ONNX blending (3), section detection (4)
  - **Zero new dependencies**: Stdlib only for M2
- **Smart Resume Reuse M3: LaTeX Engine (TASK-030)**: LaTeX compiler, templates, and TinyTeX bundler. (FR-030-20 to FR-030-26, NFR-030-11 to NFR-030-13, ADR-031)
  - **LaTeX compiler**: `core/latex_compiler.py` — pdflatex discovery (bundled TinyTeX → PATH → common locations), special character escaping, Jinja2 rendering, PDF compilation with timeout
  - **4 resume templates**: classic (helvet, standard), modern (accent colors), academic (palatino, education-first), minimal (10pt compact)
  - **Custom Jinja2 delimiters**: `\VAR{}`, `\BLOCK{}` to avoid LaTeX brace conflicts (ADR-031)
  - **TinyTeX bundler**: `electron/scripts/bundle-tinytex.js` — platform-specific download, extraction, package installation
  - **31 new tests**: Escaping (12), pdflatex discovery (4), template rendering (8), compilation (5), convenience API (2)
  - **New dependency**: jinja2 (template rendering)
- **Smart Resume Reuse M4: Resume Assembly + Bot Integration (TASK-030)**: KB-first resume generation pipeline. (FR-030-27 to FR-030-32, NFR-030-14 to NFR-030-15, ADR-032)
  - **Resume assembler**: `core/resume_assembler.py` — score KB entries against JD, select top per category, build LaTeX context, compile PDF (0 API calls)
  - **KB-first bot flow**: `bot/bot.py` `_generate_docs()` tries KB assembly first, falls through to LLM, then ingests LLM output back into KB
  - **Post-LLM ingestion**: LLM-generated resumes automatically parsed and inserted into KB for future reuse
  - **Version tracking**: `resume_versions.reuse_source` (kb_assembly/llm_generated) + `source_entry_ids` (JSON array)
  - **23 new tests**: Entry selection (5), context building (4), full assembly (5), PDF saving (3), ingestion (3), DB reuse (3)
- **Smart Resume Reuse M5: Upload UI + KB Viewer + Preview (TASK-030)**: Full-stack KB management UI with upload, viewer, and resume preview. (FR-030-33 to FR-030-42, NFR-030-16 to NFR-030-18, ADR-033)
  - **8 REST API endpoints**: Upload (`POST /api/kb/upload`), stats, list with filter/search/pagination, get/update/delete entry, documents list, resume preview (`POST /api/kb/preview`)
  - **KB viewer module**: `static/js/knowledge-base.js` — stats cards, entries table, category filter, debounced search, pagination, edit/delete overlays, upload with status feedback
  - **Resume preview module**: `static/js/resume-preview.js` — template picker (4 styles), JD textarea for auto-scoring, PDF iframe display with download
  - **KB navigation tab**: New "Knowledge Base" tab between Resume Library and Settings, with full ARIA tablist integration
  - **HTML screen**: Upload card, filter controls, entries table, edit/preview overlays, documents list
  - **Blueprint registration**: `kb_bp` registered in `create_app()` with existing auth/rate-limit middleware
  - **i18n**: `nav.knowledge_base` key added to en.json and es.json (33 KB + 13 reuse keys already from M1)
  - **19 new tests**: Stats (2), list (4), get (2), update (3), delete (2), upload (3), documents (1), preview (2)
  - **WCAG 2.1 AA**: ARIA labels, roles, aria-live regions, keyboard navigation, semantic HTML
- **Smart Resume Reuse M6: ATS Scoring + Platform Profiles (TASK-030)**: ATS compatibility scoring with gap analysis and vendor-specific profiles. (FR-030-43 to FR-030-48, NFR-030-19 to NFR-030-20)
  - **ATS composite scorer**: 5-component weighted score (keyword match 35%, section completeness 20%, skill match 20%, content length 15%, format compliance 10%)
  - **Gap analysis**: Identifies matched/missing keywords, skills, and resume sections
  - **7 ATS platform profiles**: Default, Greenhouse, Lever, Workday, Ashby, iCIMS, Taleo — each with vendor-specific weight adjustments
  - **2 API endpoints**: `POST /api/kb/ats-score` (composite score + gaps), `GET /api/kb/ats-profiles` (list profiles)
  - **ATS scoring UI**: Platform selector, JD textarea, color-coded score badge, component progress bars, missing keyword/skill/section badges
  - **i18n**: 18 new keys in `ats` section (en.json + es.json)
  - **31 new tests**: Component scorers (16), composite scorer (4), platform profiles (6), API endpoints (5)
  - **WCAG 2.1 AA**: ARIA labels, aria-live results region, semantic HTML, keyboard navigation
- **Smart Resume Reuse M7: Manual Resume Builder (TASK-030)**: Drag-and-drop resume builder with presets and one-page mode. (FR-030-49 to FR-030-54, NFR-030-21 to NFR-030-22)
  - **Resume presets CRUD**: Save/load/update/delete named entry ID combinations with template choice
  - **`resume_presets` table**: New SQLite table (id, name, entry_ids JSON, template, created_at, updated_at)
  - **4 API endpoints**: `GET/POST /api/kb/presets`, `PUT/DELETE /api/kb/presets/<id>`
  - **Drag-and-drop builder UI**: Full-screen overlay with left panel (KB entries + search/filter) and right panel (6 resume sections with drop zones)
  - **Entry reorder**: Up/down controls within each resume section
  - **One-page mode**: Live page indicator with line estimation (~55 lines/page), warning when exceeding 1 page
  - **Auto-fill from JD**: Keyword-based auto-selection using ATS scoring with per-category limits
  - **PDF preview**: Inline iframe preview using existing `/api/kb/preview` endpoint
  - **i18n**: 27 new keys in `builder` section (en.json + es.json)
  - **15 new tests**: Preset DB methods (7) + preset API endpoints (8)
  - **WCAG 2.1 AA**: ARIA labels on panels/zones/buttons, aria-live regions, keyboard-accessible controls, reduced motion
- **Smart Resume Reuse M8: Performance (TASK-030)**: PDF cache, JD classifier, async upload. (FR-030-55 to FR-030-62, NFR-030-23 to NFR-030-24)
  - **PDF compilation cache**: Content-hash LRU cache (`core/pdf_cache.py`) — SHA256[:16] keys, max 200 files, lazy eviction
  - **LaTeX compiler integration**: `compile_latex()` checks cache before compilation, stores result after (controlled by `use_cache` param)
  - **JD classifier**: Keyword-based job type detection (`core/jd_classifier.py`) — 9 job types, related type expansion, KB entry pre-filtering
  - **Async document upload**: `POST /api/kb/upload/async` returns 202 with task_id, background thread processes file
  - **Upload status polling**: `GET /api/kb/upload/status/<task_id>` — returns processing/completed/failed with entry count
  - **Thread safety**: `threading.Lock` protects shared upload task dict, daemon threads for clean shutdown
  - **30 new tests**: PDF cache (9), JD classifier (14), async upload (5), LaTeX cache integration (2)
  - **Security**: 6 findings all PASS — content-hash keys prevent path traversal, UUID4 task IDs prevent enumeration
- **Smart Resume Reuse M9: Intelligence (TASK-030)**: Outcome-based learning, cover letter KB assembly, reuse stats. (FR-030-63 to FR-030-70, NFR-030-25 to NFR-030-26)
  - **Outcome-based learning**: `kb_usage_log` table tracks entry usage per application; `effectiveness_score` recalculated from interview/total ratio
  - **Feedback API**: `POST /api/kb/feedback` accepts outcome (interview/rejected/no_response), updates effectiveness scores
  - **Effectiveness ranking**: `GET /api/kb/effectiveness` returns entries ranked by effectiveness_score
  - **Cover letter KB assembly**: `core/cover_letter_assembler.py` — template-based cover letter from KB entries (0 API calls)
  - **Reuse stats**: `GET /api/analytics/reuse-stats` — total assemblies, entries used, interview rate, avg effectiveness
  - **JD classifier integration**: Resume assembler pre-filters entries by JD type before TF-IDF scoring
  - **Effectiveness weighting**: TF-IDF scores blended with effectiveness_score (0.7 × tfidf + 0.3 × effectiveness)
  - **DB migration**: 3 new columns on knowledge_base (effectiveness_score, usage_count, last_used_at) + kb_usage_log table
  - **27 new tests**: Usage log (10), cover letter (4), JD integration (1), effectiveness weighting (2), API endpoints (10)
  - **Security**: 6 findings all PASS — parameterized SQL, input validation, derived scores
- **Smart Resume Reuse M10: Migration + Polish (TASK-030)**: Auto-migration of legacy files and LaTeX hardening. (FR-030-71 to FR-030-76, NFR-030-27 to NFR-030-28)
  - **KB migrator**: `core/kb_migrator.py` — auto-migrates `.txt` experience files and `.md` resumes into KB on first startup
  - **Migration pipeline**: `run_migration()` checks marker → migrates experiences + resumes → marks complete (idempotent)
  - **Category guessing**: Keyword heuristics classify entries as experience/skill/education/certification
  - **LaTeX backslash hardening**: Placeholder-based escaping prevents double-escaping of braces in `\textbackslash{}`
  - **28 new tests**: Migration marker (3), experience files (6), resume files (4), full pipeline (4), category guessing (4), LaTeX escaping (7)
  - **Security**: 6 findings all PASS — hardcoded paths, safe JSON, graceful error handling
  - **TASK-030 COMPLETE**: All 10 milestones delivered (M1–M10)

### Changed
- **Traceability matrix v15.0**: 230 requirements, all ✅ (0 ⚠️). TASK-030 M1-M10 adds 104 new requirements (76 FRs + 28 NFRs).
- **CLAUDE.md v5.0**: Gitflow-lite branching model (develop + master), shared-workflows.md as single source of truth
- **CLAUDE.md v4.2**: Added principle #9 (GitHub Issues for every implementation), lesson 12.8 (issue lifecycle)

## [1.9.0] - 2026-03-11

Distribution Build System + Frontend i18n Migration + CI/CD Pipeline.

### Added
- **Frontend JS i18n migration (QOL-1)**: All 12 JS modules now use `t()` calls from `static/js/i18n.js` instead of hardcoded English strings. ~55 string occurrences migrated across bot-control, applications, settings, profile, login, wizard, feed, review, ai-status, analytics, file-upload, and tag-input modules. (LE-3)
- **HTML template i18n migration (QOL-2)**: ~200 elements in `templates/index.html` tagged with `data-i18n`, `data-i18n-placeholder`, and `data-i18n-aria-label` attributes. Covers all wizard steps, navbar, dashboard, applications table, profile, analytics, settings (all sections), and modals. (LE-3)
- **`data-i18n` attribute processor**: Added `_applyDataI18n()` to `static/js/i18n.js` — automatically translates HTML elements on locale load. Supports `data-i18n` (textContent), `data-i18n-placeholder`, `data-i18n-aria-label`, and `data-i18n-title`. (LE-3)
- **Expanded string catalog**: `static/locales/en.json` grew from 166 to 383 keys across 23 sections. New sections: dashboard, eeo, modal, file_upload, experience_levels (short variants).
- **Distribution build system (DIST-1 to DIST-9)**: Complete installer pipeline for all three platforms. (ADR-018, ADR-019, ADR-020)
  - **App icon generation** (`electron/scripts/generate-icon.js`): Programmatic 1024×1024 PNG → ICO (Windows) + ICNS (macOS) via `canvas` + `png2icons`. Run `npm run icons:generate`.
  - **Version sync** (`electron/scripts/sync-version.js`): Reads `pyproject.toml` version → updates `electron/package.json` automatically during build.
  - **Python runtime bundling** (`electron/scripts/bundle-python.js`): Downloads platform-specific Python (Windows embeddable / python-build-standalone for macOS & Linux), installs all dependencies + Playwright Chromium into `electron/python-runtime/`. (ADR-018)
  - **Packaged-mode Python detection**: `python-backend.js` checks bundled `python-runtime/` first in packaged mode, falls back to venv/system Python in dev.
  - **Updated extraResources**: Added `routes/`, `static/`, `app_state.py`, `pyproject.toml` to electron-builder config. Excludes `__pycache__`, tests, venv, .git, node_modules.
  - **Windows NSIS installer**: `npm run dist:win` builds `.exe` installer with custom icon, optional install directory.
  - **macOS DMG installer**: `npm run dist:mac` builds `.dmg` disk image.
  - **Linux AppImage**: `npm run dist:linux` builds portable `.AppImage`.
  - **CI release workflow** (`.github/workflows/release.yml`): Push a `v*` tag to trigger parallel Windows/macOS/Linux builds, uploading all installers to a GitHub Release. (ADR-020)
- **GitHub repository governance**: CODEOWNERS, CONTRIBUTING.md, PR template, issue templates (bug report, feature request), branch protection rules (required status checks, conversation resolution).

### Fixed
- **CI pipeline hardening**: Upgraded all GitHub Actions to Node.js 24-compatible versions (checkout v6, setup-python v6, setup-node v6, upload-artifact v7, download-artifact v8). Fixed gevent exit code handling (SIGTERM codes 143/15 treated as success). Fixed pip-audit for local packages via `pip freeze --exclude`. Fixed mypy return type in `core/i18n.py`.
- **Python bundling**: Fixed `bundle-python.js` quote stripping regex and pip install shell quoting on Windows (uses temp requirements file instead of inline args).
- **Setuptools discovery**: Added explicit package include list in `pyproject.toml` to prevent flat-layout auto-discovery of non-Python directories. Renamed `setup.py` → `setup_env.py` to avoid pip conflict.

## [1.8.3] - 2026-03-11

Production Readiness 10.0/10 — Accessibility, i18n, structured logging, resilience.

### Added
- **Internationalization (i18n)**: JSON-based translation system with 383 strings in `static/locales/en.json`. Backend `core/i18n.py` with `t()` function and `{placeholder}` interpolation. Frontend `static/js/i18n.js` ES module with locale auto-detection. All backend error strings migrated to `t()` calls. `/api/locales` endpoint. To add a new language: copy `en.json`, translate, done. (LE-3)
- **Structured JSON logging**: Set `AUTOAPPLY_LOG_FORMAT=json` for machine-parseable log output with ISO 8601 timestamps and exception serialization. (D-7)
- **LLM retry with exponential backoff**: API calls retry up to 3 times on transient errors (429, 5xx, network failures) with 1s/2s/4s delays. Fails fast on non-retryable errors (400, 401, 403). (D-6)
- **SQLite WAL mode**: `PRAGMA journal_mode=WAL` enables concurrent reads during writes. `PRAGMA busy_timeout=5000` handles lock contention gracefully. (D-5)
- **Accessibility (WCAG 2.1 AA)**: Skip navigation link, semantic HTML (`<main>`, `<nav>`, `role="tablist"`), ARIA attributes (`aria-live`, `aria-label`, `aria-selected`, `aria-modal`), keyboard navigation (arrow keys on tabs, Enter/Space on rows), focus trap in modals, `:focus-visible` outlines, `@media (prefers-reduced-motion: reduce)`. (LE-2)
- **Security hardening**: Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`), 16MB request size limit, path traversal protection on resume/description endpoints, URL validation with domain allowlist on login endpoint, TOCTOU fix on login browser. (ME-9)

### Changed
- Tests increased from 542 to 563+ (21 i18n + 3 WAL + 9 retry + 5 JSON logging tests added).

## [1.8.2] - 2026-03-10

Frontend Component Refactor — split monolithic SPA into ES modules.

### Added
- **Frontend ES modules**: Split 3,170-line `index.html` into 17 JS modules in `static/js/` + CSS in `static/css/main.css`. No build step — native ES module support. (LE-1, ADR-017)

## [1.8.1] - 2026-03-10

Production Readiness — CI, auth, Blueprint refactor, graceful shutdown, mypy, dep pinning.

### Security
- **Flask SECRET_KEY**: Now cryptographically random (`secrets.token_hex(32)`), persisted to `~/.autoapply/.flask_secret` with restricted permissions. Replaces hardcoded key. (NFR-QW1)
- **API key keyring storage**: API keys are stored in the OS keyring (Windows Credential Locker, macOS Keychain, Linux SecretService) when available. Falls back to plaintext `config.json` gracefully. Existing plaintext keys are auto-migrated on first load. (NFR-QW1)
- **API authentication**: All `/api/*` endpoints now require `Authorization: Bearer <token>` header. Token auto-generated at `~/.autoapply/.api_token` on first run. `/api/health` exempt. Dev mode (`AUTOAPPLY_DEV=1`) bypasses auth. Token injected into frontend automatically. (NFR-ME2)
- **CORS lockdown**: SocketIO `cors_allowed_origins` changed from `"*"` to localhost-only (`http://localhost:*`, `http://127.0.0.1:*`). (NFR-ME5)
- **Input validation**: `PUT /api/config` now catches Pydantic `ValidationError` and returns 400 instead of 500. `PATCH /api/applications/:id` validates `status` against allowed set. (NFR-ME3)
- **Error handler hardening**: Added 400 error handler. Generic exception handler now logs full traceback at ERROR level and returns only generic message (no stack traces). (NFR-ME4)

### Fixed
- **Graceful shutdown**: App now cleanly tears down all resources (bot thread, scheduler, login browser, database) on SIGINT/SIGTERM and via `/api/shutdown`. Idempotent shutdown handler registered via `atexit` and signal handlers. Prevents orphaned Chromium processes on exit. (NFR-ME8)
- **Swallowed exceptions**: All 16 bare `except: pass` sites across 8 files now log at appropriate levels (DEBUG for teardown/UI, WARNING for data loss). No silent exception suppression remains. (NFR-QW2)
- **Race condition on bot thread**: `_bot_thread` global now protected by `threading.Lock`. All reads/writes serialized. `_scheduler_start_bot()` returns status string for cleaner route logic. (NFR-QW4)
- **Temp file leak in CSV export**: `export_applications()` now reads CSV into `BytesIO` buffer and deletes the temp file in a `finally` block. No orphaned temp files. (NFR-QW5)
- **Port conflict crash**: `run.py` now auto-detects a free port (5000-5010) instead of crashing with `WinError 10048` when port 5000 is already in use.

### Added
- **Structured logging**: `run.py` configures root logger at startup with console + rotating file handler (`~/.autoapply/backend.log`, 5MB, 3 backups). Set `AUTOAPPLY_DEBUG=1` for DEBUG level. (NFR-QW3)
- **GitHub Actions CI**: Added `.github/workflows/ci.yml` — runs `ruff check`, `pytest`, and `pip-audit` in parallel jobs on every push to master and on PRs. (NFR-ME1, NFR-ME6)
- **Dependency security scanning**: `pip-audit` runs in CI with `--strict` flag — build fails on any known vulnerability. Added to dev dependencies. (NFR-ME6)
- **Dependabot**: Added `.github/dependabot.yml` — weekly automated PRs for pip and GitHub Actions dependency updates. (NFR-ME6)
- **Python tooling (pyproject.toml)**: Consolidated project metadata, dependencies, ruff config, and pytest config into `pyproject.toml`. CI now installs via `pip install -e ".[dev]"`. (NFR-ME3)
- **Pre-commit hooks**: Added `.pre-commit-config.yaml` with ruff lint and format hooks. (NFR-ME3)
- **Lint cleanup**: Fixed 64 ruff lint issues across 14 files — unused imports (F401), unused variables (F841), undefined name reference (F821), import sorting (I001). Codebase now passes `ruff check` clean. (NFR-ME3)
- **Pinned dependency versions**: All 13 runtime dependencies pinned to exact versions (`==`) in `pyproject.toml`. Eliminates supply-chain drift from unpinned `>=` ranges. (NFR-ME6)
- **mypy type checking**: Added mypy configuration to `pyproject.toml` with `check_untyped_defs = true`. All 37 source files pass with zero errors. mypy runs in CI lint job. Fixed 21 type errors including null-safety on `Database | None` routes, `Any`-return from API JSON parsing, and a latent bug in `ApplyResult` construction with invalid kwargs. (NFR-ME7)
- **Job description storage**: Every job that passes the filter has its full description saved as a styled HTML file in `~/.autoapply/profile/job_descriptions/`. Accessible via "View Job Description" button in the application detail modal, and via `GET /api/applications/:id/description`. Useful for interview prep after applying. (FR-075)
- **AI Provider settings**: New Settings section to select LLM provider (Anthropic, OpenAI, Google, DeepSeek), enter API key, and optionally override the default model.
- **API key validation endpoint** (`POST /api/ai/validate`): Test your API key before saving.
- **Default models per provider**: Anthropic → `claude-sonnet-4-20250514`, OpenAI → `gpt-4o`, Google → `gemini-2.0-flash`, DeepSeek → `deepseek-chat`.

### Changed
- **Blueprint architecture**: Split 852-line `app.py` monolith into 7 Flask Blueprints (`routes/bot.py`, `routes/applications.py`, `routes/config.py`, `routes/profile.py`, `routes/login.py`, `routes/analytics.py`, `routes/lifecycle.py`). Shared state extracted to `app_state.py`. `create_app()` factory pattern. All API contracts preserved — zero endpoint changes. (NFR-ME4)
- **Multi-provider LLM API**: Replaced Claude Code CLI integration with direct HTTP API calls to Anthropic, OpenAI, Google Gemini, and DeepSeek. Configure your preferred provider and API key in Settings → AI Provider. (FR-031 through FR-036)
- **Electron-only distribution**: Removed browser mode (`--no-browser` flag, auto-browser-open). AutoApply now launches exclusively as an Electron desktop app.
- **AI status field**: `claude_code_available` renamed to `ai_available` across all API responses.
- **Privacy model**: AI document generation now sends prompts to your configured cloud LLM provider. No data is sent if no API key is configured.

## [1.8.0] - 2026-03-10

Workday & Ashby ATS Support + Application Answers UI.

### Added
- **Workday applier** (`bot/apply/workday.py`): Multi-step form automation for Workday ATS (`*.myworkdayjobs.com`). Handles Apply button, account sign-in, My Information (name, phone, address, country/state dropdowns), My Experience (resume upload), Application Questions (cover letter, screening answers), Voluntary Disclosures (EEO), Self-Identification, and final submission. Uses `data-automation-id` selectors throughout. (FR-070)
- **Ashby applier** (`bot/apply/ashby.py`): Single-page form automation for Ashby ATS (`jobs.ashbyhq.com`, used by OpenAI, YC startups). Fills name, email, phone, LinkedIn, portfolio, location, uploads resume, fills cover letter, and answers custom questions via label matching. (FR-071)
- **ATS pipeline registration**: Workday and Ashby appliers registered in `APPLIERS` dict. Jobs with `myworkdayjobs.com` or `ashbyhq.com` URLs are automatically routed to the correct applier. (FR-072)
- **Application Answers UI** (Settings): New "Application Answers" section between Job Preferences and Platform Login. Collects work authorization, visa sponsorship, years of experience, desired salary, willingness to relocate, earliest start date. Collapsible EEO section for gender, ethnicity, veteran status, disability status. (FR-073)
- **Application Answers UI** (Wizard): Collapsible "Application Answers (recommended)" section in the Profile step with the 6 core screening fields. (FR-073)
- **Screening answers persistence**: `loadSettings()` and `saveSettings()` now read/write `screening_answers` dict. `wizardFinish()` collects wizard screening answers. All data stored in `profile.screening_answers` in `config.json`. (FR-073)
- **Ashby ATS fingerprint**: Added `ashbyhq.com` to `ATS_FINGERPRINTS` in `core/filter.py`. (FR-072)

### Changed
- `bot/bot.py` APPLIERS dict expanded from 4 to 6 entries (added Workday, Ashby).
- `core/filter.py` ATS_FINGERPRINTS expanded from 8 to 9 entries (added `ashbyhq.com`).

### Security
- Workday and Ashby appliers use same human-like interaction delays as existing appliers. (NFR-024)
- CAPTCHA detection on both Workday and Ashby forms. (NFR-025)
- Workday dropdown interaction uses `aria-haspopup="listbox"` pattern, avoiding fragile CSS selectors. (NFR-028)
- EEO data stored locally in `config.json` only — never transmitted to external services. (NFR-020)

## [1.7.2] - 2026-03-10

### Added
- **Apply Manually button**: Review card now includes an "Apply Manually" button that opens the job URL in your browser and saves the application as `manual_required`, letting you apply yourself while the bot continues to the next job.
- `POST /api/bot/review/manual` endpoint for manual submit review decision.
- 2 new tests for manual review endpoint. Tests: 292 total.

## [1.7.1] - 2026-03-10

Bugfixes for platform login and Claude Code detection. *(Note: Claude Code CLI was replaced by multi-provider LLM API in a later release.)*

### Fixed
- **Claude Code detection on Windows**: `check_claude_code_available()` now returns full path from `shutil.which()` instead of bare command name. *(Superseded: Claude Code CLI replaced by LLM API in [Unreleased].)*
- **Platform login browser**: Wizard login buttons (LinkedIn, Indeed) now functional — calls new backend endpoints to open a headed Playwright browser for login. Previously showed placeholder alerts.

### Added
- **Login API endpoints**: `POST /api/login/open`, `POST /api/login/close`, `GET /api/login/status` — open/close a headed browser for platform login with persistent session.
- **Settings: Platform Login section**: Log into LinkedIn or Indeed from the Settings tab (not just during the wizard).
- **Login tests**: 10 new tests covering all login endpoints (validation, domain restriction, open/close/status).
- Tests increased from 280 to 290.

## [1.7.0] - 2026-03-10

Application Detail View — click into any application to see full details, timeline, and notes.

### Added
- **Application detail endpoint** (`GET /api/applications/:id`): Returns full application data including all 17 fields. (FR-065)
- **Application events endpoint** (`GET /api/applications/:id/events`): Returns feed events matching the application's job title and company, providing an activity timeline. (FR-066)
- **Application detail modal**: Click any row in the Applications table to open a detail modal with all fields, editable status/notes, activity timeline, and action links (view posting, download resume, view cover letter). (FR-065)
- **Database**: `get_feed_events_for_job()` method for querying events by job title and company.

### Changed
- `PATCH /api/applications/:id` now supports partial updates — notes-only updates no longer require `status` field. Returns 404 for non-existent applications. (FR-067)
- Application table rows are clickable with hover highlight.
- Status dropdown in table now includes Error and Manual Required options.
- Field name compatibility: table rendering uses both `job_title`/`applied_at` (backend) and `title`/`applied_date` (legacy) field names.
- Tests increased from 265 to 280 (15 new: 3 detail endpoint + 3 events endpoint + 5 PATCH partial + 4 database method).

### Security
- Detail and events endpoints validate application existence before returning data — returns 404 for unknown IDs. (NFR-028)

## [1.6.0] - 2026-03-10

Scheduling & Daily Planner — time-based bot automation.

### Added
- **Schedule configuration** (`config/settings.py`): `ScheduleConfig` model with `enabled`, `days_of_week`, `start_time`, `end_time` fields. Nested in `BotConfig.schedule`. (FR-060)
- **Scheduler engine** (`core/scheduler.py`): Background thread checks every 60 seconds whether the bot should be running based on configured days and time window. Supports overnight windows (e.g., 22:00-06:00). (FR-061, FR-062)
- **Schedule API endpoints**: `GET /api/bot/schedule` and `PUT /api/bot/schedule` with validation for day names and HH:MM time format. (FR-063)
- **Dashboard schedule UI**: Toggle, day-of-week checkboxes, and start/end time pickers in Settings panel. Active badge shows when schedule is enabled. (FR-064)
- **Auto-start on boot**: Scheduler starts automatically on app launch if schedule is enabled in config. (FR-061)

### Changed
- `bot_start()` reuses shared `_scheduler_start_bot()` to avoid duplicating bot thread logic.
- `bot_status` response now includes `schedule_enabled` field.
- Tests increased from 240 to 265 (25 new: 11 time window + 8 scheduler logic + 6 API).

### Security
- Schedule API validates day names against allowlist and time format against 0-23:0-59 range — rejects invalid input with 400. (NFR-028)
- Scheduler only stops bots it auto-started — manually started bots are never interrupted by the scheduler. (NFR-029)

## [1.5.0] - 2026-03-10

ATS Portal Support — Greenhouse and Lever application automation.

### Added
- **Greenhouse applier** (`bot/apply/greenhouse.py`): Form-filling automation for Greenhouse ATS — personal info (first/last name, email, phone, LinkedIn), resume upload, cover letter, and form submission. (FR-057)
- **Lever applier** (`bot/apply/lever.py`): Form-filling automation for Lever ATS — personal info (name, email, phone, LinkedIn, portfolio), resume upload, cover letter, and form submission with automatic `/apply` URL append. (FR-058)
- **ATS pipeline registration**: Greenhouse and Lever appliers registered in `APPLIERS` dict — jobs with `greenhouse.io` or `lever.co` URLs are now automatically routed to the correct applier. (FR-059)

### Changed
- `bot/bot.py` APPLIERS dict expanded from 2 to 4 entries (LinkedIn, Indeed, Greenhouse, Lever).
- Tests increased from 221 to 240 (19 new: 6 Greenhouse + 9 Lever + 4 pipeline registration).

### Security
- Greenhouse and Lever appliers use same human-like interaction delays as existing appliers. (NFR-024)
- CAPTCHA detection on both Greenhouse and Lever forms. (NFR-025)
- Form error detection prevents silent failures. (NFR-028)

## [1.4.0] - 2026-03-09

Dashboard Polish & Review Mode — user visibility and override control over the application process.

### Added
- **Application mode selector**: Dropdown in bot control bar with three modes — Full Auto, Review, Watch. (FR-053)
- **Review mode**: Bot pauses before each submission, emits REVIEW event with job details and generated cover letter for user preview. (FR-053)
- **Review card UI**: Preview card in dashboard with editable cover letter textarea and Approve / Edit / Skip buttons. (FR-053)
- **Review API endpoints**: `POST /api/bot/review/approve`, `/skip`, `/edit` for user decisions. Returns 409 if no review is pending. (FR-053)
- **Bot review gate**: `wait_for_review_decision()` blocks bot thread using `threading.Event` until user responds or bot is stopped. (FR-053)
- **Watch mode**: Launches Chromium in headed (visible) mode when selected. (FR-054)
- **Analytics charts**: Chart.js integration with daily line chart, status donut chart, and platform bar chart. (FR-055)
- **Cover letter modal**: View cover letter for past applications via dedicated modal. (FR-056)
- **REVIEW/SKIPPED feed badges**: Purple and gray badge styling for new event types. (FR-053)

### Changed
- `BotConfig.apply_mode` replaces `watch_mode` boolean — values: `"full_auto"` | `"review"` | `"watch"`. `watch_mode` kept for backward compatibility but deprecated. (FR-053)
- `BotState.get_status_dict()` now includes `awaiting_review` field. (FR-053)
- `BrowserManager` uses `apply_mode` instead of `watch_mode` for headed/headless decision. (FR-054)
- Tests increased from 205 to 221 (7 new API review tests + 9 new state review tests).

### Security
- Review endpoints return 409 when no review is pending — prevents duplicate decisions. (NFR-028)
- Review edit endpoint validates required `cover_letter` field — returns 400 if missing. (NFR-028)

## [1.3.1] - 2026-03-09

Dashboard Live Feed — real-time activity feed with history persistence.

### Added
- **Feed history API** (`GET /api/feed`): Returns recent feed events from the database with configurable `limit` parameter. Feed now persists across page refreshes. (FR-051)
- **Feed counter badge**: Shows event count `(N)` next to "Activity Feed" heading.
- **Clear button**: Clears the feed display (events remain in database).
- **CAPTCHA badge style**: Feed items with type `CAPTCHA` now display with red badge styling.
- **Message display**: Feed items show the backend `message` field as a secondary line when it adds context.
- **Application filter statuses**: Added "Error" and "Manual Required" options to the Applications tab status dropdown.

### Fixed
- **Feed field name mismatch**: `addFeedItem` now reads `evt.job_title` matching backend payload (was reading `evt.title`). Feed items were showing blank titles.
- **Stats not syncing from server**: `handleBotStatus` now reads flat fields (`jobs_found_today`, `applied_today`, `errors_today`) from the backend. Stats were stuck at zero on reconnect.
- **CAPTCHA errors not counted**: CAPTCHA events now increment the error counter in dashboard stats.

### Changed
- Tests increased from 202 to 205 (3 new feed endpoint tests).

## [1.3.0] - 2026-03-09

Bot Core — automated job searching, filtering, and application submission.

### Added
- **Job search engines** (`bot/search/`): LinkedIn and Indeed searchers using Playwright for real-time job discovery with pagination support. (FR-041, FR-042, FR-043)
- **Job scoring engine** (`core/filter.py`): 0-100 scoring system based on title match (0-35), salary (0-20), location (0-20), and keyword match (0-25) with hard disqualifiers for blacklisted companies, excluded keywords, and duplicates. (FR-044, FR-045)
- **ATS detection** (`core/filter.py`): URL-based fingerprinting for Greenhouse, Lever, Workday, Taleo, iCIMS, LinkedIn, and Indeed. (FR-045)
- **Browser manager** (`bot/browser.py`): Playwright persistent context at `~/.autoapply/browser_profile/` preserving login sessions across runs. (FR-047)
- **LinkedIn Easy Apply** (`bot/apply/linkedin.py`): Multi-step modal automation — form filling, resume upload, cover letter paste, submission with confirmation. (FR-048)
- **Indeed Quick Apply** (`bot/apply/indeed.py`): Multi-step form automation — name/email/phone fill, resume upload, external ATS redirect detection. (FR-049)
- **Main bot loop** (`bot/bot.py`): Search → filter → generate docs → apply → save pipeline with pause/stop support, daily limits, rate limiting, and search intervals. (FR-050)
- **Live feed events**: SocketIO events (FOUND, FILTERED, GENERATING, APPLYING, APPLIED, CAPTCHA, ERROR) with database persistence. (FR-051)
- **Bot thread integration** (`app.py`): Daemon thread spawning with duplicate prevention, config validation, and graceful stop with 10s join timeout. (FR-052)

### Changed
- `bot_start()` now validates config exists before spawning thread (returns 400 if missing). (FR-052)
- `bot_stop()` now joins thread with 10s timeout for clean shutdown. (FR-052)
- Tests increased from 77 to 202 (49 new: 35 filter + 14 bot base).

### Security
- CAPTCHA detection prevents automated bypass attempts — returns error to user. (NFR-025)
- Human-like interaction delays (30-80ms per keystroke, 0.5-2s pauses) to avoid detection. (NFR-024)
- Browser automation uses persistent context, no credential storage in code. (NFR-025)
- Thread-safe bot state with `threading.Lock` on all mutations. (NFR-027)

## [1.2.0] - 2026-03-09

Claude Code AI Engine — AI-powered resume and cover letter generation.

### Added
- **AI Engine** (`core/ai_engine.py`): Invokes Claude Code CLI to generate tailored resumes and cover letters for each job application. (FR-031 through FR-036)
- **Resume PDF Renderer** (`core/resume_renderer.py`): Converts Markdown resumes to ATS-safe PDFs using ReportLab — Helvetica only, single-column, no colors/tables. (FR-037)
- **Claude Code availability check**: Runtime detection via `claude --version` subprocess with 10s timeout. (FR-031)
- **Fallback templates**: When Claude Code is unavailable, falls back to static cover letter template and pre-uploaded resume PDF. (FR-038)
- **Dashboard warning banner**: Persistent warning when Claude Code is not detected, with link to install instructions. (FR-039)
- **Experience file reader**: Reads and concatenates all `.txt` files from experience directory with section separators. (FR-033)

### Changed
- `check_claude_code_available()` in `app.py` now delegates to `core.ai_engine` for real runtime check (previously only checked `shutil.which()`). (FR-040)
- Dashboard initialization reads `claude_code_available` from `/api/setup/status` and `/api/bot/status`. (FR-039)
- Tests increased from 46 to 77 (36 new tests for AI engine and PDF renderer).

### Security
- Claude Code invocation uses list-form `subprocess.run()` — no `shell=True`. (NFR-022)
- Prompts contain only non-secret profile fields (name, email, phone, location, URLs, bio). (NFR-020)

## [1.1.0] - 2026-03-09

Electron desktop shell — standalone native app experience.

### Added
- **Electron desktop shell** (`electron/`): Native app window with system tray, splash screen, and single-instance lock. (FR-019, FR-022, FR-024, NFR-015)
- **Python backend lifecycle**: Electron spawns and manages Flask as a child process with health checks, crash restart, and graceful shutdown. (FR-020, FR-021, FR-023)
- **Health endpoint** (`GET /api/health`): Readiness probe for lifecycle management. (FR-025)
- **Shutdown endpoint** (`POST /api/shutdown`): Graceful server termination, localhost-only. (FR-026)
- **CLI flags**: `--no-browser` flag and `AUTOAPPLY_PORT` env var for Electron integration. (FR-027, FR-028)
- **Shared Chromium**: Playwright reuses Electron's bundled Chromium to save ~150MB. (FR-029, ADR-006)
- **Backend logging**: stdout/stderr captured to `~/.autoapply/backend.log` with rotation at 10MB. (FR-030)
- **Port auto-detection**: Finds available port if 5000 is occupied. (ADR-008)

### Changed
- `run.py` now uses `argparse` for CLI argument handling.
- Tests increased from 109 to 117 (new endpoint and CLI tests).

### Security
- `/api/shutdown` rejects non-localhost requests with 403. (FR-026)
- Electron renderer: `nodeIntegration: false`, `contextIsolation: true`. (NFR-016)
- `preload.js` only exposes `openExternal` (URL scheme validated) and `getVersion`. (NFR-016)

## [1.0.0] - 2026-03-09

Phase 1 Foundation — project setup, configuration, database, API, and dashboard.

### Added
- **Setup script** (`setup.py`): Automated environment setup with Python version check, dependency installation, Playwright Chromium installation, and data directory creation. (FR-001, FR-002)
- **Configuration system** (`config/settings.py`): Pydantic v2 models for `UserProfile`, `SearchCriteria`, `BotConfig`, and `AppConfig` with JSON persistence at `~/.autoapply/config.json`. (FR-003, FR-004, FR-005)
- **SQLite database** (`db/database.py`): `applications` and `feed_events` tables with parameterized queries, deduplication index, CSV export, and analytics queries. (FR-006, FR-007, FR-015, FR-016)
- **Database models** (`db/models.py`): Pydantic models for `Application` (17 fields) and `FeedEvent` (7 fields). (FR-006)
- **Bot state machine** (`bot/state.py`): Thread-safe `BotState` with `threading.Lock`, supporting start/pause/stop/resume transitions, daily counters, and uptime tracking. (FR-008, FR-009)
- **Flask web server** (`app.py`): 19 API endpoints covering bot control, applications CRUD, profile/experience file management, configuration, analytics, and setup status. (FR-010 through FR-018)
- **SPA dashboard** (`templates/index.html`): Single-page application with dark theme, 7-step setup wizard, bot controls, application list with filters, analytics charts, settings panel, and profile management. (FR-010, FR-011, FR-012, FR-013, FR-014)
- **WebSocket integration**: Flask-SocketIO with gevent async mode for real-time bot status updates. (FR-009)
- **Entry point** (`run.py`): Creates data directories, starts server on port 5000, auto-opens browser. (FR-001, FR-002)
- **Path traversal protection**: Allowlist filename regex on all experience file endpoints. (NFR-007)
- **Error handling**: Global exception handlers returning JSON (no stack trace leakage). (NFR-009)
- **Unit tests**: 101 tests across 4 test files with 96% code coverage. (NFR-005)
- **Integration tests**: 8 cross-component workflow tests. (NFR-005)
- **Security audit**: Full OWASP Top 10 review, all checks passed. (NFR-007, NFR-010)

### Security
- Parameterized SQL queries throughout — no string concatenation. (NFR-007)
- Filename validation with allowlist regex `^[a-zA-Z0-9_\- ]+\.txt$`. (NFR-007)
- Server binds to 127.0.0.1 only — no external network access. (NFR-007)
- JSON error responses — no internal details leaked. (NFR-009)
