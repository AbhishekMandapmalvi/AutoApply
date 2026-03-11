# System Architecture Document

**Document ID**: SAD-TASK-030-smart-resume-reuse
**Version**: 1.0
**Date**: 2026-03-11
**Status**: approved
**Author**: Claude (System Engineer)
**SRS Reference**: SRS-TASK-030-smart-resume-reuse

---

## 1. Executive Summary

This architecture defines the M1 foundation for the Smart Resume Reuse feature: a Knowledge Base pipeline that extracts structured career entries from uploaded documents via a single LLM call and stores them in SQLite for later assembly (M2+). The design introduces 4 new Python modules, 3 new SQLite tables, 2 new config models, and extends the existing Database class with 13 new methods. All components follow the existing layer architecture and integrate via the established patterns (SQLite, Pydantic, structured logging).

## 2. Architecture Overview

### 2.1 Component Diagram

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ DocumentParser   │─────▶│ KnowledgeBase    │─────▶│ Database         │
│ (text extraction)│      │ (orchestrator)   │      │ (SQLite CRUD)    │
│ [PyPDF2/docx]   │      │ [core logic]     │      │ [sqlite3]        │
└─────────────────┘      └────────┬─────────┘      └─────────────────┘
                                  │                         ▲
                          ┌───────┴────────┐                │
                          ▼                ▼                │
                 ┌──────────────┐  ┌──────────────┐        │
                 │ AI Engine    │  │ ResumeParser  │        │
                 │ (LLM call)   │  │ (md → entries)│        │
                 │ [invoke_llm] │  │ [regex]       │        │
                 └──────────────┘  └──────────────┘        │
                                                            │
                 ┌──────────────┐                           │
                 │ Experience   │───────────────────────────┘
                 │ Calculator   │
                 │ [date math]  │
                 └──────────────┘

                 ┌──────────────┐
                 │ Config Models│  (ResumeReuseConfig, LatexConfig)
                 │ [Pydantic]   │
                 └──────────────┘
```

### 2.2 Data Flow

**Upload Pipeline (process_upload)**:
1. File enters via `process_upload(file_path, llm_config)`
2. `DocumentParser.extract_text()` reads file → plain text string
3. `Database.save_uploaded_document()` persists upload metadata + raw text
4. `KnowledgeBase._extract_via_llm()` sends text to cloud LLM → JSON array of entries
5. `KnowledgeBase._insert_entries()` inserts valid entries into KB with dedup

**Resume Ingestion Pipeline (ingest_generated_resume)**:
1. Markdown resume path enters via `ingest_generated_resume(path)`
2. File read as UTF-8 string
3. `ResumeParser.parse_resume_md()` splits by headings → list of entry dicts
4. `KnowledgeBase.ingest_entries()` inserts into KB with dedup

**Experience Calculation**:
1. `calculate_experience(db)` reads all roles from DB
2. Parses date strings, calculates durations in months
3. Aggregates by domain → returns total_years + by_domain dict

### 2.3 Layer Architecture

| Layer | Responsibility | Components |
|-------|---------------|------------|
| Service | Business logic, orchestration | `KnowledgeBase`, `calculate_experience()` |
| Domain | Pure data parsing, no I/O | `parse_resume_md()`, `_parse_date()`, config models |
| Repository | Data access | `Database` (KB CRUD methods) |
| Infrastructure | External calls, filesystem | `extract_text()`, `invoke_llm()` |

### 2.4 Component Catalog

| Component | Responsibility | Technology | Layer | File |
|-----------|---------------|------------|-------|------|
| DocumentParser | Extract text from PDF/DOCX/TXT/MD | PyPDF2, python-docx, stdlib | Infrastructure | `core/document_parser.py` |
| KnowledgeBase | Orchestrate upload pipeline, CRUD delegation | stdlib | Service | `core/knowledge_base.py` |
| ResumeParser | Parse markdown resumes into entry dicts | regex, stdlib | Domain | `core/resume_parser.py` |
| ExperienceCalculator | Calculate years of experience from roles | datetime, stdlib | Domain | `core/experience_calculator.py` |
| Database (extended) | SQLite CRUD for KB, documents, roles | sqlite3 | Repository | `db/database.py` |
| ResumeReuseConfig | Resume reuse settings | Pydantic | Domain | `config/settings.py` |
| LatexConfig | LaTeX compilation settings | Pydantic | Domain | `config/settings.py` |
| LatexCompiler | LaTeX escaping, template rendering, PDF compilation | Jinja2, subprocess | Infrastructure | `core/latex_compiler.py` |
| LaTeX Templates | 4 resume templates with custom Jinja2 delimiters | Jinja2 (.tex.j2) | Infrastructure | `templates/latex/*.tex.j2` |
| TinyTeX Bundler | Platform-specific TinyTeX download and packaging | Node.js | Infrastructure | `electron/scripts/bundle-tinytex.js` |

---

## 3. Interface Contracts

### 3.1 document_parser.extract_text()

**Purpose**: Extract plain text from an uploaded career document.
**Category**: query (reads)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| file_path | Path | yes | Must exist, extension in SUPPORTED_EXTENSIONS | Path to document file |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | str | no | Extracted plain text content |

Errors:
| Error Condition | Error Type | HTTP Status |
|----------------|------------|-------------|
| File not found | FileNotFoundError | N/A |
| Unsupported extension | ValueError | N/A |
| Missing PyPDF2 | RuntimeError | N/A |
| Missing python-docx | RuntimeError | N/A |

**Preconditions**: File must exist on disk.
**Postconditions**: Text returned; file not modified.
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (read-only).

---

### 3.2 KnowledgeBase.process_upload()

**Purpose**: Full pipeline: extract text from file, store document record, call LLM, insert KB entries.
**Category**: command (mutates)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| file_path | Path | yes | Must exist, supported extension | Uploaded document path |
| llm_config | LLMConfig | yes | provider + api_key + model | LLM configuration |
| upload_dir | Path or None | no | default: None | Directory to copy file to |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | int | no | Count of entries inserted (0 if empty text or LLM failure) |

Errors:
| Error Condition | Error Type |
|----------------|------------|
| File not found | FileNotFoundError (from extract_text) |
| Unsupported type | ValueError (from extract_text) |
| LLM call failure | Caught internally, returns 0 |

**Preconditions**: Database initialized; LLM config has valid provider+key.
**Postconditions**: Document row in uploaded_documents; 0+ entries in knowledge_base.
**Side Effects**: LLM API call (1 call); file copy if upload_dir provided.
**Idempotency**: No — inserts document record each call (entries deduplicated).
**Thread Safety**: Safe (SQLite WAL + Database locking).

---

### 3.3 KnowledgeBase.get_all_entries()

**Purpose**: Query KB entries with optional filtering by category, active status, and text search.
**Category**: query

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| category | str or None | no | default: None | Filter by category |
| active_only | bool | no | default: True | Exclude soft-deleted entries |
| search | str or None | no | default: None | LIKE search on text field |
| limit | int | no | default: 500, max: 10000 | Result limit |
| offset | int | no | default: 0 | Pagination offset |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | list[dict] | no | List of entry dicts (id, category, text, subsection, job_types, tags, source_doc_id, is_active, created_at, updated_at) |

**Preconditions**: Database initialized.
**Postconditions**: No state change.
**Idempotency**: Yes.
**Thread Safety**: Safe.

---

### 3.4 KnowledgeBase.update_entry()

**Purpose**: Update text, subsection, job_types, or tags of a KB entry.
**Category**: command

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| entry_id | int | yes | Must be valid KB entry ID | Entry to update |
| text | str or None | no | Non-empty if provided | New text |
| subsection | str or None | no | | New subsection |
| job_types | str or None | no | JSON array string | New job types |
| tags | str or None | no | Comma-separated string | New tags |

Output:
| Field | Type | Description |
|-------|------|-------------|
| (return) | bool | True if entry found and updated, False if not found |

**Side Effects**: updated_at set to CURRENT_TIMESTAMP.
**Idempotency**: Yes (same update produces same state).

---

### 3.5 KnowledgeBase.soft_delete_entry()

**Purpose**: Soft-delete a KB entry by setting is_active=0.
**Category**: command

Input: `entry_id: int`
Output: `bool` (True if found, False if not)
**Side Effects**: is_active=0, updated_at set.
**Idempotency**: Yes.

---

### 3.6 resume_parser.parse_resume_md()

**Purpose**: Parse markdown-formatted resume into structured KB entry dicts.
**Category**: query (pure function, no I/O)

Input: `md_text: str`
Output: `list[dict]` with keys: category, text, subsection, job_types, tags

**Preconditions**: None.
**Postconditions**: No state change.
**Idempotency**: Yes.
**Thread Safety**: Safe (pure function).

---

### 3.7 experience_calculator.calculate_experience()

**Purpose**: Calculate total and per-domain years of experience from roles table.
**Category**: query

Input: `db: Database`
Output: `dict` with keys: total_years (float), by_domain (dict[str, float])

**Preconditions**: Database initialized.
**Postconditions**: No state change.
**Idempotency**: Yes.
**Thread Safety**: Safe (read-only DB query).

---

### 3.8 Database.save_kb_entry()

**Purpose**: Insert a KB entry with dedup on (category, text).
**Category**: command

Input: category, text, subsection, job_types, tags, source_doc_id
Output: `int | None` — new row ID if inserted, None if duplicate

**SQL**: `INSERT OR IGNORE INTO knowledge_base (...) VALUES (...)`

---

### 3.9 Database.save_uploaded_document()

**Purpose**: Insert an uploaded document record.
**Category**: command

Input: filename, file_type, file_path, raw_text, llm_provider, llm_model
Output: `int` — new row ID

---

### 3.10 Database.save_role()

**Purpose**: Insert a role record with dedup on (title, company, start_date).
**Category**: command

Input: title, company, start_date, end_date, domain, description
Output: `int | None` — new row ID if inserted, None if duplicate

---

### 3.11 resume_scorer.score_kb_entries() (M2)

**Purpose**: Score KB entries against a job description using TF-IDF cosine similarity with keyword boosting and optional ONNX blending.
**Category**: query (read-only, no side effects)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| jd_text | str | yes | Non-empty | Job description text |
| entries | list[dict] | yes | Each dict has 'id', 'text', 'category' | KB entry dicts |
| config | ResumeReuseConfig or None | no | default: None (uses min_score=0.60, method="auto") | Scoring configuration |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | list[dict] | no | Entry dicts with added 'score' (float) and 'scoring_method' (str) keys, sorted by score descending, filtered to >= min_score |

Errors:
| Error Condition | Error Type | HTTP Status |
|----------------|------------|-------------|
| Empty jd_text or entries | (no error) returns [] | N/A |

**Preconditions**: KB entries must have 'text' field.
**Postconditions**: No state change. Input entries not modified (new dicts created).
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (no shared mutable state).

---

### 3.12 jd_analyzer.analyze_jd() (M2)

**Purpose**: Analyze a job description to extract structured keyword data for scoring.
**Category**: query (pure function)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| text | str | yes | May be empty/None | Job description text |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| keywords | list[str] | no | All extracted keywords (normalized) |
| required_keywords | list[str] | no | Keywords from requirements section |
| preferred_keywords | list[str] | no | Keywords from preferred/nice-to-have section |
| tech_terms | list[str] | no | Recognized technology terms from TECH_TERMS dict |
| ngrams | list[str] | no | 2-3 word phrases |
| sections | dict[str, str] | no | Detected sections (requirements, preferred, responsibilities, benefits, about) |
| keyword_counts | dict[str, int] | no | Frequency counts per keyword |

**Preconditions**: None.
**Postconditions**: No state change.
**Idempotency**: Yes.
**Thread Safety**: Safe (pure function).

---

### 3.13 jd_analyzer.normalize_term() (M2)

**Purpose**: Normalize a technology term using the synonym map.
**Category**: query (pure function)

Input: `term: str`
Output: `str` — canonical form (e.g., "JS" → "javascript", unknown terms lowered)

---

### 3.14 resume_scorer.compute_tfidf_score() (M2)

**Purpose**: Compute TF-IDF cosine similarity between a JD text and a single entry text. Utility function for testing and one-off scoring.
**Category**: query (pure function)

Input: `jd_text: str`, `entry_text: str`
Output: `float` in [0.0, 1.0]

---

### 3.15 latex_compiler.escape_latex() (M3)

**Purpose**: Escape special LaTeX characters in user-supplied text to prevent compilation errors.
**Category**: query (pure function)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| text | str or None | yes | May be None or empty | Raw text to escape |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | str | no | LaTeX-safe string with 9 special chars escaped (& → \&, % → \%, $ → \$, # → \#, _ → \_, { → \{, } → \}, ~ → \textasciitilde{}, ^ → \textasciicircum{}). Backslash is NOT escaped (preserved for LaTeX commands). Returns "" if input is None or empty. |

**Preconditions**: None.
**Postconditions**: No state change.
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (pure function).

---

### 3.16 latex_compiler.find_pdflatex() (M3)

**Purpose**: Discover pdflatex binary — first check bundled TinyTeX directory, then system PATH.
**Category**: query (filesystem read)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| bundled_dir | Path or None | no | default: None | Path to bundled TinyTeX directory (e.g., electron/tinytex/) |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | str or None | yes | Absolute path to pdflatex binary if found, None if not available |

**Discovery Order**:
1. If `bundled_dir` provided and `bundled_dir/bin/<platform>/pdflatex(.exe)` exists → return it
2. `shutil.which("pdflatex")` on system PATH → return if found
3. Return None (caller falls back to ReportLab PDF renderer)

**Preconditions**: None.
**Postconditions**: No state change.
**Side Effects**: None (filesystem stat only).
**Idempotency**: Yes.
**Thread Safety**: Safe (read-only filesystem checks).

---

### 3.17 latex_compiler.render_template() (M3)

**Purpose**: Render a Jinja2 LaTeX template with the given context using custom delimiters.
**Category**: query (filesystem read + string rendering)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| template_name | str | yes | Must match a .tex.j2 file in templates/latex/ | Template filename (e.g., "classic.tex.j2") |
| context | dict | yes | Keys: name, email, phone, location, summary, experiences, education, skills, certifications, projects | Template variables |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | str | no | Rendered LaTeX source string |

Errors:
| Error Condition | Error Type | HTTP Status |
|----------------|------------|-------------|
| Template not found | jinja2.TemplateNotFound | N/A |
| Render error | jinja2.TemplateSyntaxError | N/A |

**Jinja2 Environment Configuration** (see ADR-031):
- `block_start_string`: `\BLOCK{`
- `block_end_string`: `}`
- `variable_start_string`: `\VAR{`
- `variable_end_string`: `}`
- `comment_start_string`: `\#{`
- `comment_end_string`: `}`
- `autoescape`: False
- `loader`: FileSystemLoader pointing to `templates/latex/`

**Preconditions**: Template file exists in templates/latex/.
**Postconditions**: No state change.
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (Jinja2 Environment is thread-safe after creation).

---

### 3.18 latex_compiler.compile_latex() (M3)

**Purpose**: Compile raw LaTeX source into PDF bytes by invoking pdflatex in a temporary directory.
**Category**: command (subprocess + filesystem I/O)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| tex_content | str | yes | Non-empty, valid LaTeX | LaTeX source to compile |
| pdflatex_path | str or None | no | default: None (auto-discover via find_pdflatex()) | Path to pdflatex binary |
| timeout | int | no | default: 30 | Subprocess timeout in seconds |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | bytes or None | yes | PDF file bytes if compilation succeeds, None if pdflatex unavailable or compilation fails |

Errors:
| Error Condition | Error Type | HTTP Status |
|----------------|------------|-------------|
| pdflatex not found | (no error) returns None | N/A |
| Compilation failure | (no error) returns None, logs ERROR with stderr | N/A |
| Timeout exceeded | (no error) returns None, logs ERROR | N/A |

**Compilation Steps**:
1. Create temp directory via `tempfile.mkdtemp()`
2. Write `tex_content` to `resume.tex` in temp dir
3. Run `pdflatex -interaction=nonstopmode -halt-on-error resume.tex` (twice for references)
4. Read `resume.pdf` from temp dir → return bytes
5. Clean up temp dir in `finally` block

**Preconditions**: pdflatex binary available (bundled or system).
**Postconditions**: No persistent state change (temp dir cleaned up).
**Side Effects**: Subprocess execution, temp directory creation/deletion.
**Idempotency**: Yes (same input → same PDF bytes).
**Thread Safety**: Safe (uses isolated temp directories per call).

---

### 3.19 latex_compiler.compile_resume() (M3)

**Purpose**: High-level convenience function: render a template with context and compile to PDF bytes.
**Category**: command (combines render_template + compile_latex)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| template_name | str | yes | Must match a .tex.j2 file | Template name (e.g., "classic") — ".tex.j2" appended automatically |
| context | dict | yes | Same keys as render_template() | Template variables |
| pdflatex_path | str or None | no | default: None | Path to pdflatex binary |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | bytes or None | yes | PDF bytes if successful, None if pdflatex unavailable or compilation fails |

**Pipeline**:
1. Call `escape_latex()` on all string values in context (recursively for lists of dicts)
2. Call `render_template(template_name + ".tex.j2", escaped_context)` → LaTeX source
3. Call `compile_latex(tex_source, pdflatex_path)` → PDF bytes or None
4. Return PDF bytes

**Preconditions**: Template exists; pdflatex available for PDF output.
**Postconditions**: No persistent state change.
**Side Effects**: Subprocess execution via compile_latex().
**Idempotency**: Yes.
**Thread Safety**: Safe.

---

## 4. Data Model

### 4.1 Entity Definitions

#### uploaded_documents

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | Primary identifier |
| filename | TEXT | NOT NULL | Original filename |
| file_type | TEXT | NOT NULL | Extension (pdf, docx, txt, md) |
| file_path | TEXT | NOT NULL | Stored file path |
| raw_text | TEXT | | Extracted text content |
| llm_provider | TEXT | | Provider used for extraction |
| llm_model | TEXT | | Model used for extraction |
| processed_at | DATETIME | | When LLM extraction completed |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Upload time |

#### knowledge_base

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | Primary identifier |
| category | TEXT | NOT NULL | Entry category (experience, skill, etc.) |
| text | TEXT | NOT NULL | Entry content |
| subsection | TEXT | | Context (role/company for experience) |
| job_types | TEXT | | JSON array of relevant job types |
| tags | TEXT | | Comma-separated tags |
| source_doc_id | INTEGER | FK → uploaded_documents(id) | Source document |
| embedding | BLOB | | Reserved for ONNX embeddings (M2) |
| is_active | INTEGER | NOT NULL, DEFAULT 1 | Soft-delete flag |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Creation time |
| updated_at | DATETIME | | Last modification time |

**Business invariants**:
- (category, text) is UNIQUE — dedup constraint
- category must be one of VALID_CATEGORIES
- is_active: 1 (active) or 0 (soft-deleted)

**Indexes**:
| Index Name | Columns | Type | Rationale |
|-----------|---------|------|-----------|
| idx_kb_dedup | (category, text) | UNIQUE | Deduplication |
| idx_kb_category | (category) | B-tree | Filter by category |
| idx_kb_active | (is_active) | B-tree | Filter active entries |

#### roles

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | INTEGER | PK, AUTOINCREMENT | Primary identifier |
| title | TEXT | NOT NULL | Job title |
| company | TEXT | NOT NULL | Company name |
| start_date | TEXT | NOT NULL | Start date (flexible format) |
| end_date | TEXT | | End date or "Present" |
| domain | TEXT | | Career domain (backend, frontend, etc.) |
| description | TEXT | | Role description |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Creation time |

**Business invariants**:
- (title, company, start_date) is UNIQUE — dedup constraint

**Indexes**:
| Index Name | Columns | Type | Rationale |
|-----------|---------|------|-----------|
| idx_roles_dedup | (title, company, start_date) | UNIQUE | Deduplication |

#### resume_versions (modified — 2 new columns)

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| reuse_source | TEXT | nullable | "kb" if assembled from KB, null if LLM-generated |
| source_entry_ids | TEXT | nullable | JSON array of KB entry IDs used |

### 4.2 Relationships

```
uploaded_documents ──1:N──▶ knowledge_base  (via knowledge_base.source_doc_id)
```

### 4.3 State Machines

#### KB Entry Lifecycle

```
[create] ──▶ ACTIVE (is_active=1)
                  │
            [soft_delete]
                  │
                  ▼
            DELETED (is_active=0)
```

| From | To | Trigger | Guard | Action |
|------|-----|---------|-------|--------|
| — | ACTIVE | save_kb_entry() | unique (category, text) | Insert row |
| ACTIVE | ACTIVE | update_kb_entry() | entry exists | Update fields + updated_at |
| ACTIVE | DELETED | soft_delete_kb_entry() | entry exists | Set is_active=0 + updated_at |

---

## 5. Error Handling Strategy

| Category | Example | Handling | Log Level |
|----------|---------|---------|-----------|
| File not found | Missing upload path | Raise FileNotFoundError | N/A (caller handles) |
| Unsupported type | .csv file | Raise ValueError with supported list | N/A |
| Missing optional dep | PyPDF2 not installed | Raise RuntimeError with install instructions | N/A |
| LLM response malformed | Invalid JSON | Return empty list, log error | ERROR |
| LLM response not array | JSON object instead of array | Return empty list, log error | ERROR |
| Encoding failure | Non-UTF-8 text file | Fallback to Latin-1 | WARNING |
| Empty extraction | PDF with no extractable text | Log warning, return 0 entries | WARNING |
| Duplicate entry | Same (category, text) exists | INSERT OR IGNORE, return None | DEBUG |
| Invalid entry | Empty text or unknown category | Skip silently during validation | DEBUG |
| Date parse failure | Unparseable date string | Return None, log debug | DEBUG |

---

## 6. Configuration Strategy

| Parameter | Type | Default | Location | Description |
|-----------|------|---------|----------|-------------|
| resume_reuse.enabled | bool | true | config.json | Enable KB-based resume assembly |
| resume_reuse.min_score | float | 0.60 | config.json | Minimum TF-IDF score to include entry |
| resume_reuse.min_experience_bullets | int | 6 | config.json | Minimum experience entries for KB assembly |
| resume_reuse.scoring_method | str | "auto" | config.json | "tfidf", "onnx", or "auto" |
| resume_reuse.cover_letter_strategy | str | "generate" | config.json | "generate" or "template" |
| latex.template | str | "classic" | config.json | LaTeX template name |
| latex.font_family | str | "helvetica" | config.json | Font family |
| latex.font_size | int | 11 | config.json | Font size in points |
| latex.margin | str | "0.75in" | config.json | Page margins |

**Hierarchy**: Pydantic defaults → config.json overrides
**Validation**: At AppConfig load time via Pydantic validators.

---

## 7. Architecture Decision Records

### ADR-027: SQLite Knowledge Base with Dedup on (category, text)

**Status**: accepted
**Context**: KB entries must be stored locally for offline-first desktop app. Duplicate entries from re-uploading the same document or ingesting the same resume must be prevented.

**Decision**: Use SQLite table with UNIQUE index on (category, text) and INSERT OR IGNORE for dedup.

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| Full-text hash dedup | Exact match guaranteed | Same text in different categories treated as different (correct behavior) |
| Fuzzy dedup (embeddings) | Catches near-duplicates | Requires ONNX model, adds complexity in M1 |
| **UNIQUE(category, text)** | **Simple, reliable, no deps** | **Won't catch paraphrased duplicates** |

**Consequences**:
- Positive: Zero external dependencies, fast insert, reliable
- Negative: Won't catch semantically similar but textually different entries
- Risks: Very long text entries may hit SQLite limits → mitigated by entry text being typically < 500 chars

**Rationale**: M1 focuses on foundation. Semantic dedup can be added in M2 with ONNX embeddings.

---

### ADR-028: Single LLM Call Per Document Upload

**Status**: accepted
**Context**: Each document upload needs to be processed into structured entries. Options: (a) one LLM call per upload with full prompt, (b) multiple calls chunking the document, (c) no LLM — rule-based only.

**Decision**: Single LLM call per upload with the full document text (truncated to 12,000 chars).

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| Multiple chunked calls | Handles long documents | Expensive, complex merging |
| Rule-based only | Zero cost | Poor quality, can't extract metrics |
| **Single call, 12k truncation** | **One call = cheap, simple** | **Long docs lose tail content** |

**Consequences**:
- Positive: Minimal cost ($0.02-0.10 per upload), simple pipeline
- Negative: Documents over ~4 pages may be truncated
- Risks: Important content at end of long document is lost → user can split into multiple uploads

---

## 8. Design Traceability Matrix

| Requirement | Type | Design Component(s) | Interface(s) | ADR |
|-------------|------|---------------------|---------------|-----|
| FR-030-01 | FR | DocumentParser | extract_text() | — |
| FR-030-02 | FR | Database | save_uploaded_document() | — |
| FR-030-03 | FR | KnowledgeBase, AI Engine | _extract_via_llm(), invoke_llm() | ADR-028 |
| FR-030-04 | FR | KnowledgeBase, Database | save_kb_entry(), get_kb_entries(), update_kb_entry(), soft_delete_kb_entry() | ADR-027 |
| FR-030-05 | FR | Database | get_kb_stats() | — |
| FR-030-06 | FR | ResumeParser | parse_resume_md() | — |
| FR-030-07 | FR | KnowledgeBase | ingest_generated_resume(), ingest_entries() | — |
| FR-030-08 | FR | Database | save_role(), get_roles() | — |
| FR-030-09 | FR | ExperienceCalculator | calculate_experience() | — |
| FR-030-10 | FR | Config Models | ResumeReuseConfig, LatexConfig, AppConfig | — |
| FR-030-11 | FR | Database | _migrate() | — |
| FR-030-12 | FR | i18n locale files | en.json, es.json | — |
| NFR-030-01 | NFR | Database (SQLite indexes) | CRUD methods | ADR-027 |
| NFR-030-02 | NFR | All new modules | logging.getLogger(__name__) | — |
| NFR-030-03 | NFR | Test suite | pytest | — |
| NFR-030-04 | NFR | Config Models | Pydantic defaults | — |
| NFR-030-05 | NFR | pyproject.toml | pinned versions | — |
| NFR-030-06 | NFR | All new modules | t() for user strings | — |
| FR-030-13 | FR | ResumeScorer | score_kb_entries(), compute_tfidf_score() | ADR-029 |
| FR-030-14 | FR | JDAnalyzer | analyze_jd() | — |
| FR-030-15 | FR | JDAnalyzer | _detect_sections() | — |
| FR-030-16 | FR | JDAnalyzer | normalize_term(), SYNONYM_MAP | — |
| FR-030-17 | FR | ResumeScorer | _compute_tfidf_scores() (keyword boost) | — |
| FR-030-18 | FR | ResumeScorer | _onnx_score_entries(), blending logic | ADR-030 |
| FR-030-19 | FR | JDAnalyzer | TECH_TERMS frozenset, _extract_tech_terms() | — |
| NFR-030-07 | NFR | ResumeScorer | _compute_tfidf_scores() (batch) | ADR-029 |
| NFR-030-08 | NFR | Test suite (M2) | pytest | — |
| NFR-030-09 | NFR | pyproject.toml | No new deps for M2 | ADR-029 |
| NFR-030-10 | NFR | ResumeScorer, JDAnalyzer | logging.getLogger(__name__) | — |
| FR-030-20 | FR | LatexCompiler | escape_latex() | — |
| FR-030-21 | FR | LatexCompiler | find_pdflatex() | — |
| FR-030-22 | FR | LatexCompiler | render_template(), compile_latex() | ADR-031 |
| FR-030-23 | FR | LatexCompiler | compile_resume() | — |
| FR-030-24 | FR | LaTeX Templates | classic.tex.j2, modern.tex.j2, compact.tex.j2, academic.tex.j2 | ADR-031 |
| FR-030-25 | FR | TinyTeX Bundler | bundle-tinytex.js | — |
| NFR-030-11 | NFR | LatexCompiler | compile_latex() timeout, temp dir cleanup | — |
| NFR-030-12 | NFR | LatexCompiler | logging.getLogger(__name__) | — |
| NFR-030-13 | NFR | Test suite (M3) | pytest | — |

**Completeness**: 25/25 FRs mapped, 13/13 NFRs mapped. Zero gaps.

---

## 9. Implementation Plan

| Order | Task ID | Description | Depends On | Size | Risk | FR Coverage |
|-------|---------|------------|------------|------|------|-------------|
| 1 | IMPL-001 | DB schema: 3 new tables, 2 new columns, migration | — | M | Low | FR-030-02, FR-030-08, FR-030-11 |
| 2 | IMPL-002 | Document parser module | — | S | Low | FR-030-01 |
| 3 | IMPL-003 | Config models (ResumeReuseConfig, LatexConfig) | — | S | Low | FR-030-10 |
| 4 | IMPL-004 | Resume markdown parser | — | M | Low | FR-030-06 |
| 5 | IMPL-005 | Experience calculator | IMPL-001 | S | Low | FR-030-09 |
| 6 | IMPL-006 | Knowledge Base class (CRUD + LLM extraction) | IMPL-001, IMPL-002 | L | Medium | FR-030-03, FR-030-04, FR-030-05, FR-030-07 |
| 7 | IMPL-007 | i18n keys (en.json, es.json) | — | S | Low | FR-030-12 |
| 8 | IMPL-008 | Unit tests (all modules) | IMPL-001 through IMPL-007 | L | Low | All |

### Per-Task Detail

#### IMPL-001: DB Schema + Migration
- **Creates**: 3 tables in SCHEMA_SQL, 2 UNIQUE indexes
- **Modifies**: `db/database.py` — SCHEMA_SQL, _migrate(), 13 new CRUD methods
- **Tests**: test_kb_database.py — schema, migration, CRUD, dedup, cascade
- **Done when**: All 3 tables created; migration handles existing DBs; all CRUD methods work

#### IMPL-002: Document Parser
- **Creates**: `core/document_parser.py`
- **Tests**: test_document_parser.py — TXT, MD, PDF mock, DOCX mock, errors
- **Done when**: extract_text() works for all 4 formats with proper error handling

#### IMPL-003: Config Models
- **Modifies**: `config/settings.py`
- **Tests**: test_kb_config.py — defaults, overrides, backward compat, serialization
- **Done when**: AppConfig loads with/without resume_reuse/latex keys

#### IMPL-004: Resume Parser
- **Creates**: `core/resume_parser.py`
- **Tests**: test_resume_parser.py — all sections, alternative headings, edge cases
- **Done when**: parse_resume_md() correctly parses all section types

#### IMPL-005: Experience Calculator
- **Creates**: `core/experience_calculator.py`
- **Tests**: test_experience_calculator.py — date parsing, duration, domains
- **Done when**: calculate_experience() returns correct totals from roles

#### IMPL-006: Knowledge Base Class
- **Creates**: `core/knowledge_base.py`
- **Tests**: test_knowledge_base.py — process_upload, CRUD delegation, LLM mocking, ingestion
- **Done when**: Full upload pipeline works; CRUD delegates to DB; dedup works

#### IMPL-007: i18n Keys
- **Modifies**: `static/locales/en.json`, `static/locales/es.json`
- **Tests**: Manual verification
- **Done when**: kb and reuse sections present in both locale files

#### IMPL-008: Unit Tests (M1)
- **Creates**: 6 test files, 89+ tests
- **Done when**: All tests pass; ruff clean; coverage > 80% on new modules

---

### M2 Implementation Tasks

| Order | Task ID | Description | Depends On | Size | Risk | FR Coverage |
|-------|---------|------------|------------|------|------|-------------|
| 9 | IMPL-009 | JD Analyzer module | — | M | Low | FR-030-14, FR-030-15, FR-030-16, FR-030-19 |
| 10 | IMPL-010 | TF-IDF Resume Scorer module | IMPL-009 | M | Low | FR-030-13, FR-030-17, FR-030-18 |
| 11 | IMPL-011 | M2 Unit Tests | IMPL-009, IMPL-010 | M | Low | All M2 FRs |

#### IMPL-009: JD Analyzer
- **Creates**: `core/jd_analyzer.py`
- **Contains**: `analyze_jd()`, `normalize_term()`, `SYNONYM_MAP` (40+ aliases), `TECH_TERMS` (100+ terms), `_detect_sections()`, `_extract_keywords()`, `_extract_tech_terms()`, `_extract_ngrams()`
- **Tests**: `test_resume_scorer.py::TestJDAnalyzer`, `TestSectionDetection`
- **Done when**: JD analysis returns keywords, tech terms, sections, n-grams; synonyms normalize correctly

#### IMPL-010: TF-IDF Resume Scorer
- **Creates**: `core/resume_scorer.py`
- **Contains**: `score_kb_entries()`, `compute_tfidf_score()`, TF-IDF engine (`_tokenize`, `_term_frequency`, `_inverse_document_frequency`, `_tfidf_vector`, `_cosine_similarity`), keyword boost logic, ONNX interface (`_onnx_available()`, `_onnx_score_entries()`)
- **Tests**: `test_resume_scorer.py::TestTFIDF`, `TestScoreKBEntries`, `TestONNXBlending`
- **Done when**: score_kb_entries() returns ranked, filtered results; ONNX blending works with mocked scores; TF-IDF is stdlib-only

#### IMPL-011: M2 Unit Tests
- **Creates**: `tests/test_resume_scorer.py` — 38 tests across 5 test classes
- **Done when**: All tests pass; ruff clean; coverage > 90% on new modules

---

### M3 Implementation Tasks

| Order | Task ID | Description | Depends On | Size | Risk | FR Coverage |
|-------|---------|------------|------------|------|------|-------------|
| 12 | IMPL-012 | LaTeX compiler module | IMPL-003 | M | Medium | FR-030-20, FR-030-21, FR-030-22, FR-030-23 |
| 13 | IMPL-013 | LaTeX resume templates | IMPL-012 | M | Low | FR-030-24 |
| 14 | IMPL-014 | TinyTeX bundling script | — | S | Medium | FR-030-25 |

#### IMPL-012: LaTeX Compiler Module
- **Creates**: `core/latex_compiler.py`
- **Contains**: `escape_latex()`, `find_pdflatex()`, `render_template()`, `compile_latex()`, `compile_resume()`
- **Dependencies**: `jinja2` (already in project deps)
- **Jinja2 Environment**: Custom delimiters per ADR-031 (`\VAR{}`, `\BLOCK{}`, `\#{}`)
- **Tests**: `tests/test_latex_compiler.py` — escape special chars, pdflatex discovery (mocked), template rendering, compilation (mocked subprocess), full pipeline, error paths (missing pdflatex, compilation failure, timeout)
- **Done when**: All 5 interface contracts (§3.15–§3.19) satisfied; escape handles all 10 LaTeX special chars; find_pdflatex checks bundled then system; compile_latex uses temp dir with cleanup; compile_resume escapes context recursively

#### IMPL-013: LaTeX Resume Templates
- **Creates**: `templates/latex/classic.tex.j2`, `templates/latex/modern.tex.j2`, `templates/latex/compact.tex.j2`, `templates/latex/academic.tex.j2`
- **Template Structure**: Each template uses custom Jinja2 delimiters (ADR-031), includes sections for header (name, contact), summary, experience, education, skills, certifications, projects
- **Delimiter Usage**: `\VAR{name}` for variables, `\BLOCK{for exp in experiences}...\BLOCK{endfor}` for loops, `\#{comment}` for comments
- **Font Configuration**: Templates read `font_family`, `font_size`, `margin` from context (sourced from LatexConfig)
- **Tests**: Verified via IMPL-012 render_template() tests with sample context dicts
- **Done when**: All 4 templates render valid LaTeX source; each template produces distinct visual layout; all context variables used

#### IMPL-014: TinyTeX Bundling Script
- **Creates**: `electron/scripts/bundle-tinytex.js`
- **Purpose**: Download and bundle platform-specific TinyTeX distribution for offline pdflatex support
- **Platform Detection**: `process.platform` → downloads appropriate TinyTeX archive (Windows .zip, macOS .tar.gz, Linux .tar.gz)
- **Download Sources**: TinyTeX GitHub releases (https://github.com/rstudio/tinytex-releases)
- **Output Directory**: `electron/tinytex/` — contains `bin/<platform>/pdflatex(.exe)` and minimal TeX packages
- **Required LaTeX Packages**: `latex-bin`, `collection-fontsrecommended`, `geometry`, `hyperref`, `enumitem`, `titlesec`, `fancyhdr`, `xcolor`, `parskip`
- **Script Behavior**: Skip download if `electron/tinytex/` already exists and is populated; use `tlmgr` to install required packages after extraction
- **Integration**: Called by `electron/scripts/bundle-python.js` (existing) or standalone via `node electron/scripts/bundle-tinytex.js`
- **Tests**: Manual verification — run script, verify pdflatex binary exists, verify `pdflatex --version` succeeds
- **Done when**: Script downloads TinyTeX for current platform; pdflatex binary is executable; required packages installed; idempotent (skip if already present)

---

### ADR-029: Stdlib-Only TF-IDF Scoring

**Status**: accepted
**Context**: KB entries must be scored against job descriptions for relevance ranking. The scoring engine must work offline, be fast (<30ms for 200 entries), and add zero new dependencies.

**Decision**: Hand-rolled TF-IDF cosine similarity using only `collections.Counter`, `math`, and `re` from the Python stdlib. IDF uses smoothing: `log((N+1) / (df+1)) + 1`. Keyword boost adds up to +0.25 total (required +0.15, preferred +0.05, tech +0.05).

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| scikit-learn TfidfVectorizer | Battle-tested, fast | Heavy dependency (~150MB with NumPy/SciPy) |
| Sentence-Transformers | Best semantic quality | Requires PyTorch (~2GB), slow on CPU |
| **stdlib TF-IDF + keyword boost** | **Zero deps, <30ms, good enough for ranking** | **No semantic understanding** |

**Consequences**:
- Positive: Zero dependency footprint, fast, deterministic, easy to test
- Negative: Cannot capture semantic similarity (e.g., "ML" and "machine learning" only match via synonym map, not semantically)
- Risks: Accuracy may be lower than embedding-based approaches → mitigated by optional ONNX blending (ADR-030)

---

### ADR-030: Optional ONNX Embedding Blending

**Status**: accepted
**Context**: TF-IDF is keyword-based and misses semantic relationships. ONNX embeddings provide better matching but require optional dependencies (`onnxruntime`, `tokenizers`).

**Decision**: M2 defines the blending interface (0.3 × TF-IDF + 0.7 × ONNX). ONNX scoring returns None when unavailable, triggering pure TF-IDF fallback. Full ONNX implementation deferred to M8 (Performance milestone).

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| ONNX required | Best quality scoring | Adds ~130MB, not all users need it |
| **ONNX optional with TF-IDF fallback** | **Works everywhere, upgradeable** | **Two code paths to maintain** |
| No ONNX support | Simplest | No upgrade path for semantic scoring |

**Consequences**:
- Positive: Zero runtime cost when not installed; clear upgrade path
- Negative: Two scoring paths (TF-IDF only vs blended) require separate test coverage
- Risks: Blending weights (0.3/0.7) may need tuning → configurable in future milestones

---

### ADR-031: Custom Jinja2 Delimiters for LaTeX Templates

**Status**: accepted
**Context**: LaTeX uses `{` and `}` extensively for grouping arguments (e.g., `\textbf{bold}`, `\begin{document}`). Jinja2's default delimiters (`{{ }}`, `{% %}`, `{# #}`) conflict with LaTeX braces, making templates unreadable and error-prone. Every LaTeX brace would need escaping or raw blocks, defeating the purpose of templating.

**Decision**: Use custom Jinja2 delimiters that start with `\` (a LaTeX command prefix) to feel natural in LaTeX source:

| Jinja2 Purpose | Default Delimiter | Custom Delimiter |
|----------------|-------------------|------------------|
| Variable | `{{ var }}` | `\VAR{var}` |
| Block/logic | `{% if %}` | `\BLOCK{if condition}` |
| Comment | `{# comment #}` | `\#{comment}` |

**Jinja2 Environment Configuration**:
```python
env = jinja2.Environment(
    block_start_string="\\BLOCK{",
    block_end_string="}",
    variable_start_string="\\VAR{",
    variable_end_string="}",
    comment_start_string="\\#{",
    comment_end_string="}",
    autoescape=False,
    loader=jinja2.FileSystemLoader("templates/latex/"),
)
```

**Template Example**:
```latex
\documentclass[11pt]{article}
\begin{document}
\textbf{\VAR{name}} \\
\VAR{email} | \VAR{phone}

\BLOCK{for exp in experiences}
\textbf{\VAR{exp.title}} at \VAR{exp.company} \\
\VAR{exp.start_date} -- \VAR{exp.end_date}
\BLOCK{endfor}
\end{document}
```

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| Default Jinja2 delimiters | No config needed | Conflicts with every LaTeX `{}` usage |
| `<< >>` / `<% %>` delimiters | No LaTeX conflict | Looks foreign in LaTeX source, possible HTML confusion |
| Raw blocks around LaTeX | Works with defaults | Verbose, defeats templating purpose |
| **`\VAR{}` / `\BLOCK{}` / `\#{}` delimiters** | **Looks like LaTeX commands, zero conflict** | **Requires env configuration** |

**Consequences**:
- Positive: Templates read naturally as LaTeX with embedded variables; no escaping needed for LaTeX braces; `\VAR{name}` visually signals "this is a variable" to LaTeX-familiar users
- Negative: Requires custom Jinja2 Environment setup (one-time, 6 lines); developers must learn non-default syntax
- Risks: `}` as end delimiter could theoretically conflict with LaTeX's `}` in complex nesting → mitigated by placing Jinja2 tags on their own lines or at clear boundaries

---

## System Architecture -- GATE 4 OUTPUT

**Document**: SAD-TASK-030-smart-resume-reuse
**Components**: 12 components defined (7 M1 + 2 M2 + 3 M3)
**Interfaces**: 19 contracts specified (10 M1 + 4 M2 + 5 M3)
**Entities**: 4 data entities modeled (3 new tables + 1 modified)
**ADRs**: 5 decisions documented (ADR-027, ADR-028, ADR-029, ADR-030, ADR-031)
**Impl Tasks**: 14 tasks in dependency order (8 M1 + 3 M2 + 3 M3)
**Traceability**: 38/38 requirements mapped (100%)
**Checklist**: 20/20 items passed

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| Backend Developer | Interface contracts, data model, impl plan |
| Unit Tester | Interface contracts for test generation |
| Integration Tester | API contracts, integration points |
