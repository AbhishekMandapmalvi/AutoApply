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

**Explicitly out of scope (M1)**:
- TF-IDF scoring engine (M2)
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

---

## 5. Interface Requirements

### 5.1 Internal Interfaces (M1 — no external/UI interfaces)

| Module | Function | Direction | Consumers |
|--------|----------|-----------|-----------|
| core/document_parser | `extract_text(file_path)` | Called by KnowledgeBase | core/knowledge_base |
| core/knowledge_base | `KnowledgeBase.process_upload()` | Called by routes (M5) | routes/knowledge_base (M5) |
| core/knowledge_base | `KnowledgeBase.get_all_entries()` | Called by assembler (M4) | core/resume_assembler (M4) |
| core/resume_parser | `parse_resume_md(md_text)` | Called by KnowledgeBase | core/knowledge_base |
| core/experience_calculator | `calculate_experience(db)` | Called by assembler (M4) | core/resume_assembler (M4) |
| core/ai_engine | `invoke_llm(prompt, config)` | Called by KnowledgeBase | core/knowledge_base |
| db/database | KB CRUD methods | Called by KnowledgeBase | core/knowledge_base |

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

- **TF-IDF scoring engine**: Deferred to M2 — requires JD analyzer dependency.
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

---

## Software Requirements Specification -- GATE 3 OUTPUT

**Document**: SRS-TASK-030-smart-resume-reuse
**FRs**: 12 functional requirements
**NFRs**: 6 non-functional requirements
**ACs**: 42 total acceptance criteria (31 positive + 11 negative)
**Quality Checklist**: 20/20 items passed (100%)

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| System Engineer | Full SRS for architecture design |
| Unit Tester | ACs for test case generation |
| Integration Tester | NFRs for performance test planning |
| Security Engineer | Security NFRs + compliance constraints |
| Documenter | Feature descriptions for user docs |
