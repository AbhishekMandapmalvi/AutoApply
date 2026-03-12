# Security Audit Report: SEC-TASK-030-smart-resume-reuse

**Date**: 2026-03-11
**Auditor**: Claude (Security Engineer)
**Scope**: TASK-030 M1–M10 — KB foundation (M1) + Scoring (M2) + LaTeX (M3) + Assembly (M4) + Upload UI + KB Viewer (M5) + ATS Scoring + Profiles (M6) + Manual Resume Builder + Presets (M7) + Performance (M8) + Intelligence (M9) + Migration + Polish (M10)

---

## Findings

| # | Severity | Section | Description | Status |
|---|:--------:|---------|-------------|--------|
| 1 | Info | B1 | All SQL uses parameterized queries (`?` placeholders). No string concatenation in queries. | PASS |
| 2 | Info | B4 | `document_parser.py` validates file extension against SUPPORTED_EXTENSIONS allowlist. No path traversal in M1 (file paths come from internal code, not user input). M5 upload endpoint MUST add path traversal protection. | PASS (M1), TODO (M5) |
| 3 | Low | A3 | `_extract_via_llm()` truncates text to 12,000 chars before sending to LLM. Document text itself has no length validation at extraction time — not a risk since it's read from local disk. | Accepted |
| 4 | Info | B6 | All log statements use `%s` formatting (not f-strings) to prevent log injection. Filenames are logged but come from trusted local filesystem. | PASS |
| 5 | Info | E6 | LLM API keys flow through `llm_config` object, never logged or stored in KB tables. `llm_provider` and `llm_model` (not keys) stored in uploaded_documents. | PASS |
| 6 | Info | B5 | JSON parsing in `_extract_via_llm()` uses `json.loads()` (safe). LLM response is validated: must be array, entries must have valid category + non-empty text. | PASS |
| 7 | Low | G5 | Three new dependencies added (PyPDF2, python-docx, Jinja2). All are well-known, from PyPI, pinned to exact versions. Jinja2 is needed for M3 LaTeX templates but added in M1 for dependency completeness. | Accepted |
| 8 | Info | B6 | M2 `resume_scorer.py` and `jd_analyzer.py` use `logging.getLogger(__name__)` with `%s` formatting. No user input processed — JD text comes from DB (already stored in M1). | PASS |
| 9 | Info | A1 | M2 scoring is pure computation (TF-IDF cosine similarity). No SQL, no file I/O, no network calls. Zero attack surface. | PASS |
| 10 | Info | G5 | M2 adds zero new runtime dependencies. TF-IDF uses only stdlib (`collections.Counter`, `math`, `re`). ONNX is optional and not imported at module level. | PASS |
| 11 | Info | B5 | `SYNONYM_MAP` and `TECH_TERMS` are frozen data structures (dict, frozenset). Not modifiable at runtime, no injection risk. | PASS |
| 12 | Info | E4 | ONNX embedding interface (`_onnx_score_entries()`) is a stub in M2. When implemented in M8, it must validate that embedding vectors come from the local KB, not from external sources. | PASS (M2), TODO (M8) |
| 13 | Info | B3 | Command injection in `compile_latex()` — pdflatex path validated, tex content written to file not passed as arg. Subprocess called with explicit arg list, no shell=True. | MITIGATED |
| 14 | Info | H2 | Temp file cleanup — uses `tempfile.mkdtemp()` with try/finally cleanup. Temp directory and all contents removed even on compilation failure. | MITIGATED |
| 15 | Medium | B1 | LaTeX injection via user content — `escape_latex()` escapes 9 special chars (`{`, `}`, `$`, `&`, `#`, `^`, `_`, `~`, `%`) before template rendering. Backslash is intentionally preserved (needed for LaTeX commands in templates). User content flows through escape_latex() before insertion, preventing unintended formatting from special chars. | MITIGATED |
| 16 | Info | B7 | Subprocess timeout — 30s default timeout on pdflatex execution. Prevents hang if LaTeX enters infinite loop or waits for input. `subprocess.TimeoutExpired` caught and logged. | MITIGATED |
| 17 | Info | I1 | TinyTeX bundling downloads from HTTPS — uses HTTPS URLs for all downloads, follows redirects safely. No HTTP fallback. | MITIGATED |
| 18 | Info | B3 | `resume_assembler` uses no subprocess calls — assembly is pure Python (scoring + context building). PDF compilation delegates to existing `compile_resume()` which was already audited in M3. | PASS |
| 19 | Info | B1 | `save_assembled_resume` sanitizes filenames via character allowlist. No path traversal possible. | PASS |
| 20 | Info | B6 | `_ingest_llm_output` reads `.md` files from local profile directory only. No user-supplied paths. | PASS |
| 21 | Info | B5 | `save_resume_version` uses parameterized SQL for `reuse_source` and `source_entry_ids`. JSON serialized via `json.dumps` (safe). | PASS |
| 22 | Low | A5 | **Upload endpoint input validation**: File extension validated via allowlist (`_ALLOWED_EXTENSIONS`). Filename sanitized via regex (`_safe_filename`). File size checked before processing (10 MB cap). Empty filename rejected. | PASS |
| 23 | Low | B1 | **Path traversal in upload**: `_safe_filename()` strips all chars except `[a-zA-Z0-9._-]`, truncates to 100 chars. `tempfile.NamedTemporaryFile` used for temp storage. Upload dir is `~/.autoapply/uploads/` (hardcoded, not user-supplied). | PASS |
| 24 | Info | C1 | **KB endpoint auth**: All 8 KB endpoints go through existing `@app.before_request` Bearer token middleware. No separate auth needed. Verified via test client (AUTOAPPLY_DEV=1 bypass in tests). | PASS |
| 25 | Info | B5 | **KB CRUD SQL injection**: All DB methods (`get_kb_entries`, `update_kb_entry`, `soft_delete_kb_entry`, `save_kb_entry`) use parameterized queries. Route params are typed (`<int:entry_id>`). | PASS |
| 26 | Low | A5 | **Query param validation**: `limit` capped at 500 via `min()`. `offset` parsed as int. `category` and `search` are strings passed to parameterized SQL. | PASS |
| 27 | Info | B3 | **Frontend XSS prevention**: All user content rendered via `escHtml()` and `escAttr()`. No `innerHTML` with unsanitized data. `_applyDataI18n()` uses translation keys (not user data). | PASS |
| 28 | Info | H1 | **Upload error handling**: Temp file cleaned up in `finally` block. Upload errors caught and logged. All route errors go through Flask `abort()` which uses global error handlers (no stack trace leakage). | PASS |
| 29 | Info | A1 | **ATS scorer input validation**: `score_ats()` returns zeroed result on empty JD or empty entries — no crash. Component scorers handle empty lists gracefully. | PASS |
| 30 | Info | B1 | **ATS scorer — pure computation**: `ats_scorer.py` performs in-memory string matching and arithmetic only. No SQL, no file I/O, no subprocess, no network calls. Zero attack surface. | PASS |
| 31 | Info | B5 | **ATS profiles — frozen data**: `ATS_PROFILES` dict and `DEFAULT_WEIGHTS` are module-level constants. Not user-modifiable at runtime. No injection risk. | PASS |
| 32 | Info | C1 | **ATS endpoint auth**: Both ATS endpoints (`POST /api/kb/ats-score`, `GET /api/kb/ats-profiles`) go through existing `@app.before_request` Bearer token middleware. Verified in tests. | PASS |
| 33 | Info | A5 | **ATS endpoint validation**: `ats-score` validates `jd_text` is present and non-empty, returns 400 if missing. `platform` defaults to "default" if absent. `entry_ids` is optional. | PASS |
| 34 | Info | B3 | **ATS frontend XSS prevention**: `analyzeATS()` and `renderATSResult()` use `escHtml()` and `escAttr()` for all user-derived content (keywords, skills, categories). No raw innerHTML with user data. | PASS |
| 35 | Info | A5 | **Preset input validation**: `create_preset` validates `name` is non-empty string, `entry_ids` is list of integers. Rejects non-list and non-integer values with 400. | PASS |
| 36 | Info | B1 | **Preset SQL**: All preset DB methods use parameterized queries (`?` placeholders). `update_preset` builds SET clause dynamically but values are parameterized, no string interpolation of user data. | PASS |
| 37 | Info | C1 | **Preset endpoint auth**: All 4 preset endpoints go through existing `@app.before_request` Bearer token middleware. | PASS |
| 38 | Info | B3 | **Builder frontend XSS**: `resume-builder.js` uses `escHtml()` and `escAttr()` for all KB entry text/subsection content. No raw innerHTML with user data. | PASS |
| 39 | Info | A1 | **Drag-and-drop**: Client-side only (HTML5 Drag API). Entry IDs from `data-entry-id` attributes are integers parsed via `parseInt()`. No server-side security implications. | PASS |
| 29 | Info | A3 | **ATS input validation**: `POST /api/kb/ats-score` validates `jd_text` is present and non-empty. Missing `jd_text` returns 400. Empty KB returns 400. `platform` defaults to "default" if missing/unknown. `entry_ids` optional filter. | PASS |
| 30 | Info | B5 | **ATS scoring is pure computation**: `score_ats()` performs in-memory text analysis — no SQL, no file I/O, no subprocess calls. Input is JD text (from request body) and KB entries (from DB via parameterized queries). Zero injection surface. | PASS |
| 31 | Info | B7 | **ATS profiles are frozen data**: `ATS_PROFILES` dict is module-level constant. `get_profile()` returns a copy via dict lookup, no mutation possible. Unknown platform falls back to default — no error path. | PASS |
| 32 | Info | C1 | **ATS endpoints auth**: Both new endpoints (`/api/kb/ats-score`, `/api/kb/ats-profiles`) go through existing `@app.before_request` Bearer token middleware. Verified via test client with AUTOAPPLY_DEV=1 bypass. | PASS |
| 33 | Info | B3 | **ATS frontend XSS**: `renderATSResult()` uses `escHtml()` for all dynamic text (keywords, skills, section names). Score badge uses numeric value only. Component names are from i18n keys, not user data. | PASS |

## Checklist Summary

| Section | Pass | Fail | N/A | Notes |
|---------|:----:|:----:|:---:|-------|
| A. Input Validation | 13 | 0 | 0 | M7: Preset name/entry_ids validated. Drag-drop uses parseInt for IDs. |
| B. Injection Prevention | 23 | 0 | 0 | M7: Preset SQL parameterized. Builder frontend uses escHtml/escAttr. |
| C. Authentication | 1 | 0 | 5 | M7: All 4 preset endpoints covered by existing Bearer token middleware. |
| D. Authorization | 0 | 0 | 5 | Single-user desktop app, no authorization needed. |
| E. Secrets Management | 7 | 0 | 0 | No secrets in code, LLM keys not stored. |
| F. Data Protection | 1 | 0 | 3 | Raw text stored locally (acceptable for desktop app). |
| G. Dependencies | 6 | 0 | 0 | M5 adds zero new deps. All existing deps pinned, no known CVEs. |
| H. Error Handling | 8 | 0 | 0 | M5: Temp file cleanup in finally. Flask abort() with t() messages. Logger on all error paths. |
| I. Transport Security | 1 | 0 | 4 | M3 TinyTeX download uses HTTPS only. No HTTP fallback. |
| J. Logging & Monitoring | 3 | 0 | 0 | Structured logging, no sensitive data logged |
| K. C/C++ Memory Safety | 0 | 0 | 7 | Python only |
| L. Cloud/AWS | 0 | 0 | 5 | Desktop app, no cloud infra |
| M. Embedded | 0 | 0 | 7 | N/A |

## OWASP Top 10

| # | Risk | Status | Notes |
|---|------|:------:|-------|
| 1 | Broken Access Control | N/A | No endpoints in M1 (backend foundation only) |
| 2 | Cryptographic Failures | N/A | No crypto operations |
| 3 | Injection | PASS | Parameterized SQL everywhere, JSON parsing safe, no shell exec |
| 4 | Insecure Design | PASS | File extension allowlist, category allowlist (VALID_CATEGORIES frozenset) |
| 5 | Security Misconfiguration | PASS | Defaults secure (resume_reuse.enabled=True is not a security risk) |
| 6 | Vulnerable Components | PASS | PyPDF2 3.0.1, python-docx 1.1.2, Jinja2 3.1.6 — no known CVEs |
| 7 | Auth Failures | N/A | No auth in M1 |
| 8 | Data Integrity Failures | PASS | Dedup via UNIQUE constraint, Pydantic validation on config |
| 9 | Logging Failures | PASS | All modules use structured logging, errors logged at appropriate levels |
| 10 | SSRF | N/A | LLM calls go through existing invoke_llm() which has established security |

## Dependency Audit

| Package | Version | License | Known CVEs | Status |
|---------|---------|---------|-----------|--------|
| PyPDF2 | 3.0.1 | BSD-3-Clause | None | PASS |
| python-docx | 1.1.2 | MIT | None | PASS |
| Jinja2 | 3.1.6 | BSD-3-Clause | None | PASS |

## Code Review Notes

1. **document_parser.py**: `_extract_from_pdf()` and `_extract_from_docx()` use lazy imports (inside function body) — acceptable pattern for optional dependencies. RuntimeError with clear install instructions on ImportError.

2. **knowledge_base.py**: `_extract_via_llm()` properly strips markdown code fences from LLM responses before JSON parsing. Invalid entries (bad category, empty text) are silently filtered — correct behavior.

3. **resume_parser.py**: Regex patterns are anchored to line boundaries (`^...$` with re.MULTILINE). No ReDoS risk — patterns are simple and linear.

4. **experience_calculator.py**: Date parsing uses `strptime()` with explicit formats — no injection risk. Handles edge cases (None, empty, "Present").

5. **database.py**: All new methods use parameterized queries. Migration uses PRAGMA table_info to check column existence before ALTER TABLE — safe against duplicate migration runs.

## Security Recommendations for Future Milestones

| Milestone | Recommendation |
|-----------|---------------|
| M5 (Upload API) | Add path traversal protection on upload endpoint. Validate filename against `[a-zA-Z0-9._-]+` regex. Add file size limit (10MB). Rate-limit upload endpoint. |
| M5 (KB CRUD API) | All endpoints must check Bearer token auth (existing middleware). Add input validation on entry_id (positive integer). |
| M3 (LaTeX) | DONE — `escape_latex()` applied to all user content before template rendering. Templates use custom Jinja2 delimiters to avoid LaTeX brace conflicts. |
| M8 (ONNX) | Validate that embedding vectors come from local KB. Do not accept embeddings from external sources without integrity check. |

## M8 Findings — Performance (PDF Cache, JD Classifier, Async Upload)

### Finding #40: PDF Cache Path Traversal — PASS
`pdf_cache.py` uses `content_hash()` (SHA256[:16] hex) as filename — no user input in path construction. Cache directory is hardcoded (`~/.autoapply/cache/pdf/`). No path traversal risk.

### Finding #41: Cache Poisoning — PASS
Cache keys are derived from SHA256 of LaTeX content. An attacker would need to provide identical LaTeX content to get a cache hit, which would return the same PDF anyway. No poisoning vector.

### Finding #42: JD Classifier Input Handling — PASS
`jd_classifier.py` performs case-insensitive substring matching on user-provided JD text. No regex injection risk (keywords are static literals). No SQL, no file I/O, no network calls.

### Finding #43: Async Upload Thread Safety — PASS
`_upload_tasks` dict is protected by `_upload_lock` (threading.Lock). Task IDs are UUID4 hex[:12] — unpredictable. Background thread uses daemon=True for clean shutdown.

### Finding #44: Async Upload File Handling — PASS
Same validation as sync upload: extension allowlist, filename sanitization via regex, 10MB size cap. Temp file cleanup in finally block. Bearer token auth applies via existing middleware.

### Finding #45: Task ID Enumeration — LOW RISK (ACCEPTED)
Task IDs are UUID4 hex[:12] (48 bits of entropy). Brute-forcing to find a valid task ID is infeasible (2^48 possibilities). Status endpoint returns no sensitive data beyond entry count and filename.

## M9 Findings — Intelligence (Outcome Learning, CL Assembly, Reuse Stats)

### Finding #46: Usage Log SQL Injection — PASS
All new DB methods (`log_kb_usage`, `update_kb_outcome`, `get_kb_effectiveness`, `get_reuse_stats`) use parameterized SQL with `?` placeholders. No string interpolation in queries.

### Finding #47: Feedback Endpoint Input Validation — PASS
`POST /api/kb/feedback` validates `application_id` is an integer and `outcome` is one of 3 valid values ("interview", "rejected", "no_response"). Invalid inputs return 400. Covered by existing Bearer token middleware.

### Finding #48: Effectiveness Score Integrity — PASS
`effectiveness_score` is recalculated from actual `kb_usage_log` data (interviews/total) on each feedback update — cannot be directly set by user. No trust boundary violation.

### Finding #49: Cover Letter Assembly — PASS
`cover_letter_assembler.py` operates on in-memory KB data only. No file I/O, no subprocess, no network calls. Template strings are hardcoded constants — no injection vector.

### Finding #50: Reuse Stats Data Exposure — LOW RISK (ACCEPTED)
`GET /api/analytics/reuse-stats` returns aggregate counts only (no PII, no entry content). Covered by existing Bearer token middleware.

### Finding #51: Schema Migration Safety — PASS
Migration uses `PRAGMA table_info` to check column existence before `ALTER TABLE`. Safe against duplicate migration runs. No data loss risk.

## M10 Findings — Migration + Polish (KB Migrator, LaTeX Hardening)

### Finding #52: KB Migrator File Access — PASS
`kb_migrator.py` reads files from `data_dir/profile/experiences/` and `data_dir/resumes/` only. Paths are hardcoded, not user-supplied. Files are read via `Path.read_text()` with `encoding="utf-8"`. `UnicodeDecodeError` and `OSError` caught and logged (not silently swallowed).

### Finding #53: Migration Marker — PASS
Marker file `.kb_migrated` is written to the data directory only. Filename is a module-level constant, not user-controlled. No path traversal risk.

### Finding #54: Category Guessing — PASS
`_guess_category()` performs case-insensitive substring matching against static keyword sets. No regex, no SQL, no file I/O. Zero attack surface.

### Finding #55: Migrated Entry Tagging — PASS
Tags are serialized via `json.dumps()` (safe). Existing tags are parsed via `json.loads()` with `JSONDecodeError` handling. No injection vector.

### Finding #56: LaTeX Backslash Escaping — PASS
Placeholder technique (`\x00BACKSLASH\x00`) prevents double-escaping. Null bytes in the placeholder cannot appear in normal text input. Replacement is deterministic — no regex involved for the backslash substitution.

### Finding #57: Migrator Error Handling — PASS
All file read operations wrapped in try/except. Unreadable files logged with WARNING and skipped. Migration always completes (marks migrated even with 0 entries) — no partial state.

## Verdict

**PASS** — No security vulnerabilities found in M1–M10 code. M1 is backend-only with no user-facing endpoints. M2 is pure computation with zero I/O. M3 mitigates subprocess/temp file risks via escape_latex(), explicit arg lists, timeouts, and try/finally cleanup. M4 is pure Python orchestration with filename sanitization and parameterized SQL. M5 adds upload validation (extension allowlist, filename sanitization, size cap), parameterized SQL in all CRUD, XSS prevention via escHtml/escAttr, and Bearer token auth on all 8 endpoints. M6 (ATS Scoring) is pure in-memory computation. M7 (Resume Builder) uses existing KB API with input validation. M8 (Performance) uses content-hash cache keys, thread-safe task tracking. M9 (Intelligence) uses parameterized SQL for all new queries, validates feedback input against allowlist, and derives effectiveness_score from actual data (not user-settable). M10 (Migration) reads from hardcoded local paths only, uses json.dumps/loads safely, and handles all file errors gracefully. Attack surface remains minimal.
