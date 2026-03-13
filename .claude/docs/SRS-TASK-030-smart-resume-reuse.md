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
This SRS specifies the functional and non-functional requirements for Milestones 1–4 (Foundation, Scoring, ~~LaTeX Compilation~~ [DEPRECATED], Resume Assembly via LLM + ReportLab + Bot Integration) of the Smart Resume Reuse feature (TASK-030). The audience is the System Engineer, Backend Developer, Unit Tester, Integration Tester, Security Engineer, and Release Engineer.

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

**In scope (M3)** [SUPERSEDED by M4 LLM + ReportLab pipeline]:
- ~~LaTeX special character escaping for safe template rendering~~
- ~~pdflatex binary discovery (bundled TinyTeX, system PATH, common install locations)~~
- ~~Jinja2-based LaTeX template rendering with custom delimiters (`\VAR{}`, `\BLOCK{}`)~~
- ~~PDF compilation via pdflatex subprocess with configurable timeout~~
- ~~Four built-in resume templates (classic, modern, academic, minimal)~~
- ~~TinyTeX bundling script for cross-platform distribution (Windows, macOS, Linux)~~
- ~~`compile_resume()` convenience function combining template rendering and PDF compilation~~
- **M4 replacement**: LLM-based resume generation from KB entries with strict KB-only prompt, rendered to PDF via ReportLab (stateless, no external binary required)

**In scope (M4)**:
- Resume assembly from KB entries scored against a JD: TF-IDF scoring → entry selection → LLM generation with strict KB-only prompt → ReportLab PDF rendering
- Entry selection with configurable per-category minimums (e.g., min 3 experience, 1 summary)
- LLM-based resume text generation from selected KB entries (uses `llm_config`, NOT `latex_config`)
- ReportLab PDF rendering as PRIMARY renderer (stateless, no external binary dependency)
- Bot `_generate_docs` KB-first flow: attempt KB assembly, fall back to LLM if insufficient entries
- Post-LLM ingestion: auto-parse LLM-generated resume into KB entries for future reuse
- `resume_versions.reuse_source` column tracking origin (`kb_assembly` or `llm_generated`)
- `resume_versions.source_entry_ids` column storing JSON array of KB entry IDs used in assembly

**Explicitly out of scope (M1/M2/M3/M4)**:
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
- Optional dependencies: PyPDF2 3.0.1 (PDF), python-docx 1.1.2 (DOCX), Jinja2 3.1.6 (templates, deprecated for resume assembly), ReportLab (primary PDF renderer)

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

### FR-030-20: [DEPRECATED - M4 Redesign] LaTeX Special Character Escaping

**Description**: ~~The system shall escape LaTeX special characters (`& % $ # _ { } ~ ^`) in user-provided text before template rendering, converting them to their safe LaTeX equivalents (e.g., `&` → `\&`, `~` → `\textasciitilde{}`).~~ Superseded by LLM + ReportLab pipeline in M4. LaTeX compilation is no longer used for resume generation.

**Priority**: ~~P0 (M3 ship-blocking)~~ N/A (deprecated)
**Source**: Derived from M3 LaTeX compilation requirement
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-20-1**: Given text containing `&`, `%`, `$`, `#`, `_`, `{`, `}`, When `escape_latex()` is called, Then each character is replaced with its backslash-escaped form.
- **AC-030-20-2**: Given text containing `~`, When `escape_latex()` is called, Then it is replaced with `\textasciitilde{}`.
- **AC-030-20-3**: Given text containing `^`, When `escape_latex()` is called, Then it is replaced with `\textasciicircum{}`.
- **AC-030-20-4**: Given text containing `\`, When `escape_latex()` is called, Then backslash is preserved (NOT escaped), because backslashes are used in LaTeX commands (e.g., `\textbf`, `\section`).

**Negative Cases**:
- **AC-030-20-N1**: Given `None` input, When `escape_latex()` is called, Then an empty string is returned.
- **AC-030-20-N2**: Given an empty string, When `escape_latex()` is called, Then an empty string is returned.

---

### FR-030-21: [DEPRECATED - M4 Redesign] pdflatex Binary Discovery

**Description**: ~~The system shall discover the `pdflatex` binary by searching in order: (1) bundled TinyTeX directory, (2) system PATH, (3) common installation locations per OS (e.g., `/usr/local/texlive`, `C:\texlive`, `/Library/TeX`).~~ Superseded by ReportLab PDF rendering in M4. No external binary discovery needed.

**Priority**: ~~P0 (M3 ship-blocking)~~ N/A (deprecated)
**Source**: Derived from M3 LaTeX compilation requirement
**Dependencies**: None

**Acceptance Criteria**:

- **AC-030-21-1**: Given a bundled TinyTeX installation exists at the expected location, When `find_pdflatex()` is called, Then the bundled binary path is returned.
- **AC-030-21-2**: Given no bundled TinyTeX but pdflatex is on system PATH, When `find_pdflatex()` is called, Then the PATH binary is returned via `shutil.which()`.
- **AC-030-21-3**: Given pdflatex is not bundled or on PATH but exists in a common location, When `find_pdflatex()` is called, Then the common location binary is returned.

**Negative Cases**:
- **AC-030-21-N1**: Given pdflatex is not found in any location, When `find_pdflatex()` is called, Then `None` is returned.

---

### FR-030-22: [DEPRECATED - M4 Redesign] Jinja2 LaTeX Template Rendering

**Description**: ~~The system shall render LaTeX templates using Jinja2 with custom delimiters (`\VAR{...}` for variables, `\BLOCK{...}` for blocks) to avoid conflicts with LaTeX's native brace syntax. Templates receive a context dict with resume sections, contact info, and formatting options.~~ Superseded by LLM text generation + ReportLab PDF rendering in M4.

**Priority**: ~~P0 (M3 ship-blocking)~~ N/A (deprecated)
**Source**: Derived from M3 LaTeX compilation requirement
**Dependencies**: FR-030-20 (escaping)

**Acceptance Criteria**:

- **AC-030-22-1**: Given a valid LaTeX template file and a context dict, When `render_latex_template()` is called, Then Jinja2 renders the template with custom delimiters and returns the rendered LaTeX string.
- **AC-030-22-2**: Given a context dict with values containing LaTeX special characters, When rendered, Then all values are auto-escaped via the `escape_latex` filter.
- **AC-030-22-3**: Given a template name that exists in the templates directory, When `render_latex_template()` is called with that name, Then the corresponding `.tex` template file is loaded.

**Negative Cases**:
- **AC-030-22-N1**: Given a template name that does not exist, When `render_latex_template()` is called, Then `FileNotFoundError` is raised.
- **AC-030-22-N2**: Given a template with a Jinja2 syntax error, When rendered, Then the Jinja2 exception propagates with a descriptive message.

---

### FR-030-23: [DEPRECATED - M4 Redesign] PDF Compilation via pdflatex

**Description**: ~~The system shall compile rendered LaTeX source into a PDF by invoking `pdflatex` as a subprocess with `-interaction=nonstopmode`, a configurable timeout (default 30s), and a temporary working directory. The compiled PDF is returned as a file path.~~ Superseded by ReportLab `render_resume_to_pdf()` in M4. No subprocess compilation needed.

**Priority**: ~~P0 (M3 ship-blocking)~~ N/A (deprecated)
**Source**: Derived from M3 LaTeX compilation requirement
**Dependencies**: FR-030-21 (binary discovery), FR-030-22 (template rendering)

**Acceptance Criteria**:

- **AC-030-23-1**: Given valid LaTeX source and pdflatex is available, When `compile_pdf()` is called, Then pdflatex is invoked in a temp directory and the output PDF path is returned.
- **AC-030-23-2**: Given pdflatex completes successfully, When the PDF is generated, Then the output file exists and is non-empty.
- **AC-030-23-3**: Given a compilation that exceeds the timeout, When `compile_pdf()` is called, Then `subprocess.TimeoutExpired` is caught and a `RuntimeError` is raised with a descriptive message.

**Negative Cases**:
- **AC-030-23-N1**: Given pdflatex is not available (not found), When `compile_pdf()` is called, Then `RuntimeError` is raised indicating pdflatex is not installed.
- **AC-030-23-N2**: Given LaTeX source with compilation errors, When pdflatex fails (non-zero exit), Then `RuntimeError` is raised including the pdflatex log output.

---

### FR-030-24: [DEPRECATED - M4 Redesign] Built-in Resume Templates

**Description**: ~~The system shall provide four built-in LaTeX resume templates: `classic` (traditional single-column), `modern` (two-column with accent colors), `academic` (CV-style with publications section), and `minimal` (clean whitespace-focused). Each template accepts the same context dict interface.~~ Superseded by LLM-generated resume content rendered via ReportLab in M4. LaTeX templates are no longer used for resume assembly.

**Priority**: ~~P1~~ N/A (deprecated)
**Source**: US-106 from PRD
**Dependencies**: FR-030-22 (template rendering)

**Acceptance Criteria**:

- **AC-030-24-1**: Given the templates directory, Then it contains `classic.tex`, `modern.tex`, `academic.tex`, and `minimal.tex` files.
- **AC-030-24-2**: Given any of the four templates and a standard context dict, When rendered, Then valid LaTeX source is produced without Jinja2 errors.
- **AC-030-24-3**: Given the LatexConfig model with `template="classic"`, When compilation is requested, Then the classic template is selected.
- **AC-030-24-4**: Given a template name not in the four built-in templates, When compilation is requested, Then the system falls back to `classic`.

---

### FR-030-25: [DEPRECATED - M4 Redesign] TinyTeX Bundling Script

**Description**: ~~The system shall provide a bundling script that downloads and packages TinyTeX (minimal TeX Live distribution) for Windows, macOS, and Linux, including only the LaTeX packages required for resume compilation (e.g., `geometry`, `hyperref`, `enumitem`, `fontenc`, `inputenc`).~~ Superseded by ReportLab in M4. No external TeX distribution required.

**Priority**: ~~P2~~ N/A (deprecated)
**Source**: Derived from distribution requirement
**Dependencies**: FR-030-21 (binary discovery expects bundled TinyTeX)

**Acceptance Criteria**:

- **AC-030-25-1**: Given Windows as the target platform, When the bundling script is run, Then TinyTeX is downloaded and extracted to `electron/resources/tinytex/`.
- **AC-030-25-2**: Given macOS or Linux as the target platform, When the bundling script is run, Then the platform-appropriate TinyTeX archive is downloaded and extracted.
- **AC-030-25-3**: Given the bundled TinyTeX, Then it includes `pdflatex` binary and the required LaTeX packages.

**Negative Cases**:
- **AC-030-25-N1**: Given network is unavailable during bundling, When the script is run, Then a clear error message is displayed and the script exits with non-zero code.

---

### FR-030-26: [DEPRECATED - M4 Redesign] compile_resume Convenience Function

**Description**: ~~The system shall provide a `compile_resume()` convenience function that combines template rendering (FR-030-22) and PDF compilation (FR-030-23) into a single call, accepting a template name, context dict, and optional output path.~~ Superseded by `assemble_resume()` in M4, which uses LLM generation + ReportLab rendering.

**Priority**: ~~P0 (M3 ship-blocking)~~ N/A (deprecated)
**Source**: Derived from M3 integration requirement
**Dependencies**: FR-030-22, FR-030-23

**Acceptance Criteria**:

- **AC-030-26-1**: Given a template name and context dict, When `compile_resume()` is called, Then the template is rendered and compiled to PDF, returning the output PDF path.
- **AC-030-26-2**: Given an explicit output_path parameter, When `compile_resume()` is called, Then the compiled PDF is copied to the specified output path.
- **AC-030-26-3**: Given no output_path parameter, When `compile_resume()` is called, Then the PDF is written to a temporary directory and its path is returned.

**Negative Cases**:
- **AC-030-26-N1**: Given pdflatex is not available, When `compile_resume()` is called, Then `RuntimeError` is raised with install instructions.
- **AC-030-26-N2**: Given template rendering fails, When `compile_resume()` is called, Then the error propagates without leaving orphaned temp files.

---

### FR-030-27: Resume Assembly from KB Entries

**Description**: The system shall assemble a complete resume by selecting KB entries scored against a job description via TF-IDF, then generating resume text via LLM with a strict KB-only prompt, and rendering the result to PDF via ReportLab. The assembler retrieves all active KB entries, scores them via `score_kb_entries()`, selects top entries per category respecting configurable minimums, sends selected entries to `generate_resume_from_kb()` for LLM-based text generation, and renders the output to PDF via `render_resume_to_pdf()`. The function signature is `assemble_resume(jd_text, db, llm_config)` (takes `llm_config`, NOT `latex_config`).

**Priority**: P0 (M4 ship-blocking)
**Source**: US-102, US-106 from PRD
**Dependencies**: FR-030-04 (KB CRUD), FR-030-13 (TF-IDF scoring)

**Acceptance Criteria**:

- **AC-030-27-1**: Given a JD text and KB with sufficient entries, When `assemble_resume(jd_text, db, llm_config)` is called, Then selected KB entries are passed to LLM for resume text generation and the result is rendered to PDF via ReportLab.
- **AC-030-27-2**: Given assembled resume text, When passed to `render_resume_to_pdf()`, Then a valid PDF file is produced without errors (ReportLab is the PRIMARY renderer, not a fallback).
- **AC-030-27-3**: Given the assembly process, Then the LLM prompt enforces strict KB-only content (no fabrication beyond what KB entries provide).
- **AC-030-27-4**: Given a KB with entries across all categories, When assembled, Then entries are sorted by score descending within each section before being sent to LLM.
- **AC-030-27-5**: Given the assembly result, Then it includes a `selected_entry_ids` list containing the IDs of all KB entries used.

**Negative Cases**:
- **AC-030-27-N1**: Given an empty KB (0 active entries), When `assemble_resume()` is called, Then `None` is returned indicating insufficient entries.
- **AC-030-27-N2**: Given a KB with entries but none scoring above `min_score`, When assembled, Then `None` is returned indicating insufficient entries.

---

### FR-030-28: Entry Selection with Category Minimums

**Description**: The system shall select KB entries for assembly using configurable per-category minimum counts. If the KB cannot satisfy the minimum for any required category (summary, experience, skills), assembly fails and returns `None` to trigger LLM fallback.

**Priority**: P0 (M4 ship-blocking)
**Source**: US-102 from PRD
**Dependencies**: FR-030-27 (assembly)

**Acceptance Criteria**:

- **AC-030-28-1**: Given default category minimums `{summary: 1, experience: 3, skills: 1, education: 0, certifications: 0, projects: 0}`, When selecting entries, Then at least 1 summary, 3 experience, and 1 skills entry must be available above `min_score`.
- **AC-030-28-2**: Given custom category minimums in ResumeReuseConfig, When selecting entries, Then the custom minimums are used instead of defaults.
- **AC-030-28-3**: Given a category with more entries than the minimum, When selecting, Then the top N entries by score are selected (up to a configurable max per category, default 10).
- **AC-030-28-4**: Given a category with entries between minimum and max, When selecting, Then all qualifying entries above `min_score` are included.

**Negative Cases**:
- **AC-030-28-N1**: Given a KB with only 2 experience entries above `min_score` and minimum is 3, When assembly is attempted, Then `None` is returned.
- **AC-030-28-N2**: Given a KB with 0 summary entries, When assembly is attempted, Then `None` is returned.

---

### FR-030-29: Bot KB-First Flow with LLM Fallback

**Description**: The system shall modify `bot.bot._generate_docs()` to attempt KB-based resume assembly first. If assembly succeeds, the assembled resume is compiled to PDF and used directly. If assembly returns `None` (insufficient entries), the system falls back to the existing LLM-based `generate_documents()` flow.

**Priority**: P0 (M4 ship-blocking)
**Source**: US-102 from PRD
**Dependencies**: FR-030-27 (assembly), FR-030-30 (post-LLM ingestion)

**Acceptance Criteria**:

- **AC-030-29-1**: Given `resume_reuse.enabled=True` in config and KB assembly succeeds, When `_generate_docs()` is called, Then the KB-assembled resume is used and `invoke_llm()` is NOT called for resume generation.
- **AC-030-29-2**: Given `resume_reuse.enabled=True` but KB assembly returns `None`, When `_generate_docs()` is called, Then the existing `generate_documents()` LLM flow is invoked as fallback.
- **AC-030-29-3**: Given `resume_reuse.enabled=False` in config, When `_generate_docs()` is called, Then KB assembly is skipped entirely and LLM flow is used directly.
- **AC-030-29-4**: Given KB assembly succeeds, When the resume is saved, Then `reuse_source="kb_assembly"` is stored in resume_versions.
- **AC-030-29-5**: Given LLM fallback is used, When the resume is saved, Then `reuse_source="llm_generated"` is stored in resume_versions.

**Negative Cases**:
- **AC-030-29-N1**: Given KB assembly raises an unexpected exception, When `_generate_docs()` is called, Then the error is logged at ERROR level and LLM fallback is used (never crash the bot loop).

---

### FR-030-30: Post-LLM Ingestion

**Description**: The system shall automatically parse LLM-generated markdown resumes into KB entries after each LLM fallback, so that future applications for similar roles can reuse those entries without additional LLM calls.

**Priority**: P1
**Source**: US-105 from PRD
**Dependencies**: FR-030-06 (markdown parser), FR-030-07 (ingestion pipeline), FR-030-29 (LLM fallback)

**Acceptance Criteria**:

- **AC-030-30-1**: Given LLM fallback produces a markdown resume, When the resume is saved, Then `ingest_generated_resume()` is called to parse and insert entries into KB.
- **AC-030-30-2**: Given duplicate entries already exist in KB from a previous ingestion, When `ingest_generated_resume()` is called, Then duplicates are silently skipped via dedup (INSERT OR IGNORE).
- **AC-030-30-3**: Given post-LLM ingestion, Then the ingested entry count is logged at INFO level.

**Negative Cases**:
- **AC-030-30-N1**: Given `ingest_generated_resume()` raises an exception, When post-LLM ingestion fails, Then the error is logged at WARNING level and the bot continues (ingestion failure is non-blocking).

---

### FR-030-31: resume_versions reuse_source Column

**Description**: The `resume_versions` table shall include a `reuse_source` column (TEXT, nullable, default NULL) indicating the origin of each resume version: `"kb_assembly"` for KB-assembled resumes or `"llm_generated"` for LLM-produced resumes. Existing rows without this field retain NULL.

**Priority**: P1
**Source**: Derived from FR-030-29 (tracking)
**Dependencies**: FR-030-11 (schema migration)

**Acceptance Criteria**:

- **AC-030-31-1**: Given a KB-assembled resume is saved, When the resume_versions row is inserted, Then `reuse_source="kb_assembly"` is stored.
- **AC-030-31-2**: Given an LLM-generated resume is saved, When the resume_versions row is inserted, Then `reuse_source="llm_generated"` is stored.
- **AC-030-31-3**: Given an existing resume_versions row created before M4, Then `reuse_source` is NULL (backward compatible).
- **AC-030-31-4**: Given the resume_versions API returns version data, Then `reuse_source` is included in the response dict.

---

### FR-030-32: resume_versions source_entry_ids Column

**Description**: The `resume_versions` table shall include a `source_entry_ids` column (TEXT, nullable, default NULL) storing a JSON-serialized array of KB entry IDs used during assembly. This enables tracing which KB entries contributed to each resume version.

**Priority**: P1
**Source**: Derived from FR-030-27 (assembly tracking)
**Dependencies**: FR-030-11 (schema migration), FR-030-27 (assembly)

**Acceptance Criteria**:

- **AC-030-32-1**: Given a KB-assembled resume using entry IDs [5, 12, 23, 41], When saved, Then `source_entry_ids='[5, 12, 23, 41]'` is stored as a JSON string.
- **AC-030-32-2**: Given an LLM-generated resume (no KB entries), When saved, Then `source_entry_ids` is NULL.
- **AC-030-32-3**: Given a resume_versions row with `source_entry_ids`, When the API returns version data, Then `source_entry_ids` is parsed from JSON and returned as a list.
- **AC-030-32-4**: Given an existing resume_versions row created before M4, Then `source_entry_ids` is NULL (backward compatible).

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

### NFR-030-11: [DEPRECATED - M4 Redesign] Template Rendering Latency (M3)

**Description**: ~~Jinja2 LaTeX template rendering (excluding PDF compilation) shall complete within 50ms for any built-in template with a standard context dict.~~ Superseded by ReportLab rendering in M4. ReportLab is stateless and instant; no performance concern.
**Metric**: ~~p95 latency < 50ms for template rendering~~ N/A
**Priority**: ~~P1~~ N/A (deprecated)
**Validation Method**: ~~Unit test measuring wall-clock time of `render_latex_template()` over 100 iterations~~ N/A

### NFR-030-12: [DEPRECATED - M4 Redesign] PDF Compilation Timeout (M3)

**Description**: ~~PDF compilation via pdflatex shall enforce a maximum timeout of 30 seconds (configurable via LatexConfig). If compilation exceeds the timeout, the subprocess is killed and a RuntimeError is raised.~~ Superseded by ReportLab in M4. ReportLab rendering is in-process and stateless; no subprocess timeout needed.
**Metric**: ~~Compilation killed and error raised within 1s of timeout expiry~~ N/A
**Priority**: ~~P0~~ N/A (deprecated)
**Validation Method**: ~~Unit test with mock subprocess that simulates hang~~ N/A

### NFR-030-13: [DEPRECATED - M4 Redesign] LaTeX Escaping Robustness (M3)

**Description**: ~~The `escape_latex()` function shall handle `None`, empty strings, and non-string inputs gracefully, returning an empty string without raising exceptions.~~ Superseded by LLM + ReportLab pipeline in M4. No LaTeX escaping needed.
**Metric**: ~~Zero exceptions for None, empty, int, float, or bool inputs~~ N/A
**Priority**: ~~P0~~ N/A (deprecated)
**Validation Method**: ~~Unit test with None, "", 0, 3.14, True inputs~~ N/A

### NFR-030-14: KB Assembly Latency (M4)

**Description**: KB-based resume assembly (entry retrieval, scoring, selection, and context dict construction) shall complete within 2 seconds, excluding LLM generation and ReportLab PDF rendering time.
**Metric**: p95 latency < 2s for assembly of 500-entry KB against a single JD
**Priority**: P1
**Validation Method**: Unit test with 500 pre-inserted KB entries, measure wall-clock time of `assemble_resume()` excluding LLM and PDF rendering

### NFR-030-15: Backward Compatibility (M4)

**Description**: Existing callers of `_generate_docs()`, `save_resume_version()`, and resume_versions API endpoints shall continue to work without modification. Callers that do not supply `reuse_source` or `source_entry_ids` fields shall receive NULL defaults. Existing resume_versions rows without the new columns shall be returned with `reuse_source=None` and `source_entry_ids=None`.
**Metric**: Zero breaking changes to existing bot loop, resume_versions API, or database queries
**Priority**: P0
**Validation Method**: Run existing test suite (`test_resume_versions.py`, `test_bot_loop.py`) with zero modifications — all must pass

---

## 5. Interface Requirements

### 5.1 Internal Interfaces (M1 — no external/UI interfaces, M2 — internal scoring APIs, M3 — DEPRECATED LaTeX APIs, M4 — LLM + ReportLab assembly + bot integration APIs)

| Module | Function | Direction | Consumers |
|--------|----------|-----------|-----------|
| core/document_parser | `extract_text(file_path)` | Called by KnowledgeBase | core/knowledge_base |
| core/knowledge_base | `KnowledgeBase.process_upload()` | Called by routes (M5) | routes/knowledge_base (M5) |
| core/knowledge_base | `KnowledgeBase.get_all_entries()` | Called by assembler (M4) | core/resume_assembler |
| core/knowledge_base | `KnowledgeBase.ingest_generated_resume()` | Called by bot (M4) | bot/bot.py |
| core/resume_parser | `parse_resume_md(md_text)` | Called by KnowledgeBase | core/knowledge_base |
| core/experience_calculator | `calculate_experience(db)` | Called by assembler (M4) | core/resume_assembler |
| core/ai_engine | `invoke_llm(prompt, config)` | Called by KnowledgeBase | core/knowledge_base |
| core/ai_engine | `generate_resume_from_kb(entries, jd_text, llm_config)` | Called by assembler (M4) | core/resume_assembler |
| db/database | KB CRUD methods | Called by KnowledgeBase | core/knowledge_base |
| core/resume_scorer | `score_kb_entries(jd_text, entries, config)` | Called by assembler (M4) | core/resume_assembler |
| core/resume_scorer | `compute_tfidf_score(jd_text, entry_text)` | Utility | Any module |
| core/jd_analyzer | `analyze_jd(text)` | Called by ResumeScorer | core/resume_scorer |
| core/jd_analyzer | `normalize_term(term)` | Called by ResumeScorer | core/resume_scorer |
| ~~core/latex_compiler~~ | ~~`escape_latex(text)`~~ | ~~Utility~~ | [DEPRECATED - M4 Redesign] |
| ~~core/latex_compiler~~ | ~~`find_pdflatex()`~~ | ~~Called by compile_pdf~~ | [DEPRECATED - M4 Redesign] |
| ~~core/latex_compiler~~ | ~~`render_latex_template(template_name, context)`~~ | ~~Called by compile_resume~~ | [DEPRECATED - M4 Redesign] |
| ~~core/latex_compiler~~ | ~~`compile_pdf(latex_source, timeout)`~~ | ~~Called by compile_resume~~ | [DEPRECATED - M4 Redesign] |
| ~~core/latex_compiler~~ | ~~`compile_resume(template_name, context, output_path)`~~ | ~~Called by assembler (M4)~~ | [DEPRECATED - M4 Redesign] |
| core/resume_renderer | `render_resume_to_pdf(resume_text, output_path)` | Called by assembler (M4) | core/resume_assembler |
| core/resume_assembler | `assemble_resume(jd_text, db, llm_config)` | Called by bot (M4) | bot/bot.py |
| bot/bot | `_generate_docs()` (modified) | Called by bot loop | bot/bot.py |
| db/database | `save_resume_version(..., reuse_source, source_entry_ids)` | Called by bot (M4) | bot/bot.py |
| routes/config | `upload_default_resume()` — POST /api/config/default-resume | Called by Dashboard UI | static/js/dashboard.js |
| routes/config | `get_default_resume()` — GET /api/config/default-resume | Called by Dashboard UI | static/js/dashboard.js |
| routes/config | `delete_default_resume()` — DELETE /api/config/default-resume | Called by Dashboard UI | static/js/dashboard.js |

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

- **LaTeX compilation**: Originally planned for M3, now SUPERSEDED by LLM + ReportLab pipeline in M4. LatexConfig exists in code but is DEPRECATED and not used in assembly.
- **Bot integration and resume assembly**: Covered in M4.
- **Frontend UI and API endpoints**: Deferred to M5 — M1-M4 are backend only.
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
| Jinja2 3.1.6 | Runtime | Available | ~~Required for M3 LaTeX templates~~ [DEPRECATED - M4 Redesign] |
| ReportLab | Runtime | Available | PRIMARY PDF renderer for M4 resume assembly |
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
| FR-030-20 | Derived | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py → Test: test_latex_compiler.py~~ |
| FR-030-21 | Derived | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py → Test: test_latex_compiler.py~~ |
| FR-030-22 | Derived | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py → Test: test_latex_compiler.py~~ |
| FR-030-23 | Derived | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py → Test: test_latex_compiler.py~~ |
| FR-030-24 | US-106 | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py, templates/*.tex → Test: test_latex_compiler.py~~ |
| FR-030-25 | Derived | [DEPRECATED - M4 Redesign] ~~Design: Distribution → Code: electron/scripts/bundle-tinytex.js → Test: manual~~ |
| FR-030-26 | Derived | [DEPRECATED - M4 Redesign] ~~Design: LatexCompiler → Code: core/latex_compiler.py → Test: test_latex_compiler.py~~ |
| FR-030-27 | US-102, US-106 | Design: ResumeAssembler → Code: core/resume_assembler.py, core/ai_engine.py, core/resume_renderer.py → Test: test_resume_assembler.py |
| FR-030-28 | US-102 | Design: ResumeAssembler → Code: core/resume_assembler.py → Test: test_resume_assembler.py |
| FR-030-29 | US-102 | Design: BotIntegration → Code: bot/bot.py → Test: test_bot_loop.py |
| FR-030-30 | US-105 | Design: BotIntegration → Code: bot/bot.py, core/knowledge_base.py → Test: test_bot_loop.py |
| FR-030-31 | Derived | Design: Database → Code: db/database.py → Test: test_resume_versions.py |
| FR-030-32 | Derived | Design: Database → Code: db/database.py → Test: test_resume_versions.py |
| FR-030-33 | US-107 | Design: KBRoutes → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-34 | US-107 | Design: KBRoutes → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-35 | US-108 | Design: KBRoutes → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-36 | US-108 | Design: KBRoutes → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-37 | US-109 | Design: KBRoutes → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-38 | US-110 | Design: KBUI → Code: static/js/knowledge-base.js → Test: manual |
| FR-030-39 | US-110 | Design: KBUI → Code: static/js/knowledge-base.js → Test: manual |
| FR-030-40 | US-111 | Design: PreviewUI → Code: static/js/resume-preview.js → Test: manual |
| FR-030-41 | US-111 | Design: PreviewUI → Code: routes/knowledge_base.py → Test: test_knowledge_base_routes.py |
| FR-030-42 | US-112 | Design: Navigation → Code: templates/index.html, static/js/navigation.js → Test: manual |

---

## 9. Milestone 5 — Upload UI + KB Viewer + Preview

### 9.1 User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-107 | As a user, I want to upload career documents (PDF/DOCX/TXT/MD) so that the system extracts KB entries automatically | Must |
| US-108 | As a user, I want to browse, search, filter, edit, and delete my KB entries | Must |
| US-109 | As a user, I want to see KB statistics (entry counts by category) | Should |
| US-110 | As a user, I want a KB viewer UI with upload zone, stats cards, entries table, pagination | Must |
| US-111 | As a user, I want to preview assembled resumes from my KB entries against a job description | Should |
| US-112 | As a user, I want a Knowledge Base tab in the navigation bar | Must |

### 9.2 Functional Requirements

#### FR-030-33: Upload API Endpoint
**Priority**: Must | **Source**: US-107

The system SHALL provide `POST /api/kb/upload` accepting multipart file uploads.

**Acceptance Criteria**:
- AC-030-33-1: Given a valid PDF/DOCX/TXT/MD file under 10 MB, When uploaded, Then entries are extracted and count returned with HTTP 201
- AC-030-33-2: Given no file in request, When POST /api/kb/upload called, Then HTTP 400 returned
- AC-030-33-3: Given an unsupported file type (.exe), When uploaded, Then HTTP 400 returned
- AC-030-33-4: Given a file exceeding 10 MB, When uploaded, Then HTTP 413 returned

#### FR-030-34: KB Stats Endpoint
**Priority**: Should | **Source**: US-109

The system SHALL provide `GET /api/kb/stats` returning entry counts by category.

**Acceptance Criteria**:
- AC-030-34-1: Given an empty KB, When GET /api/kb/stats called, Then 200 returned with zero counts
- AC-030-34-2: Given entries exist, When GET /api/kb/stats called, Then counts per category returned

#### FR-030-35: KB List Entries Endpoint
**Priority**: Must | **Source**: US-108

The system SHALL provide `GET /api/kb` with optional category, search, limit, offset params.

**Acceptance Criteria**:
- AC-030-35-1: Given entries exist, When GET /api/kb called, Then entries array returned with count
- AC-030-35-2: Given category=experience filter, When GET /api/kb?category=experience called, Then only experience entries returned
- AC-030-35-3: Given limit=2, When GET /api/kb?limit=2 called, Then at most 2 entries returned

#### FR-030-36: KB Entry CRUD Endpoints
**Priority**: Must | **Source**: US-108

The system SHALL provide GET/PUT/DELETE on `/api/kb/<id>`.

**Acceptance Criteria**:
- AC-030-36-1: Given an existing entry, When GET /api/kb/<id> called, Then entry details returned
- AC-030-36-2: Given a non-existent entry, When GET /api/kb/<id> called, Then HTTP 404 returned
- AC-030-36-3: Given valid JSON body, When PUT /api/kb/<id> called, Then entry updated and 200 returned
- AC-030-36-4: Given no JSON body, When PUT /api/kb/<id> called, Then HTTP 400 returned
- AC-030-36-5: Given an existing entry, When DELETE /api/kb/<id> called, Then soft-deleted and 200 returned

#### FR-030-37: Documents List Endpoint
**Priority**: Should | **Source**: US-109

The system SHALL provide `GET /api/kb/documents` listing all uploaded documents.

**Acceptance Criteria**:
- AC-030-37-1: Given no documents uploaded, When GET /api/kb/documents called, Then empty list returned

#### FR-030-38: KB Viewer Frontend Module
**Priority**: Must | **Source**: US-110

The system SHALL provide `static/js/knowledge-base.js` implementing KB viewer with stats, entries table, category filter, search, pagination, edit/delete overlays.

**Acceptance Criteria**:
- AC-030-38-1: Given KB entries exist, When KB screen loaded, Then stats cards and entries table rendered
- AC-030-38-2: Given category filter selected, When changed, Then table filters to that category
- AC-030-38-3: Given search text entered, When 300ms debounce elapsed, Then filtered results displayed
- AC-030-38-4: Given edit button clicked, When overlay opens, Then entry fields pre-populated for editing

#### FR-030-39: File Upload UI
**Priority**: Must | **Source**: US-110

The system SHALL provide file upload input in the KB screen with format validation and status feedback.

**Acceptance Criteria**:
- AC-030-39-1: Given a file selected, When upload button clicked, Then processing status shown and entries refreshed on success
- AC-030-39-2: Given upload fails, When error returned, Then error message displayed

#### FR-030-40: Resume Preview Frontend
**Priority**: Should | **Source**: US-111

The system SHALL provide `static/js/resume-preview.js` with template picker, JD textarea, and PDF iframe display.

**Acceptance Criteria**:
- AC-030-40-1: Given template and JD text provided, When preview clicked, Then PDF rendered in iframe
- AC-030-40-2: Given no JD text, When preview clicked, Then error message shown
- AC-030-40-3: Given preview overlay open, When Escape pressed, Then overlay closes

#### FR-030-41: Resume Preview API
**Priority**: Should | **Source**: US-111

The system SHALL provide `POST /api/kb/preview` accepting template, entry_ids or jd_text, returning PDF.

**Acceptance Criteria**:
- AC-030-41-1: Given no request body, When POST /api/kb/preview called, Then HTTP 400 returned
- AC-030-41-2: Given template only (no entry_ids or jd_text), When called, Then HTTP 400 returned

#### FR-030-42: KB Navigation Tab
**Priority**: Must | **Source**: US-112

The system SHALL add a "Knowledge Base" tab to the navigation bar linking to the KB screen.

**Acceptance Criteria**:
- AC-030-42-1: Given the nav bar, When rendered, Then "Knowledge Base" tab visible between "Resume Library" and "Settings"
- AC-030-42-2: Given KB tab clicked, When screen switches, Then loadKnowledgeBase() called

### 9.3 Non-Functional Requirements

#### NFR-030-16: i18n Coverage
All user-facing strings in KB routes and frontend SHALL use `t()` or `data-i18n` attributes. All keys SHALL exist in en.json and es.json.

#### NFR-030-17: Accessibility (WCAG 2.1 AA)
All KB UI elements SHALL have ARIA labels, roles, aria-live regions, keyboard navigation, and semantic HTML.

#### NFR-030-18: Input Validation
File uploads SHALL validate extension (allowlist), filename (sanitize), and size (10 MB max). All route params SHALL be validated.

---

## 10. Functional Requirements — M6: ATS Scoring + Platform Profiles

### 10.1 User Stories

| ID | As a… | I want to… | So that… | Priority |
|----|-------|-----------|----------|----------|
| US-113 | Job seeker | See an ATS compatibility score for my KB entries against a JD | I know how well my resume matches before applying | Must |
| US-114 | Job seeker | See which keywords and skills are missing from my resume | I can fill gaps before submitting | Must |
| US-115 | Job seeker | Select an ATS platform profile (Workday, Greenhouse, etc.) | Scoring weights match the ATS I'm applying through | Should |
| US-116 | Job seeker | View all available ATS profiles | I can pick the right one for each application | Should |

### 10.2 Functional Requirements

#### FR-030-43: ATS Composite Scoring Engine

The system SHALL compute a composite ATS compatibility score (0–100) from 5 weighted components: keyword match (35%), section completeness (20%), skill match (20%), content length (15%), and format compliance (10%).

**Acceptance Criteria**:
- AC-030-43-1: Given a JD and KB entries, When `score_ats()` called, Then returns score 0–100 with 5 component breakdowns
- AC-030-43-2: Given empty JD or entries, When scored, Then returns 0 with empty gap lists
- AC-030-43-3: Given well-matched entries, When scored, Then composite score >= 50

#### FR-030-44: Keyword and Skill Gap Analysis

The system SHALL identify matched and missing keywords/skills between JD and resume content, returning them as sorted lists.

**Acceptance Criteria**:
- AC-030-44-1: Given JD keywords present in resume, When scored, Then matched_keywords contains them
- AC-030-44-2: Given JD keywords absent from resume, When scored, Then missing_keywords contains them
- AC-030-44-3: Given JD tech terms, When scored, Then matched_skills and missing_skills populated

#### FR-030-45: ATS Platform Profiles

The system SHALL define platform-specific scoring weight profiles for at least 6 ATS vendors (Greenhouse, Lever, Workday, Ashby, iCIMS, Taleo) plus a default profile.

**Acceptance Criteria**:
- AC-030-45-1: Given any profile, When weights retrieved, Then they sum to 1.0
- AC-030-45-2: Given unknown platform name, When profile requested, Then default profile returned
- AC-030-45-3: Given "workday", When weights compared to default, Then keyword_match weight is higher

#### FR-030-46: ATS Score API Endpoint

The system SHALL expose `POST /api/kb/ats-score` accepting `jd_text`, optional `platform`, and optional `entry_ids`, returning composite score + gap analysis.

**Acceptance Criteria**:
- AC-030-46-1: Given valid JD text and KB entries, When POST, Then 200 with score and gap data
- AC-030-46-2: Given missing jd_text, When POST, Then 400 error
- AC-030-46-3: Given empty KB, When POST, Then 400 error
- AC-030-46-4: Given platform="workday", When POST, Then response includes platform="workday"

#### FR-030-47: ATS Profiles List Endpoint

The system SHALL expose `GET /api/kb/ats-profiles` returning all available ATS platform profiles.

**Acceptance Criteria**:
- AC-030-47-1: Given GET request, When called, Then 200 with profiles array containing >= 7 entries
- AC-030-47-2: Given each profile, When listed, Then includes id, name, description fields

#### FR-030-48: ATS Scoring UI

The system SHALL provide a frontend ATS scoring card with platform selector, JD textarea, analyze button, and results display (score badge, component bars, gap badges).

**Acceptance Criteria**:
- AC-030-48-1: Given ATS card rendered, When user selects platform and enters JD, Then analyze button enabled
- AC-030-48-2: Given analyze clicked, When score returned, Then score badge color-coded (green >= 70, yellow >= 40, red < 40)
- AC-030-48-3: Given missing keywords/skills, When displayed, Then shown as badge elements

### 10.3 Non-Functional Requirements

#### NFR-030-19: ATS i18n Coverage
All ATS UI strings SHALL use `data-i18n` attributes. All keys SHALL exist in en.json and es.json `ats` section.

#### NFR-030-20: ATS Accessibility
The ATS scoring card SHALL have ARIA labels, aria-live region for results, semantic HTML, and keyboard-accessible controls.

### 10.4 Traceability Seeds

| FR | → Design | → Source | → Test |
|----|----------|----------|--------|
| FR-030-43 | SAD §3.31 | `core/ats_scorer.py` | `test_ats_scorer.py::TestScoreATS` |
| FR-030-44 | SAD §3.31 | `core/ats_scorer.py` | `test_ats_scorer.py::TestKeywordMatch, TestSkillMatch` |
| FR-030-45 | SAD §3.32 | `core/ats_profiles.py` | `test_ats_scorer.py::TestATSProfiles` |
| FR-030-46 | SAD §3.31, IC-028 | `routes/knowledge_base.py` | `test_ats_scorer.py::TestATSEndpoint` |
| FR-030-47 | SAD §3.32, IC-029 | `routes/knowledge_base.py` | `test_ats_scorer.py::TestATSProfilesEndpoint` |
| FR-030-48 | SAD §3.33 | `static/js/knowledge-base.js` | — |

---

## 11. Functional Requirements — M7: Manual Resume Builder

### 11.1 User Stories

| ID | As a… | I want to… | So that… | Priority |
|----|-------|-----------|----------|----------|
| US-117 | Job seeker | Drag and drop KB entries to build a custom resume | I have full control over which content appears | Must |
| US-118 | Job seeker | Save resume entry combinations as named presets | I can quickly reuse configurations for similar roles | Must |
| US-119 | Job seeker | See a one-page indicator while building | I know when my resume exceeds 1 page | Should |
| US-120 | Job seeker | Auto-fill the builder from a job description | The system pre-selects the best entries for me to review | Should |

### 11.2 Functional Requirements

#### FR-030-49: Resume Presets CRUD

The system SHALL support creating, listing, updating, and deleting named resume presets that store entry ID combinations and template choice.

**Acceptance Criteria**:
- AC-030-49-1: Given valid name and entry_ids, When POST /api/kb/presets, Then 201 with preset data
- AC-030-49-2: Given missing name or entry_ids, When POST, Then 400 error
- AC-030-49-3: Given existing presets, When GET /api/kb/presets, Then returns all presets
- AC-030-49-4: Given valid preset ID, When PUT, Then preset updated
- AC-030-49-5: Given valid preset ID, When DELETE, Then preset removed

#### FR-030-50: Resume Presets Database Table

The system SHALL store presets in a `resume_presets` table with id, name, entry_ids (JSON), template, created_at, updated_at columns.

**Acceptance Criteria**:
- AC-030-50-1: Given new DB, When schema initialized, Then resume_presets table exists
- AC-030-50-2: Given preset saved, When retrieved, Then all fields populated correctly

#### FR-030-51: Drag-and-Drop Resume Builder UI

The system SHALL provide a full-screen overlay with a left panel (KB entries with search/filter) and right panel (resume sections with drop zones) supporting drag-and-drop entry selection.

**Acceptance Criteria**:
- AC-030-51-1: Given builder opened, When rendered, Then left panel shows KB entries grouped by category
- AC-030-51-2: Given entry dragged to drop zone, When dropped, Then entry appears in that section
- AC-030-51-3: Given entry in section, When remove clicked, Then entry returns to available pool

#### FR-030-52: Entry Reorder in Builder

The system SHALL allow reordering entries within a resume section using up/down controls.

**Acceptance Criteria**:
- AC-030-52-1: Given multiple entries in a section, When up arrow clicked, Then entry moves up
- AC-030-52-2: Given entry at top, When up arrow clicked, Then button is disabled

#### FR-030-53: One-Page Mode with Line Estimation

The system SHALL estimate page count based on entry word counts and display a live page indicator. In one-page mode, it SHALL warn when content exceeds estimated 1-page limit.

**Acceptance Criteria**:
- AC-030-53-1: Given entries selected, When page indicator updates, Then shows estimated page count
- AC-030-53-2: Given one-page mode enabled and >55 estimated lines, Then warning displayed

#### FR-030-54: Auto-Fill from Job Description

The system SHALL allow pasting a JD to auto-select the best-matching KB entries using ATS keyword scoring, with per-category limits.

**Acceptance Criteria**:
- AC-030-54-1: Given JD text entered, When auto-fill clicked, Then entries selected based on keyword match
- AC-030-54-2: Given auto-fill, When complete, Then per-category limits respected (e.g., max 5 experience)

### 11.3 Non-Functional Requirements

#### NFR-030-21: Builder i18n Coverage
All builder UI strings SHALL use `data-i18n` attributes. All keys SHALL exist in en.json and es.json `builder` section.

#### NFR-030-22: Builder Accessibility
The builder SHALL have ARIA labels on all panels, drop zones, buttons, and live regions. Keyboard navigation SHALL work for add/remove/reorder operations.

### 11.4 Traceability Seeds

| FR | → Design | → Source | → Test |
|----|----------|----------|--------|
| FR-030-49 | SAD §3.35, IC-030/031/032 | `routes/knowledge_base.py`, `db/database.py` | `test_resume_builder.py::TestPresetsAPI` |
| FR-030-50 | SAD §3.35 | `db/database.py` | `test_resume_builder.py::TestPresetDB` |
| FR-030-51 | SAD §3.36 | `static/js/resume-builder.js` | — |
| FR-030-52 | SAD §3.36 | `static/js/resume-builder.js` | — |
| FR-030-53 | SAD §3.36 | `static/js/resume-builder.js` | — |
| FR-030-54 | SAD §3.36 | `static/js/resume-builder.js` | — |

---

## 12. Milestone 8 — Performance (PDF Cache, JD Classifier, Async Upload)

### 12.1 Scope
Performance optimizations: PDF compilation cache to avoid recompiling identical LaTeX, JD classifier for pre-filtering KB entries, async document upload with background processing and status polling.

### 12.2 Functional Requirements

#### FR-030-55: PDF Compilation Cache
The system SHALL cache compiled PDF bytes keyed by a SHA256[:16] hash of LaTeX content, returning cached PDFs on cache hit.

**Acceptance Criteria**:
- AC-030-55-1: Given identical LaTeX content, When compile_latex called twice, Then second call returns cached bytes without invoking pdflatex
- AC-030-55-2: Given cache disabled (use_cache=False), When compile_latex called, Then cache is bypassed entirely

#### FR-030-56: PDF Cache LRU Eviction
The system SHALL evict oldest cached PDFs when cache exceeds MAX_CACHE_SIZE (200), based on file modification time.

**Acceptance Criteria**:
- AC-030-56-1: Given 205 cached PDFs, When evict_lru called, Then 5 oldest are removed
- AC-030-56-2: Given fewer than MAX_CACHE_SIZE PDFs, When evict_lru called, Then 0 files removed

#### FR-030-57: PDF Cache Management
The system SHALL provide clear_cache() and cache_stats() functions for cache administration.

**Acceptance Criteria**:
- AC-030-57-1: Given 3 cached PDFs, When clear_cache called, Then all 3 removed, returns count 3
- AC-030-57-2: Given cached PDFs, When cache_stats called, Then returns count, size_bytes, size_mb, max_size, cache_dir

#### FR-030-58: JD Classification
The system SHALL classify job descriptions into job types (backend, frontend, fullstack, data_engineer, data_scientist, ml_engineer, devops, mobile, security) using keyword matching, sorted by match count descending.

**Acceptance Criteria**:
- AC-030-58-1: Given JD with "Python, Django, REST API, PostgreSQL", When classify_jd called, Then "backend" is in result
- AC-030-58-2: Given JD with no matching keywords, When classify_jd called, Then returns ["general"]
- AC-030-58-3: Given empty JD text, When classify_jd called, Then returns ["general"]

#### FR-030-59: JD Type Expansion
The system SHALL expand primary job types to include related types (e.g., backend → fullstack, devops) without duplicates.

**Acceptance Criteria**:
- AC-030-59-1: Given primary type ["backend"], When get_relevant_types called, Then result includes "fullstack" and "devops"
- AC-030-59-2: Given overlapping types, When expanded, Then no duplicates in result

#### FR-030-60: KB Entry Pre-Filtering by Job Type
The system SHALL filter KB entries by job type match, with fallback to all entries when fewer than min_entries match.

**Acceptance Criteria**:
- AC-030-60-1: Given entries with job_types, When filtered by ["backend"], Then only matching + universal entries returned
- AC-030-60-2: Given fewer than min_entries matching, When filtered, Then all entries returned as fallback

#### FR-030-61: Async Document Upload
The system SHALL accept document uploads via POST /api/kb/upload/async, return a task_id immediately (202), and process in a background thread.

**Acceptance Criteria**:
- AC-030-61-1: Given valid file upload, When POST /api/kb/upload/async, Then returns 202 with task_id and status "processing"
- AC-030-61-2: Given no file in request, When POST /api/kb/upload/async, Then returns 400

#### FR-030-62: Upload Status Polling
The system SHALL provide GET /api/kb/upload/status/<task_id> to poll async upload task status, returning current status, entries_created, and error if any.

**Acceptance Criteria**:
- AC-030-62-1: Given valid task_id with completed task, When GET /api/kb/upload/status/<id>, Then returns status "completed" with entries_created
- AC-030-62-2: Given unknown task_id, When GET /api/kb/upload/status/<id>, Then returns 404

### 12.3 Non-Functional Requirements

#### NFR-030-23: Cache Performance
Cache lookup SHALL complete in < 5ms for hits. Cache directory SHALL be created lazily on first use.

#### NFR-030-24: Thread Safety
Async upload task tracking SHALL use threading.Lock for concurrent access to the shared task dict.

### 12.4 Traceability Seeds

| FR | → Design | → Source | → Test |
|----|----------|----------|--------|
| FR-030-55 | SAD §3.38 | `core/pdf_cache.py`, `core/latex_compiler.py` | `test_performance.py::TestPDFCache`, `TestLatexCompilerCache` |
| FR-030-56 | SAD §3.38 | `core/pdf_cache.py` | `test_performance.py::TestPDFCache::test_evict_lru_*` |
| FR-030-57 | SAD §3.38 | `core/pdf_cache.py` | `test_performance.py::TestPDFCache::test_clear_cache`, `test_cache_stats` |
| FR-030-58 | SAD §3.39 | `core/jd_classifier.py` | `test_performance.py::TestJDClassifier::test_classify_*` |
| FR-030-59 | SAD §3.39 | `core/jd_classifier.py` | `test_performance.py::TestJDClassifier::test_get_relevant_*` |
| FR-030-60 | SAD §3.39 | `core/jd_classifier.py` | `test_performance.py::TestJDClassifier::test_filter_*` |
| FR-030-61 | SAD §3.40, IC-033 | `routes/knowledge_base.py` | `test_performance.py::TestAsyncUpload::test_async_upload_*` |
| FR-030-62 | SAD §3.40, IC-034 | `routes/knowledge_base.py` | `test_performance.py::TestAsyncUpload::test_upload_status_*` |

---

## 13. Milestone 9 — Intelligence (Outcome Learning, CL Assembly, Reuse Stats)

### 13.1 Scope
User intelligence features: outcome-based learning (effectiveness_score from interview feedback), cover letter KB assembly (0 API calls), reuse stats analytics, and JD classifier integration into the resume assembler pipeline.

### 13.2 Functional Requirements

#### FR-030-63: KB Usage Logging
The system SHALL log each KB entry's usage when selected for a resume assembly, tracking entry_id, application_id, and TF-IDF score. Usage count and last_used_at SHALL be updated on the knowledge_base table.

**Acceptance Criteria**:
- AC-030-63-1: Given a resume assembled from 5 KB entries, When log_kb_usage called, Then 5 rows inserted into kb_usage_log and usage_count incremented on each entry

#### FR-030-64: Outcome Feedback
The system SHALL accept outcome feedback (interview/rejected/no_response) for an application and update all associated kb_usage_log rows. For "interview" outcomes, effectiveness_score SHALL be recalculated as interviews/total_uses.

**Acceptance Criteria**:
- AC-030-64-1: Given application with 3 KB entries, When outcome "interview" submitted, Then all 3 log rows updated and effectiveness_score = 1.0
- AC-030-64-2: Given entry used twice (1 interview, 1 rejection), When both outcomes recorded, Then effectiveness_score = 0.5

#### FR-030-65: Effectiveness Ranking
The system SHALL provide GET /api/kb/effectiveness returning KB entries ranked by effectiveness_score descending, limited to entries with usage_count > 0.

**Acceptance Criteria**:
- AC-030-65-1: Given entries with varying effectiveness, When GET /api/kb/effectiveness, Then returns entries sorted by score DESC

#### FR-030-66: Feedback API Endpoint
The system SHALL provide POST /api/kb/feedback accepting {application_id, outcome} and updating outcomes via update_kb_outcome().

**Acceptance Criteria**:
- AC-030-66-1: Given valid application_id and outcome "interview", When POST /api/kb/feedback, Then returns success with updated count
- AC-030-66-2: Given invalid outcome value, When POST /api/kb/feedback, Then returns 400

#### FR-030-67: Cover Letter KB Assembly
The system SHALL assemble cover letters from KB entries scored against a JD using template-based generation, requiring no LLM API calls. Requires at least 2 experience entries above threshold.

**Acceptance Criteria**:
- AC-030-67-1: Given sufficient KB entries, When assemble_cover_letter called, Then returns formatted cover letter with greeting, intro, body, closing
- AC-030-67-2: Given empty KB, When assemble_cover_letter called, Then returns None

#### FR-030-68: Reuse Stats Analytics
The system SHALL provide GET /api/analytics/reuse-stats returning aggregate KB assembly metrics: total_assemblies, total_entries_used, unique_entries_used, interviews_from_kb, avg_effectiveness, top_categories.

**Acceptance Criteria**:
- AC-030-68-1: Given usage log data, When GET /api/analytics/reuse-stats, Then returns all 6 metrics accurately

#### FR-030-69: JD Classifier Integration
The resume assembler SHALL pre-filter KB entries using the JD classifier before TF-IDF scoring, narrowing entries to those matching the detected job type(s) plus related types.

**Acceptance Criteria**:
- AC-030-69-1: Given a backend-focused JD, When assemble_resume called, Then classify_jd is called to pre-filter entries

#### FR-030-70: Effectiveness Weighting in Scoring
The TF-IDF scorer SHALL blend effectiveness_score into final entry scores using weighted formula: (tfidf × 0.7) + (effectiveness × 0.3), only when effectiveness > 0.

**Acceptance Criteria**:
- AC-030-70-1: Given entry with effectiveness_score=0.9, When scored, Then final score is boosted
- AC-030-70-2: Given entry without effectiveness_score, When scored, Then original TF-IDF score used

### 13.3 Non-Functional Requirements

#### NFR-030-25: Migration Safety
Schema migration for effectiveness columns SHALL use PRAGMA table_info check before ALTER TABLE to handle existing databases safely.

#### NFR-030-26: SQL Parameterization
All new database queries SHALL use parameterized SQL (? placeholders). No string interpolation in SQL.

### 13.4 Traceability Seeds

| FR | → Design | → Source | → Test |
|----|----------|----------|--------|
| FR-030-63 | SAD §3.42 | `db/database.py` | `test_intelligence.py::TestKBUsageLog::test_log_*` |
| FR-030-64 | SAD §3.42 | `db/database.py` | `test_intelligence.py::TestKBUsageLog::test_update_outcome_*` |
| FR-030-65 | SAD §3.42, IC-036 | `db/database.py`, `routes/knowledge_base.py` | `test_intelligence.py::TestEffectivenessAPI` |
| FR-030-66 | SAD §3.42, IC-035 | `routes/knowledge_base.py` | `test_intelligence.py::TestFeedbackAPI` |
| FR-030-67 | SAD §3.43 | `core/cover_letter_assembler.py` | `test_intelligence.py::TestCoverLetterAssembly` |
| FR-030-68 | SAD §3.44, IC-037 | `db/database.py`, `routes/analytics.py` | `test_intelligence.py::TestReuseStatsAPI` |
| FR-030-69 | SAD §3.44 | `core/resume_assembler.py` | `test_intelligence.py::TestAssemblerJDPreFilter` |
| FR-030-70 | SAD §3.44 | `core/resume_scorer.py` | `test_intelligence.py::TestEffectivenessWeighting` |

---

## 14. Milestone 10 — Migration + Polish

### 14.1 Functional Requirements

#### FR-030-71: Migration Marker File
The system SHALL track KB migration state via a `.kb_migrated` marker file in the data directory.
- **AC-071-1 (positive)**: `needs_migration()` returns True when marker file does not exist.
- **AC-071-2 (positive)**: `needs_migration()` returns False after `mark_migrated()` is called.
- **AC-071-3 (positive)**: `mark_migrated()` creates `.kb_migrated` file in data directory.

#### FR-030-72: Experience File Migration
The system SHALL auto-migrate `.txt` experience files into KB entries.
- **AC-072-1 (positive)**: Lines starting with `-` or `*` are parsed as individual entries.
- **AC-072-2 (positive)**: Lines shorter than 5 characters are skipped.
- **AC-072-3 (positive)**: `README.txt` files are skipped.
- **AC-072-4 (positive)**: Returns 0 when directory does not exist or is empty.
- **AC-072-5 (positive)**: Multiple files processed with correct cumulative count.

#### FR-030-73: Resume File Migration
The system SHALL auto-migrate `.md` resume files into KB entries using `parse_resume_md`.
- **AC-073-1 (positive)**: Markdown resumes parsed into categorized KB entries.
- **AC-073-2 (positive)**: All migrated entries tagged with `"migrated"`.
- **AC-073-3 (positive)**: Returns 0 when directory does not exist or is empty.

#### FR-030-74: Full Migration Pipeline
`run_migration()` SHALL orchestrate txt + md migration and mark completion.
- **AC-074-1 (positive)**: Skips migration if already migrated (returns `{migrated: false, skipped_reason: "already_migrated"}`).
- **AC-074-2 (positive)**: Processes both experience and resume directories.
- **AC-074-3 (positive)**: Creates marker even when no files found.
- **AC-074-4 (positive)**: Returns counts of txt and md entries.

#### FR-030-75: Category Guessing
`_guess_category()` SHALL classify text into experience/skill/education/certification using keyword heuristics.
- **AC-075-1 (positive)**: Certification keywords detected (certified, certification, license).
- **AC-075-2 (positive)**: Education keywords detected (bachelor, master, degree, university).
- **AC-075-3 (positive)**: Skill keywords detected (proficient, python, frameworks).
- **AC-075-4 (positive)**: Defaults to "experience" when no keywords match.

#### FR-030-76: LaTeX Backslash Escaping
`escape_latex()` SHALL handle backslash characters without double-escaping braces.
- **AC-076-1 (positive)**: Backslash converted to `\textbackslash{}`.
- **AC-076-2 (positive)**: All 9 special characters (`& % $ # _ { } ~ ^`) properly escaped.
- **AC-076-3 (positive)**: Empty string returns empty string.
- **AC-076-4 (positive)**: Mixed backslash and special chars produce correct output.
- **AC-076-5 (negative)**: Single backslash does not produce doubled `\textbackslash{}`.

#### FR-030-77: Dashboard Automation Toggles

**Priority**: HIGH
**Description**: The Dashboard bot control card SHALL include toggles for "Adaptive Resume" and "Cover Letter" that persist to config immediately on change.

**Acceptance Criteria**:
- **AC-077-1 (positive)**: "Adaptive Resume" checkbox controls `resume_reuse.enabled` via PUT /api/config.
- **AC-077-2 (positive)**: "Cover Letter" checkbox controls `bot.cover_letter_enabled` via PUT /api/config.
- **AC-077-3 (positive)**: Toggle state loads from GET /api/config when Dashboard screen is shown.
- **AC-077-4 (positive)**: When Adaptive Resume is off, `_try_kb_assembly()` returns None (bot uses fallback).
- **AC-077-5 (positive)**: When Cover Letter is off, `generate_documents()` is called with `skip_cover_letter=True`.
- **AC-077-6 (positive)**: i18n keys `settings.adaptive_resume` and `settings.cover_letter` in en.json and es.json.

#### FR-030-78: Default Resume Upload API

**Priority**: HIGH
**Description**: The system SHALL provide endpoints to upload, retrieve, and delete a default/fallback resume file.

**Acceptance Criteria**:
- **AC-078-1 (positive)**: POST /api/config/default-resume accepts multipart file upload (PDF or DOCX, max 5 MB).
- **AC-078-2 (positive)**: File saved to `~/.autoapply/default_resume.{ext}`, path stored in `profile.fallback_resume_path`.
- **AC-078-3 (positive)**: GET /api/config/default-resume returns `{filename, path}` or `{filename: null, path: null}`.
- **AC-078-4 (positive)**: DELETE /api/config/default-resume removes file from disk and clears config path.
- **AC-078-5 (negative)**: Rejects unsupported file types with 400 error.
- **AC-078-6 (negative)**: Rejects files > 5 MB with 400 error.

#### FR-030-79: Default Resume Dashboard UI

**Priority**: MEDIUM
**Description**: The Dashboard SHALL show the current default resume filename with upload and remove controls.

**Acceptance Criteria**:
- **AC-079-1 (positive)**: "Default Resume: {filename}" label shown in bot-toggles area.
- **AC-079-2 (positive)**: Upload button triggers file picker (PDF/DOCX only).
- **AC-079-3 (positive)**: After upload, filename updates and remove (X) button appears.
- **AC-079-4 (positive)**: Remove button calls DELETE endpoint and resets display to "None".
- **AC-079-5 (positive)**: State loads via GET /api/config/default-resume on dashboard switch.

#### FR-030-80: KB Page Layout Restructure

**Priority**: LOW
**Description**: The Knowledge Base page SHALL organize sections with tools above the entries database.

**Acceptance Criteria**:
- **AC-080-1 (positive)**: Page layout: Stats cards → ATS + Smart Resume Assembly → Resume Builder + Documents → KB Entries.
- **AC-080-2 (positive)**: Upload control inside "Uploaded Documents" card (not in toolbar).
- **AC-080-3 (positive)**: Resume Templates section removed.
- **AC-080-4 (positive)**: Preview popup uses fixed overlay (z-index 1000) with dark background, Close and Download PDF buttons.

### 14.2 Non-Functional Requirements

#### NFR-030-27: Structured Logging (M10)
All M10 modules SHALL use `logging.getLogger(__name__)` with `%s` formatting. No silent exception swallowing.

#### NFR-030-28: Test Coverage (M10)
M10 SHALL include ≥25 unit tests covering all new functions, error paths, and edge cases.

### 14.3 Traceability Seeds

| FR | → Design | → Source | → Test |
|----|----------|----------|--------|
| FR-030-71 | SAD §3.46 | `core/kb_migrator.py` | `test_migration.py::TestMigrationMarker` |
| FR-030-72 | SAD §3.46 | `core/kb_migrator.py` | `test_migration.py::TestMigrateExperienceFiles` |
| FR-030-73 | SAD §3.46 | `core/kb_migrator.py` | `test_migration.py::TestMigrateResumeFiles` |
| FR-030-74 | SAD §3.46 | `core/kb_migrator.py` | `test_migration.py::TestRunMigration` |
| FR-030-75 | SAD §3.46 | `core/kb_migrator.py` | `test_migration.py::TestCategoryGuessing` |
| FR-030-76 | SAD §3.47 | `core/latex_compiler.py` | `test_migration.py::TestLatexEscapingHardening` |
| FR-030-77 | Derived | `static/js/dashboard.js`, `routes/config.py` | `test_config_routes.py::TestDashboardToggles` |
| FR-030-78 | Derived | `routes/config.py` | `test_config_routes.py::TestDefaultResumeAPI` |
| FR-030-79 | Derived | `static/js/dashboard.js`, `templates/index.html` | manual |
| FR-030-80 | Derived | `static/js/knowledge-base.js`, `templates/index.html` | manual |

---

## Software Requirements Specification -- GATE 3 OUTPUT

**Document**: SRS-TASK-030-smart-resume-reuse
**FRs**: 80 functional requirements (12 M1 + 7 M2 + 7 M3 + 6 M4 + 10 M5 + 6 M6 + 6 M7 + 8 M8 + 8 M9 + 10 M10)
**NFRs**: 28 non-functional requirements (6 M1 + 4 M2 + 3 M3 + 2 M4 + 3 M5 + 2 M6 + 2 M7 + 2 M8 + 2 M9 + 2 M10)
**ACs**: 263 total acceptance criteria (227 positive + 36 negative)
**Quality Checklist**: 48/48 items passed (100%)

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| System Engineer | Full SRS for architecture design |
| Unit Tester | ACs for test case generation |
| Integration Tester | NFRs for performance test planning |
| Security Engineer | Security NFRs + compliance constraints |
| Documenter | Feature descriptions for user docs |
