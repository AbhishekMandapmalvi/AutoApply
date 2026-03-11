# Software Requirements Specification

**Document ID**: SRS-TASK-030-smart-resume-reuse
**Version**: 1.0
**Date**: 2026-03-11
**Status**: approved
**Author**: Claude (Requirements Analyst)
**PRD Reference**: PRD-TASK-030-smart-resume-reuse

---

## 1. Purpose and Scope

### 1.1 Purpose
This SRS specifies the functional and non-functional requirements for Milestone 1 (Foundation) of the Smart Resume Reuse feature (TASK-030). The audience is the System Engineer, Backend Developer, Unit Tester, Integration Tester, Security Engineer, and Release Engineer.

### 1.2 Scope
**In scope (M1)**:
- SQLite schema for Knowledge Base entries, uploaded documents, and roles tables
- Document text extraction from PDF, DOCX, TXT, and MD files
- Cloud LLM-based extraction of structured KB entries from raw text (single call per upload)
- KB CRUD operations with deduplication
- Markdown resume parser for ingesting existing/generated resumes into KB
- Experience calculator from roles data
- Pydantic config models (ResumeReuseConfig, LatexConfig)
- i18n keys for KB and reuse settings UI (pre-populated for M5)

**In scope (M2)**:
- TF-IDF cosine similarity scoring engine (stdlib only)
- Job description analyzer: keyword extraction, section detection, tech term recognition
- Synonym normalization for common technology aliases
- ONNX embedding interface (optional, mocked in tests)
- Score blending: 0.3 * TF-IDF + 0.7 * ONNX when available, TF-IDF only otherwise

**Explicitly out of scope (M1/M2)**:
- LaTeX compilation (M3)
- Bot integration and resume assembly (M4)
- Frontend UI, upload endpoints, KB viewer (M5)
- ATS scoring (M6), manual builder (M7), performance (M8), intelligence (M9), migration (M10)

### 1.3 Definitions and Acronyms
| Term | Definition |
|------|-----------|
| KB | Knowledge Base — SQLite table storing categorized resume entries |
| Entry | A single categorized text item in the KB (e.g., one experience bullet) |
| Dedup | Deduplication — preventing identical entries via UNIQUE constraint on (category, text) |
| LLM | Large Language Model — cloud AI service (Anthropic, OpenAI, Google, DeepSeek) |
| Extraction | One-time LLM call to parse a raw document into structured KB entries |
| Ingestion | Parsing an existing markdown resume into KB entries without LLM |
| Role | A work history entry (title, company, dates, domain) used for experience calculation |

---

## 2. Overall Description

### 2.1 Product Perspective
This feature extends the existing AutoApply bot. Currently, every job application requires 2 LLM API calls (resume + cover letter). The KB pipeline processes career documents once via LLM, stores structured entries locally, and enables future milestones to assemble resumes from KB entries without additional LLM calls.

### 2.2 User Classes and Characteristics
| User Class | Description | Frequency of Use | Technical Expertise |
|-----------|-------------|-------------------|---------------------|
| Active Seeker | Job seeker running bot daily, 20-50 apps/day | Daily | Intermediate |
| Career Switcher | Professional with diverse experience | Weekly | Intermediate |
| Power User | Technical user who wants control over resume content | Ongoing | Expert |

### 2.3 Operating Environment
- Windows 10+, macOS 12+, Linux (Ubuntu 22.04+)
- Python 3.10+ (Flask backend inside Electron shell)
- SQLite 3.35+ (WAL mode, 5s busy timeout)
- Optional dependencies: PyPDF2 3.0.1 (PDF), python-docx 1.1.2 (DOCX), Jinja2 3.1.6 (templates)

### 2.4 Assumptions
| # | Assumption | Risk if Wrong | Mitigation |
|---|-----------|---------------|------------|
| A1 | PyPDF2 can extract text from most PDFs | Scanned/image-only PDFs yield empty text | Log warning, user re-uploads as TXT |
| A2 | LLM providers return valid JSON when prompted | Malformed JSON or markdown-wrapped response | Robust parsing with fence stripping + fallback |
| A3 | Existing DB migration pattern (ALTER TABLE) is sufficient | Schema version conflicts | Use PRAGMA table_info to detect columns before altering |
| A4 | 12,000 character truncation is sufficient for most documents | Long documents lose tail content | Log truncation, user can split documents |

### 2.5 Constraints
| Type | Constraint | Rationale |
|------|-----------|-----------|
| Technical | Must use SQLite (existing DB layer) | No new infrastructure, offline-first desktop app |
| Technical | Must maintain backward compatibility with existing config.json | Existing users must not lose configuration |
| Technical | LLM extraction must work with all 4 supported providers | Provider-agnostic design |
| Technical | New dependencies must be pinned versions | Reproducible builds per CLAUDE.md §8.7 |

---

## 3. Functional Requirements

### FR-030-01: Document Text Extraction

**Description**: The system shall extract plain text content from uploaded documents in PDF, DOCX, TXT, and MD formats.

**Priority**: P0 (ship-blocking)
**Source**: US-101 from PRD
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-01-1**: Given a valid UTF-8 TXT file, When `extract_text()` is called, Then the full text content is returned as a string.
- **AC-030-01-2**: Given a valid MD file, When `extract_text()` is called, Then the full markdown content is returned as a string.
- **AC-030-01-3**: Given a valid PDF file with extractable text, When `extract_text()` is called, Then all pages' text is returned joined by double newlines.
- **AC-030-01-4**: Given a valid DOCX file, When `extract_text()` is called, Then all paragraphs' text is returned joined by double newlines.
- **AC-030-01-5**: Given a TXT file with Latin-1 encoding, When UTF-8 decode fails, Then the system falls back to Latin-1 encoding and returns the content.

**Negative Cases**:
- **AC-030-01-N1**: Given a file path that does not exist, When `extract_text()` is called, Then `FileNotFoundError` is raised.
- **AC-030-01-N2**: Given a file with unsupported extension (e.g., .csv), When `extract_text()` is called, Then `ValueError` is raised with message listing supported types.
- **AC-030-01-N3**: Given a PDF file when PyPDF2 is not installed, When `_extract_from_pdf()` is called, Then `RuntimeError` is raised with install instructions.
- **AC-030-01-N4**: Given a DOCX file when python-docx is not installed, When `_extract_from_docx()` is called, Then `RuntimeError` is raised with install instructions.

---

### FR-030-02: Uploaded Document Storage

**Description**: The system shall persist metadata for each uploaded document in the `uploaded_documents` table, including filename, file type, stored path, raw extracted text, and LLM provider/model used for extraction.

**Priority**: P0
**Source**: US-101 from PRD
**Dependencies**: FR-030-01

**Acceptance Criteria**:

- **AC-030-02-1**: Given a successful text extraction, When `save_uploaded_document()` is called, Then a row is inserted with filename, file_type, file_path, raw_text, llm_provider, llm_model, and auto-generated created_at.
- **AC-030-02-2**: Given an upload_dir parameter, When `process_upload()` is called, Then the file is copied to upload_dir and stored_path references the copy.

**Negative Cases**:
- **AC-030-02-N1**: Given a document with empty extracted text, When `process_upload()` is called, Then 0 is returned and no LLM call is made.

---

### FR-030-03: LLM-Based KB Entry Extraction

**Description**: The system shall send extracted document text to a cloud LLM with a structured prompt, parse the JSON response into categorized entries, validate each entry, and return a list of valid entries.

**Priority**: P0
**Source**: US-101 from PRD
**Dependencies**: FR-030-01, FR-030-02

**Acceptance Criteria**:

- **AC-030-03-1**: Given raw document text and valid LLM config, When `_extract_via_llm()` is called, Then `invoke_llm()` is called once with `EXTRACTION_PROMPT` containing the document text.
- **AC-030-03-2**: Given LLM response is a valid JSON array of entry objects, When parsed, Then each entry with a valid category and non-empty text is included in the result.
- **AC-030-03-3**: Given LLM response is wrapped in markdown code fences (```json ... ```), When parsed, Then the fences are stripped and the inner JSON is parsed.
- **AC-030-03-4**: Given document text exceeding 12,000 characters, When `_extract_via_llm()` is called, Then the text is truncated to 12,000 characters before sending to LLM.

**Negative Cases**:
- **AC-030-03-N1**: Given LLM response is not valid JSON, When parsing fails, Then an empty list is returned and the error is logged at ERROR level.
- **AC-030-03-N2**: Given LLM response is valid JSON but not an array, When parsed, Then an empty list is returned and the error is logged.
- **AC-030-03-N3**: Given an entry with category not in VALID_CATEGORIES, When validated, Then that entry is silently skipped.
- **AC-030-03-N4**: Given an entry with empty text, When validated, Then that entry is silently skipped.

---

### FR-030-04: KB Entry CRUD Operations

**Description**: The system shall provide Create, Read, Update, and soft-Delete operations for Knowledge Base entries, with deduplication on insert.

**Priority**: P0
**Source**: US-103 from PRD
**Dependencies**: FR-030-02

**Acceptance Criteria**:

- **AC-030-04-1**: Given a new entry with unique (category, text) pair, When `save_kb_entry()` is called, Then a row is inserted and the new ID is returned.
- **AC-030-04-2**: Given an entry with duplicate (category, text) pair, When `save_kb_entry()` is called, Then `None` is returned (INSERT OR IGNORE) and no duplicate is created.
- **AC-030-04-3**: Given KB entries exist, When `get_kb_entries()` is called with no filters, Then all active entries are returned ordered by created_at DESC, limited to 500.
- **AC-030-04-4**: Given a category filter, When `get_kb_entries(category="experience")` is called, Then only entries with category "experience" are returned.
- **AC-030-04-5**: Given a search term, When `get_kb_entries(search="Python")` is called, Then only entries where text contains "Python" (case-insensitive LIKE) are returned.
- **AC-030-04-6**: Given an entry ID, When `update_kb_entry()` is called with new text, Then the text is updated and updated_at is set to CURRENT_TIMESTAMP.
- **AC-030-04-7**: Given an entry ID, When `soft_delete_kb_entry()` is called, Then is_active is set to 0 and updated_at is set.
- **AC-030-04-8**: Given active_only=True (default), When `get_kb_entries()` is called, Then soft-deleted entries (is_active=0) are excluded.
- **AC-030-04-9**: Given a list of entry IDs, When `get_kb_entries_by_ids()` is called, Then only entries with those IDs are returned.

**Negative Cases**:
- **AC-030-04-N1**: Given an entry ID that does not exist, When `update_kb_entry()` is called, Then False is returned.
- **AC-030-04-N2**: Given an entry ID that does not exist, When `soft_delete_kb_entry()` is called, Then False is returned.
- **AC-030-04-N3**: Given an entry ID that does not exist, When `get_kb_entry()` is called, Then None is returned.

---

### FR-030-05: KB Statistics

**Description**: The system shall provide aggregate statistics about the Knowledge Base including total entries, entries by category, and active entry count.

**Priority**: P1
**Source**: US-103 from PRD
**Dependencies**: FR-030-04

**Acceptance Criteria**:

- **AC-030-05-1**: Given KB entries exist, When `get_kb_stats()` is called, Then a dict is returned with keys: total, active, by_category (dict of category -> count).

**Negative Cases**:
- **AC-030-05-N1**: Given an empty KB, When `get_kb_stats()` is called, Then `{total: 0, active: 0, by_category: {}}` is returned.

---

### FR-030-06: Markdown Resume Parsing

**Description**: The system shall parse markdown-formatted resumes into structured KB entries by identifying section headings (##), subsection headings (###), and bullet points, mapping them to KB categories.

**Priority**: P0
**Source**: US-105 from PRD
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-06-1**: Given a markdown resume with ## Summary section, When `parse_resume_md()` is called, Then one entry with category "summary" is produced containing the paragraph text.
- **AC-030-06-2**: Given a markdown resume with ## Experience and ### Role headings with bullets, When parsed, Then each bullet is an "experience" entry with the ### heading as subsection.
- **AC-030-06-3**: Given a markdown resume with ## Skills section, When parsed, Then one "skill" entry is produced containing the skills text.
- **AC-030-06-4**: Given a markdown resume with ## Education section with line entries, When parsed, Then each line is an "education" entry.
- **AC-030-06-5**: Given a markdown resume with ## Certifications section with bullets, When parsed, Then each bullet is a "certification" entry.
- **AC-030-06-6**: Given a markdown resume with ## Projects section with ### subsections, When parsed, Then each bullet is a "project" entry with subsection context.
- **AC-030-06-7**: Given alternative headings like "Professional Experience" or "Technical Skills", When parsed, Then they map to the correct categories.
- **AC-030-06-8**: Given every parsed entry, Then it contains keys: category, text, subsection, job_types, tags.

**Negative Cases**:
- **AC-030-06-N1**: Given empty or whitespace-only input, When `parse_resume_md()` is called, Then an empty list is returned.
- **AC-030-06-N2**: Given a section heading not in the category map (e.g., "Hobbies"), When parsed, Then that section is ignored.

---

### FR-030-07: Resume Ingestion Pipeline

**Description**: The system shall ingest LLM-generated markdown resumes into the KB by parsing them and inserting entries with dedup.

**Priority**: P1
**Source**: US-105 from PRD
**Dependencies**: FR-030-04, FR-030-06

**Acceptance Criteria**:

- **AC-030-07-1**: Given a valid .md resume file path, When `ingest_generated_resume()` is called, Then the file is read, parsed via `parse_resume_md()`, and entries are inserted into KB.
- **AC-030-07-2**: Given parsed entries, When `ingest_entries()` is called, Then each entry with valid category and non-empty text is inserted via `save_kb_entry()`.

**Negative Cases**:
- **AC-030-07-N1**: Given a resume file that does not exist, When `ingest_generated_resume()` is called, Then 0 is returned and a warning is logged.
- **AC-030-07-N2**: Given entries with invalid category or empty text, When `ingest_entries()` is called, Then those entries are skipped silently.

---

### FR-030-08: Roles Table and Storage

**Description**: The system shall store work history roles (title, company, start_date, end_date, domain, description) in a `roles` table with dedup on (title, company, start_date).

**Priority**: P1
**Source**: US-104 from PRD
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-08-1**: Given role data, When `save_role()` is called, Then a row is inserted with title, company, start_date, end_date, domain, description.
- **AC-030-08-2**: Given duplicate (title, company, start_date), When `save_role()` is called, Then insertion is skipped (INSERT OR IGNORE).
- **AC-030-08-3**: Given roles exist, When `get_roles()` is called, Then all roles are returned ordered by start_date DESC.

**Negative Cases**:
- **AC-030-08-N1**: Given no roles stored, When `get_roles()` is called, Then an empty list is returned.

---

### FR-030-09: Experience Calculator

**Description**: The system shall calculate total years and per-domain years of experience from the roles table, handling various date formats and current roles.

**Priority**: P1
**Source**: US-104 from PRD
**Dependencies**: FR-030-08

**Acceptance Criteria**:

- **AC-030-09-1**: Given roles with start/end dates, When `calculate_experience()` is called, Then total_years and by_domain dict are returned with values rounded to 1 decimal.
- **AC-030-09-2**: Given a role with end_date "Present", "Current", "Now", or empty, When duration is calculated, Then today's date is used as the end date.
- **AC-030-09-3**: Given date strings in formats YYYY-MM-DD, YYYY-MM, YYYY, M/YYYY, M/D/YYYY, When `_parse_date()` is called, Then each is parsed correctly.
- **AC-030-09-4**: Given roles with different domain values, When calculated, Then by_domain aggregates months per domain.
- **AC-030-09-5**: Given a role with null domain, When calculated, Then it is counted under "general".

**Negative Cases**:
- **AC-030-09-N1**: Given no roles, When `calculate_experience()` is called, Then `{total_years: 0.0, by_domain: {}}` is returned.
- **AC-030-09-N2**: Given a role with unparseable start_date, When duration is calculated, Then 0 months is returned for that role.
- **AC-030-09-N3**: Given a role where end_date < start_date, When duration is calculated, Then 0 months is returned.

---

### FR-030-10: Configuration Models

**Description**: The system shall provide Pydantic config models for resume reuse settings (ResumeReuseConfig) and LaTeX compilation settings (LatexConfig), integrated into AppConfig with backward-compatible defaults.

**Priority**: P0
**Source**: US-106 from PRD
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-10-1**: Given no resume_reuse or latex keys in config.json, When AppConfig is loaded, Then default ResumeReuseConfig and LatexConfig are used (enabled=True, min_score=0.60, template="classic").
- **AC-030-10-2**: Given explicit resume_reuse settings in config.json, When AppConfig is loaded, Then custom values override defaults.
- **AC-030-10-3**: Given ResumeReuseConfig and LatexConfig models, When `model_dump()` is called, Then all fields serialize to JSON-compatible dict.

**Negative Cases**:
- **AC-030-10-N1**: Given invalid scoring_method value, When ResumeReuseConfig is constructed, Then Pydantic validation accepts it as a string (validated at runtime in M2).

---

### FR-030-11: Database Schema Migration

**Description**: The system shall automatically migrate existing databases by adding new tables (uploaded_documents, knowledge_base, roles) and new columns (reuse_source, source_entry_ids on resume_versions) without data loss.

**Priority**: P0
**Source**: Derived from backward compatibility constraint
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-11-1**: Given an existing database without the new tables, When `_migrate()` runs, Then uploaded_documents, knowledge_base, and roles tables are created.
- **AC-030-11-2**: Given an existing resume_versions table without reuse_source column, When `_migrate()` runs, Then the column is added via ALTER TABLE.
- **AC-030-11-3**: Given an existing resume_versions table without source_entry_ids column, When `_migrate()` runs, Then the column is added via ALTER TABLE.
- **AC-030-11-4**: Given a fresh database, When schema is created, Then all tables including new ones are created in SCHEMA_SQL.

**Negative Cases**:
- **AC-030-11-N1**: Given reuse_source column already exists, When `_migrate()` runs, Then no error occurs (column existence checked via PRAGMA table_info).

---

### FR-030-12: i18n Keys for KB UI

**Description**: The system shall pre-populate en.json and es.json locale files with translation keys for the Knowledge Base UI (kb section) and resume reuse settings (reuse section).

**Priority**: P2
**Source**: US-103, US-106 (future UI in M5)
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-12-1**: Given en.json, Then it contains a "kb" section with keys for upload, viewer, entry management, stats, and error messages.
- **AC-030-12-2**: Given en.json, Then it contains a "reuse" section with keys for scoring settings and LaTeX template settings.
- **AC-030-12-3**: Given es.json, Then it contains matching Spanish translations for all new kb and reuse keys.

**Negative Cases**:
- **AC-030-12-N1**: Given a locale file without kb/reuse sections, Then the application does not crash (i18n falls back to key name).

---

### FR-030-13: TF-IDF Cosine Similarity Scoring

**Description**: The system shall score KB entries against job description text using hand-rolled TF-IDF cosine similarity (stdlib only: `collections.Counter`, `math`, `re`). Scores range from 0.0 to 1.0.

**Priority**: P0 (M2 ship-blocking)
**Source**: US-102 from PRD
**Dependencies**: FR-030-04 (KB entries must exist)

**Acceptance Criteria**:

- **AC-030-13-1**: Given a JD and a list of KB entries, When `score_kb_entries()` is called, Then each entry receives a cosine similarity score in [0.0, 1.0].
- **AC-030-13-2**: Given entries with scores below `min_score`, When scoring completes, Then those entries are excluded from results.
- **AC-030-13-3**: Given scored results, When returned, Then they are sorted by score descending.
- **AC-030-13-4**: Given a backend JD and backend + frontend KB entries, When scored, Then backend entries rank higher than unrelated frontend entries.

**Negative Cases**:
- **AC-030-13-N1**: Given an empty JD or empty entries list, When `score_kb_entries()` is called, Then an empty list is returned.
- **AC-030-13-N2**: Given entries with empty text fields, When scored, Then those entries receive a score of 0.0.

---

### FR-030-14: Job Description Keyword Extraction

**Description**: The system shall analyze job description text to extract required keywords, preferred keywords, recognized tech terms, and n-gram phrases.

**Priority**: P0 (M2 ship-blocking)
**Source**: US-102 from PRD
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-14-1**: Given a JD with a "Requirements" section, When `analyze_jd()` is called, Then required keywords are extracted from that section.
- **AC-030-14-2**: Given a JD with a "Nice to Have" section, When `analyze_jd()` is called, Then preferred keywords are extracted from that section.
- **AC-030-14-3**: Given a JD mentioning Python, Flask, Docker, When analyzed, Then those terms appear in `tech_terms`.
- **AC-030-14-4**: Given a JD, When analyzed, Then 2-3 word n-gram phrases are extracted.

**Negative Cases**:
- **AC-030-14-N1**: Given empty or None text, When `analyze_jd()` is called, Then empty result dict is returned with all fields as empty lists/dicts.

---

### FR-030-15: JD Section Detection

**Description**: The system shall detect structural sections in job descriptions (requirements, preferred, responsibilities, benefits, about) by matching header patterns.

**Priority**: P1
**Source**: Derived from FR-030-14
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-15-1**: Given a JD with "Requirements:" header, When sections are detected, Then a "requirements" section is returned with its content.
- **AC-030-15-2**: Given a JD with "Nice to Have:" header, When sections are detected, Then a "preferred" section is returned.
- **AC-030-15-3**: Given a JD with "Responsibilities:" header, When sections are detected, Then a "responsibilities" section is returned.

**Negative Cases**:
- **AC-030-15-N1**: Given plain text without section headers, When analyzed, Then sections dict is empty.

---

### FR-030-16: Synonym Normalization

**Description**: The system shall normalize technology term aliases to canonical forms (e.g., "JS" → "javascript", "k8s" → "kubernetes", "postgres" → "postgresql") using a built-in synonym map of 40+ aliases.

**Priority**: P1
**Source**: Derived from FR-030-14
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-16-1**: Given the term "JS", When `normalize_term()` is called, Then "javascript" is returned.
- **AC-030-16-2**: Given the term "k8s", When `normalize_term()` is called, Then "kubernetes" is returned.
- **AC-030-16-3**: Given an unknown term, When `normalize_term()` is called, Then the term is returned lowercased.

---

### FR-030-17: Keyword Match Boosting

**Description**: The system shall boost TF-IDF scores with additive bonuses for matching required keywords (+0.03/match, max +0.15), preferred keywords (+0.02/match, max +0.05), and tech terms (+0.01/match, max +0.05). Final score is capped at 1.0.

**Priority**: P1
**Source**: Derived from FR-030-13
**Dependencies**: FR-030-14 (JD analysis), FR-030-13 (TF-IDF base score)

**Acceptance Criteria**:

- **AC-030-17-1**: Given an entry matching 5 required keywords, When scored, Then the boost is +0.15 (5 × 0.03, capped).
- **AC-030-17-2**: Given an entry matching 3 preferred keywords, When scored, Then the boost is +0.05 (3 × 0.02, capped at 0.05).
- **AC-030-17-3**: Given boosts that would push the score above 1.0, When applied, Then the final score is capped at 1.0.

---

### FR-030-18: ONNX Embedding Score Blending

**Description**: The system shall support optional ONNX embedding scores. When available, final score = 0.3 × TF-IDF + 0.7 × ONNX. When unavailable (no onnxruntime), the system falls back to TF-IDF only.

**Priority**: P2 (interface only in M2, full implementation in M8)
**Source**: US-102 from PRD
**Dependencies**: FR-030-13 (TF-IDF scores)

**Acceptance Criteria**:

- **AC-030-18-1**: Given ONNX runtime is not installed, When scoring with method="auto", Then TF-IDF only is used and scoring_method="tfidf".
- **AC-030-18-2**: Given ONNX scores are available, When blending, Then final = 0.3 × TF-IDF + 0.7 × ONNX.
- **AC-030-18-3**: Given scoring_method="tfidf" in config, When scoring, Then ONNX is never called regardless of availability.

**Negative Cases**:
- **AC-030-18-N1**: Given entries without precomputed embeddings, When ONNX scoring is attempted, Then it returns None and TF-IDF fallback is used.

---

### FR-030-19: Tech Term Dictionary

**Description**: The system shall maintain a built-in dictionary of 100+ recognized technology terms across categories (languages, frameworks, databases, cloud, data/ML) for extraction from job descriptions.

**Priority**: P1
**Source**: Derived from FR-030-14
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-19-1**: Given a JD mentioning "PostgreSQL", When tech terms are extracted, Then "postgresql" appears in results.
- **AC-030-19-2**: Given a JD mentioning "GitHub Actions", When tech terms are extracted (multi-word), Then "github actions" appears in results.
- **AC-030-19-3**: Given the TECH_TERMS dictionary, Then it contains at least 100 entries.

---

## 4. Non-Functional Requirements

### NFR-030-01: KB Assembly Latency (M1 Foundation)

**Description**: KB CRUD operations (insert, query, update, soft-delete) shall complete within 50ms for a KB with 500 entries.
**Metric**: p95 latency < 50ms for CRUD on 500-entry KB
**Priority**: P1
**Validation Method**: Unit test with 500 pre-inserted entries, measure wall-clock time

### NFR-030-02: Structured Logging

**Description**: All new modules (document_parser, knowledge_base, resume_parser, experience_calculator) shall use `logging.getLogger(__name__)` and log at appropriate levels (ERROR for failures, WARNING for degradation, INFO for operations, DEBUG for troubleshooting).
**Metric**: Zero `print()` statements; all error paths logged at WARNING or ERROR
**Priority**: P0
**Validation Method**: Code review + grep for print() in new modules

### NFR-030-03: Test Coverage

**Description**: All new modules shall have unit test coverage of at least 80% of lines, covering both happy paths and error paths.
**Metric**: >= 80% line coverage per new module
**Priority**: P0
**Validation Method**: `pytest --cov` on new modules

### NFR-030-04: Backward Compatibility

**Description**: Existing config.json files without resume_reuse or latex keys shall load without error, using defaults.
**Metric**: Zero breaking changes to AppConfig serialization
**Priority**: P0
**Validation Method**: Unit test loading config without new keys

### NFR-030-05: Dependency Pinning

**Description**: All new dependencies (PyPDF2, python-docx, Jinja2) shall be pinned to exact versions in pyproject.toml.
**Metric**: All new deps use `==` versioning
**Priority**: P0
**Validation Method**: Inspect pyproject.toml

### NFR-030-06: i18n Compliance

**Description**: All user-facing strings in new modules shall use the `t()` translation function. No hardcoded English in source code (log messages are exempt as they target developers).
**Metric**: Zero hardcoded user-facing strings in new modules
**Priority**: P1
**Validation Method**: Code review of all new modules

### NFR-030-07: TF-IDF Scoring Latency

**Description**: TF-IDF scoring of 200 KB entries against a single JD shall complete within 30ms.
**Metric**: p95 latency < 30ms for 200 entries
**Priority**: P1
**Validation Method**: Unit test with 200 entries, measure wall-clock time

### NFR-030-08: Scoring Module Test Coverage

**Description**: All new M2 modules (resume_scorer, jd_analyzer) shall have unit test coverage of at least 90% of lines, covering happy paths, error paths, and edge cases.
**Metric**: >= 90% line coverage per new module
**Priority**: P0
**Validation Method**: `pytest --cov` on new modules

### NFR-030-09: No New Runtime Dependencies (M2)

**Description**: The M2 scoring engine shall use only Python stdlib. ONNX is optional and not required at runtime.
**Metric**: Zero new entries in pyproject.toml [dependencies] for M2
**Priority**: P0
**Validation Method**: Inspect pyproject.toml diff

### NFR-030-10: Structured Logging (M2)

**Description**: Both new M2 modules shall use `logging.getLogger(__name__)` and log scoring operations at INFO level and errors at ERROR level.
**Metric**: Zero `print()` statements; all error paths logged
**Priority**: P0
**Validation Method**: Code review + grep for print() in new modules

---

## 5. Interface Requirements

### 5.1 Internal Interfaces (M1 — no external/UI interfaces, M2 — internal scoring APIs)

| Module | Function | Direction | Consumers |
|--------|----------|-----------|-----------|
| core/document_parser | `extract_text(file_path)` | Called by KnowledgeBase | core/knowledge_base |
| core/knowledge_base | `KnowledgeBase.process_upload()` | Called by routes (M5) | routes/knowledge_base (M5) |
| core/knowledge_base | `KnowledgeBase.get_all_entries()` | Called by assembler (M4) | core/resume_assembler (M4) |
| core/resume_parser | `parse_resume_md(md_text)` | Called by KnowledgeBase | core/knowledge_base |
| core/experience_calculator | `calculate_experience(db)` | Called by assembler (M4) | core/resume_assembler (M4) |
| core/ai_engine | `invoke_llm(prompt, config)` | Called by KnowledgeBase | core/knowledge_base |
| db/database | KB CRUD methods | Called by KnowledgeBase | core/knowledge_base |
| core/resume_scorer | `score_kb_entries(jd_text, entries, config)` | Called by assembler (M4) | core/resume_assembler (M4) |
| core/resume_scorer | `compute_tfidf_score(jd_text, entry_text)` | Utility | Any module |
| core/jd_analyzer | `analyze_jd(text)` | Called by ResumeScorer | core/resume_scorer |
| core/jd_analyzer | `normalize_term(term)` | Called by ResumeScorer | core/resume_scorer |

---

## 6. Data Requirements

### 6.1 Data Entities
- **uploaded_documents**: File metadata + raw extracted text
- **knowledge_base**: Categorized resume entries with dedup, soft-delete, embedding placeholder
- **roles**: Work history with title, company, dates, domain
- **resume_versions** (modified): Two new columns for reuse tracking

### 6.2 Data Retention
| Data Category | Retention Period | Deletion Method |
|--------------|-----------------|-----------------|
| KB entries | Indefinite (user manages) | Soft-delete (is_active=0) |
| Uploaded documents | Indefinite | User-initiated hard delete |
| Roles | Indefinite | User-initiated hard delete |

### 6.3 Data Migration
Existing databases auto-migrated via `_migrate()` — adds new tables and columns without affecting existing data.

---

## 7. Out of Scope

- **LaTeX compilation**: Deferred to M3 — requires pdflatex/TinyTeX bundling.
- **Bot integration**: Deferred to M4 — requires scoring + compilation from M2/M3.
- **Frontend UI and API endpoints**: Deferred to M5 — M1 is backend foundation only.
- **ATS scoring**: Deferred to M6.
- **Manual resume builder**: Deferred to M7.
- **ONNX embeddings**: M2 optional — embedding BLOB column reserved but unused in M1.

---

## 8. Dependencies

### External Dependencies
| Dependency | Type | Status | Risk if Unavailable |
|-----------|------|--------|---------------------|
| PyPDF2 3.0.1 | Runtime (optional) | Available | PDF extraction fails with clear RuntimeError |
| python-docx 1.1.2 | Runtime (optional) | Available | DOCX extraction fails with clear RuntimeError |
| Jinja2 3.1.6 | Runtime | Available | Required for M3 LaTeX templates |
| Cloud LLM API (any provider) | Runtime | Available | Extraction falls through gracefully |

### Internal Dependencies
| This Feature Needs | From Feature/Task | Status |
|-------------------|-------------------|--------|
| invoke_llm() | TASK-003 (AI Engine) | Done |
| Database class | TASK-001 (Foundation) | Done |
| AppConfig Pydantic model | TASK-001 | Done |
| i18n t() function | TASK-015 (i18n) | Done |

---

## 9. Risks

| # | Risk | Probability | Impact | Risk Score | Mitigation |
|---|------|:-----------:|:------:|:----------:|------------|
| R1 | LLM returns malformed JSON | M | M | 4 | Strip markdown fences, catch JSONDecodeError, return empty list |
| R2 | PyPDF2 fails on scanned PDFs | M | L | 3 | Log warning, user re-uploads as TXT |
| R3 | Dedup too aggressive (same text in different contexts) | L | M | 3 | Dedup on (category, text) — subsection differs OK |
| R4 | DB migration fails on edge-case schema | L | H | 4 | Check column existence via PRAGMA before ALTER |

---

## 10. Requirements Traceability Seeds

| Req ID | Source (PRD) | Traces Forward To |
|--------|-------------|-------------------|
| FR-030-01 | US-101 | Design: DocumentParser → Code: core/document_parser.py → Test: test_document_parser.py |
| FR-030-02 | US-101 | Design: Database → Code: db/database.py → Test: test_kb_database.py |
| FR-030-03 | US-101 | Design: KnowledgeBase → Code: core/knowledge_base.py → Test: test_knowledge_base.py |
| FR-030-04 | US-103 | Design: Database+KnowledgeBase → Code: db/database.py, core/knowledge_base.py → Test: test_kb_database.py, test_knowledge_base.py |
| FR-030-05 | US-103 | Design: Database → Code: db/database.py → Test: test_kb_database.py |
| FR-030-06 | US-105 | Design: ResumeParser → Code: core/resume_parser.py → Test: test_resume_parser.py |
| FR-030-07 | US-105 | Design: KnowledgeBase → Code: core/knowledge_base.py → Test: test_knowledge_base.py |
| FR-030-08 | US-104 | Design: Database → Code: db/database.py → Test: test_kb_database.py |
| FR-030-09 | US-104 | Design: ExperienceCalculator → Code: core/experience_calculator.py → Test: test_experience_calculator.py |
| FR-030-10 | US-106 | Design: Config → Code: config/settings.py → Test: test_kb_config.py |
| FR-030-11 | Derived | Design: Database → Code: db/database.py → Test: test_kb_database.py |
| FR-030-12 | US-103, US-106 | Design: i18n → Code: static/locales/en.json, es.json → Test: manual |
| FR-030-13 | US-102 | Design: ResumeScorer → Code: core/resume_scorer.py → Test: test_resume_scorer.py |
| FR-030-14 | US-102 | Design: JDAnalyzer → Code: core/jd_analyzer.py → Test: test_resume_scorer.py |
| FR-030-15 | Derived | Design: JDAnalyzer → Code: core/jd_analyzer.py → Test: test_resume_scorer.py |
| FR-030-16 | Derived | Design: JDAnalyzer → Code: core/jd_analyzer.py → Test: test_resume_scorer.py |
| FR-030-17 | Derived | Design: ResumeScorer → Code: core/resume_scorer.py → Test: test_resume_scorer.py |
| FR-030-18 | US-102 | Design: ResumeScorer → Code: core/resume_scorer.py → Test: test_resume_scorer.py |
| FR-030-19 | Derived | Design: JDAnalyzer → Code: core/jd_analyzer.py → Test: test_resume_scorer.py |

---

## Software Requirements Specification -- GATE 3 OUTPUT

**Document**: SRS-TASK-030-smart-resume-reuse
**FRs**: 19 functional requirements (12 M1 + 7 M2)
**NFRs**: 10 non-functional requirements (6 M1 + 4 M2)
**ACs**: 66 total acceptance criteria (49 positive + 17 negative)
**Quality Checklist**: 20/20 items passed (100%)

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| System Engineer | Full SRS for architecture design |
| Unit Tester | ACs for test case generation |
| Integration Tester | NFRs for performance test planning |
| Security Engineer | Security NFRs + compliance constraints |
| Documenter | Feature descriptions for user docs |
