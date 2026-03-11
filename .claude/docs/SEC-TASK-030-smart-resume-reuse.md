# Security Audit Report: SEC-TASK-030-smart-resume-reuse

**Date**: 2026-03-11
**Auditor**: Claude (Security Engineer)
**Scope**: TASK-030 M1 — Knowledge Base foundation (4 new modules, 3 new DB tables, 2 config models)

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

## Checklist Summary

| Section | Pass | Fail | N/A | Notes |
|---------|:----:|:----:|:---:|-------|
| A. Input Validation | 4 | 0 | 1 | A5 N/A (no API endpoints in M1) |
| B. Injection Prevention | 6 | 0 | 1 | B3 N/A (no HTML output) |
| C. Authentication | 0 | 0 | 6 | No new endpoints in M1 |
| D. Authorization | 0 | 0 | 5 | No new endpoints in M1 |
| E. Secrets Management | 7 | 0 | 0 | No secrets in code, LLM keys not stored |
| F. Data Protection | 1 | 0 | 3 | Raw text stored locally (acceptable for desktop app) |
| G. Dependencies | 5 | 0 | 0 | All pinned, no known CVEs |
| H. Error Handling | 4 | 0 | 0 | Errors logged, no stack trace leakage |
| I. Transport Security | 0 | 0 | 5 | No network endpoints in M1 |
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
| M3 (LaTeX) | Jinja2 templates must use `autoescape=True` or manual escaping for LaTeX special chars to prevent command injection. |

## Verdict

**PASS** — No security vulnerabilities found in M1 foundation code. All M1 code is backend-only with no user-facing endpoints, reducing attack surface to zero for this milestone. Future milestones (especially M5 Upload API) must follow the recommendations above.
