# System Architecture Document

**Document ID**: SAD-TASK-030-smart-resume-reuse
**Version**: 1.1
**Date**: 2026-03-12
**Status**: approved (updated: LaTeX pipeline deprecated in favor of LLM + ReportLab)
**Author**: Claude (System Engineer)
**SRS Reference**: SRS-TASK-030-smart-resume-reuse

---

## 1. Executive Summary

This architecture defines the Smart Resume Reuse feature across four milestones: M1 (Knowledge Base foundation), M2 (TF-IDF scoring), M3 (LaTeX compilation — DEPRECATED, not used in active pipeline), and M4 (Resume Assembly + Bot Integration). The design introduces 8 new Python modules, 3 new SQLite tables, 2 new config models, and extends the existing Database class with 15 new methods. M4 adds the assembly pipeline that ties M1-M2 together with an LLM + ReportLab rendering approach: score KB entries against a JD via TF-IDF, select top entries per section, send selected entries to the LLM with a strict "only use provided data" prompt, receive markdown back, and render to PDF via ReportLab. The LaTeX compilation path (M3) is deprecated and not used in the active assembly pipeline. All components follow the existing layer architecture and integrate via the established patterns (SQLite, Pydantic, structured logging).

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
                 │ Config Models│  (ResumeReuseConfig, LatexConfig [DEPRECATED])
                 │ [Pydantic]   │
                 └──────────────┘

M4 Assembly + Bot Integration (LLM + ReportLab pipeline):

┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ Bot (bot.py)     │─────▶│ ResumeAssembler  │─────▶│ ResumeScorer     │
│ _generate_docs() │      │ (assembly pipe)  │      │ (TF-IDF scoring) │
│ _try_kb_assembly │      │ [core logic]     │      │ [M2 scorer]      │
│ _ingest_llm_out  │      └────────┬─────────┘      └─────────────────┘
└─────────────────┘               │
                          ┌───────┼────────┐
                          ▼       ▼        ▼
                 ┌──────────┐ ┌──────────┐ ┌──────────────┐
                 │ AI Engine│ │ Resume   │ │ KnowledgeBase│
                 │ (LLM     │ │ Renderer │ │ (KB read +   │
                 │ generate)│ │[ReportLab]│ │  ingestion)  │
                 └──────────┘ └──────────┘ └──────────────┘

    NOTE: LaTeX Compiler (M3) is DEPRECATED — not used in active pipeline.
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

**Dashboard Toggle Change (Automation Config)**:
```
Dashboard Toggle Change
  → initBotToggles() event listener
  → PUT /api/config { resume_reuse: { enabled: bool } } or { bot: { cover_letter_enabled: bool } }
  → routes/config.py::update_config() shallow merge
  → save_config() writes to ~/.autoapply/config.json
  → Next bot cycle reads updated config
  → _generate_docs() checks config.bot.cover_letter_enabled
  → _try_kb_assembly() checks config.resume_reuse.enabled
```

### 2.3 Layer Architecture

| Layer | Responsibility | Components |
|-------|---------------|------------|
| Service | Business logic, orchestration | `KnowledgeBase`, `calculate_experience()`, `ResumeAssembler`, Bot KB-first flow |
| Domain | Pure data parsing, no I/O | `parse_resume_md()`, `_parse_date()`, `_select_entries()`, `_build_context()`, config models |
| Repository | Data access | `Database` (KB CRUD methods, resume_versions extension) |
| Infrastructure | External calls, filesystem | `extract_text()`, `invoke_llm()`, `render_resume_to_pdf()`, `save_assembled_resume()` |

### 2.4 Component Catalog

| Component | Responsibility | Technology | Layer | File |
|-----------|---------------|------------|-------|------|
| DocumentParser | Extract text from PDF/DOCX/TXT/MD | PyPDF2, python-docx, stdlib | Infrastructure | `core/document_parser.py` |
| KnowledgeBase | Orchestrate upload pipeline, CRUD delegation | stdlib | Service | `core/knowledge_base.py` |
| ResumeParser | Parse markdown resumes into entry dicts | regex, stdlib | Domain | `core/resume_parser.py` |
| ExperienceCalculator | Calculate years of experience from roles | datetime, stdlib | Domain | `core/experience_calculator.py` |
| Database (extended) | SQLite CRUD for KB, documents, roles | sqlite3 | Repository | `db/database.py` |
| ResumeReuseConfig | Resume reuse settings | Pydantic | Domain | `config/settings.py` |
| LatexConfig | **DEPRECATED** — LaTeX compilation settings (not used in active pipeline) | Pydantic | Domain | `config/settings.py` |
| LatexCompiler | **DEPRECATED** — LaTeX escaping, template rendering, PDF compilation | Jinja2, subprocess | Infrastructure | `core/latex_compiler.py` |
| LaTeX Templates | **DEPRECATED** — 4 resume templates with custom Jinja2 delimiters | Jinja2 (.tex.j2) | Infrastructure | `templates/latex/*.tex.j2` |
| TinyTeX Bundler | **DEPRECATED** — Platform-specific TinyTeX download and packaging | Node.js | Infrastructure | `electron/scripts/bundle-tinytex.js` |
| AI Engine (KB resume) | LLM-based resume generation from KB context with strict data-only prompt | invoke_llm | Infrastructure | `core/ai_engine.py` |
| ResumeRenderer | Render markdown resume to PDF via ReportLab (Helvetica, 22pt name, 9.5pt body, 11pt section headers) | ReportLab | Infrastructure | `core/resume_renderer.py` |
| ResumeAssembler | Orchestrate KB-first resume assembly: score → select → LLM generate → ReportLab render | stdlib | Service | `core/resume_assembler.py` |
| Bot (KB-first flow) | Try KB assembly before LLM, ingest LLM output | stdlib | Service | `bot/bot.py` (modified) |
| Database (resume_versions ext) | resume_versions +reuse_source, +source_entry_ids | sqlite3 | Repository | `db/database.py` (modified) |
| DefaultResumeManager | Handle upload, retrieval, and deletion of fallback resume file. Routes in `routes/config.py`. Stores to `~/.autoapply/default_resume.{ext}`, updates `profile.fallback_resume_path` | Flask, stdlib | Service | `routes/config.py` |
| DashboardToggles | Client-side controls (`static/js/settings.js::initBotToggles()`) for Adaptive Resume and Cover Letter toggles. Auto-save via PUT /api/config on change. Load state via `loadApplyMode()` | vanilla JS | Presentation | `static/js/settings.js`, `templates/index.html` |

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

### 3.15 latex_compiler.escape_latex() (M3) — DEPRECATED

> **DEPRECATED**: LaTeX compilation is not used in the active assembly pipeline. The primary rendering path is LLM + ReportLab (see §3.20). This interface contract is retained for reference only.

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

### 3.16 latex_compiler.find_pdflatex() (M3) — DEPRECATED

> **DEPRECATED**: LaTeX compilation is not used in the active assembly pipeline. See §3.20.

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

### 3.17 latex_compiler.render_template() (M3) — DEPRECATED

> **DEPRECATED**: LaTeX compilation is not used in the active assembly pipeline. See §3.20.

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

### 3.18 latex_compiler.compile_latex() (M3) — DEPRECATED

> **DEPRECATED**: LaTeX compilation is not used in the active assembly pipeline. See §3.20.

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

### 3.19 latex_compiler.compile_resume() (M3) — DEPRECATED

> **DEPRECATED**: LaTeX compilation is not used in the active assembly pipeline. See §3.20.

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
| latex.template | str | "classic" | config.json | **DEPRECATED** — LaTeX template name (not used in active pipeline) |
| latex.font_family | str | "helvetica" | config.json | **DEPRECATED** — Font family (not used in active pipeline) |
| latex.font_size | int | 11 | config.json | **DEPRECATED** — Font size in points (not used in active pipeline) |
| latex.margin | str | "0.75in" | config.json | **DEPRECATED** — Page margins (not used in active pipeline) |

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
| FR-030-20 | FR | LatexCompiler | escape_latex() | — | **DEPRECATED** |
| FR-030-21 | FR | LatexCompiler | find_pdflatex() | — | **DEPRECATED** |
| FR-030-22 | FR | LatexCompiler | render_template(), compile_latex() | ADR-031 (SUPERSEDED) | **DEPRECATED** |
| FR-030-23 | FR | LatexCompiler | compile_resume() | — | **DEPRECATED** |
| FR-030-24 | FR | LaTeX Templates | classic.tex.j2, modern.tex.j2, compact.tex.j2, academic.tex.j2 | ADR-031 (SUPERSEDED) | **DEPRECATED** |
| FR-030-25 | FR | TinyTeX Bundler | bundle-tinytex.js | — | **DEPRECATED** |
| NFR-030-11 | NFR | LatexCompiler | compile_latex() timeout, temp dir cleanup | — |
| NFR-030-12 | NFR | LatexCompiler | logging.getLogger(__name__) | — |
| NFR-030-13 | NFR | Test suite (M3) | pytest | — |
| FR-030-26 | FR | ResumeAssembler, AI Engine, ResumeRenderer | assemble_resume() → generate_resume_from_kb() → render_resume_to_pdf() | ADR-032 |
| FR-030-27 | FR | ResumeAssembler | _select_entries() | — |
| FR-030-28 | FR | ResumeAssembler | _build_context(), _format_kb_data_for_prompt() | — |
| FR-030-29 | FR | DashboardToggles, Bot | `static/js/settings.js`, `templates/index.html`, `bot/bot.py` — initBotToggles(), _generate_docs() toggle checks | ADR-032 |
| FR-030-30 | FR | DefaultResumeManager | `routes/config.py` — POST/GET/DELETE /api/config/default-resume | IC-043, IC-044, IC-045 |
| FR-030-31 | FR | DashboardToggles, Config UI | `templates/index.html`, `static/js/settings.js`, `static/css/main.css` — toggle controls, styling | — |
| FR-030-32 | FR | KB Viewer, Resume Preview | `templates/index.html`, `static/js/knowledge-base.js`, `static/js/resume-preview.js` — KB screen + preview | — |
| NFR-030-14 | NFR | ResumeAssembler | logging.getLogger(__name__) | — |
| NFR-030-15 | NFR | Test suite (M4) | pytest | — |

**Completeness**: 32/32 FRs mapped (FR-030-20 through FR-030-25 DEPRECATED), 15/15 NFRs mapped. Zero gaps.

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

### M3 Implementation Tasks — DEPRECATED

> **NOTE**: M3 (LaTeX compilation) was implemented but is DEPRECATED. The active assembly pipeline uses LLM + ReportLab (see §3.20). M3 code remains in the codebase but is not called by the active pipeline.

| Order | Task ID | Description | Depends On | Size | Risk | FR Coverage |
|-------|---------|------------|------------|------|------|-------------|
| 12 | IMPL-012 | LaTeX compiler module **(DEPRECATED)** | IMPL-003 | M | Medium | FR-030-20, FR-030-21, FR-030-22, FR-030-23 |
| 13 | IMPL-013 | LaTeX resume templates **(DEPRECATED)** | IMPL-012 | M | Low | FR-030-24 |
| 14 | IMPL-014 | TinyTeX bundling script **(DEPRECATED)** | — | S | Medium | FR-030-25 |

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

**Status**: SUPERSEDED — LaTeX compilation is deprecated in favor of LLM + ReportLab pipeline. This ADR is retained for historical reference only.
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

### 3.20 resume_assembler.assemble_resume() (M4)

**Purpose**: Orchestrate KB-first resume assembly: score entries against JD, select top entries per section, build structured context, send to LLM with strict "only use provided data" prompt, receive markdown, render to PDF via ReportLab. Returns assembled resume dict or None if insufficient KB entries.
**Category**: command (reads KB, calls LLM, writes PDF)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| jd_text | str | yes | Non-empty | Job description text for scoring |
| profile | dict | yes | Keys: full_name, email, phone, location | User profile from config |
| kb | KnowledgeBase | yes | Must have initialized DB | Knowledge base instance |
| reuse_config | ResumeReuseConfig or None | no | default: None (uses defaults) | Resume reuse settings (min_score, min_experience_bullets, scoring_method) |
| llm_config | LLMConfig | yes | provider + api_key + model | LLM configuration for resume generation |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | dict or None | yes | None if insufficient KB entries or AI unavailable. Otherwise dict with keys: `pdf_bytes` (bytes), `resume_md` (str), `entry_ids` (list[int]), `scoring_method` (str) |

Errors:
| Error Condition | Error Type | HTTP Status |
|----------------|------------|-------------|
| Empty jd_text | (no error) returns None | N/A |
| Fewer entries than min_experience_bullets | (no error) returns None, logs INFO | N/A |
| AI not configured | (no error) returns None via `check_ai_available()` | N/A |
| LLM generation failure | (no error) returns None, logs ERROR | N/A |

**Pipeline**:
1. Validate LLM availability via `check_ai_available(llm_config)`
2. Fetch all active KB entries via `kb.get_all_entries(active_only=True)`
3. Score entries via `score_kb_entries(jd_text, entries, reuse_config)`
4. Call `_select_entries(scored, reuse_config)` → grouped entries or None
5. If None (insufficient), return None
6. Call `_build_context(profile, selected)` → structured context dict (experience grouped by company/role, skills by category)
7. Call `_format_kb_data_for_prompt(context)` → serialized KB data string for LLM
8. Call `generate_resume_from_kb(context, jd_text, llm_config)` → resume markdown (LLM prompt requires exactly 1 page, min 2 bullets per role, allows rephrasing/synonyms from JD, strict "only use provided data")
9. Call `render_resume_to_pdf(resume_md, tmp_path)` → pdf_bytes via ReportLab (Helvetica font, 22pt name centered, 9.5pt body, 11pt section headers uppercase with rules, two-column layout for company/dates)
10. Return result dict with pdf_bytes, resume_md, entry_ids, scoring_method

**Selection Limits** (applied in step 4):
| Category | Max Entries |
|----------|------------|
| experience | 15 |
| skill | 20 |
| education | 4 |
| project | 6 |
| certification | 5 |

**Preconditions**: KB populated with entries; profile has required contact fields; LLM configured.
**Postconditions**: No DB mutation (read-only assembly). PDF bytes in memory.
**Side Effects**: LLM API call for resume generation.
**Idempotency**: Yes (same inputs → same output, assuming KB unchanged and LLM deterministic).
**Thread Safety**: Safe (reads only; temp dirs isolated per call).

---

### 3.21 resume_assembler._select_entries() (M4)

**Purpose**: Group scored entries by category and apply per-section limits. Returns None if experience section has fewer entries than `min_experience_bullets`.
**Category**: query (pure function)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| scored | list[dict] | yes | Each dict has 'id', 'text', 'category', 'subsection', 'score' | Scored KB entries (already filtered by min_score) |
| cfg | ResumeReuseConfig or None | no | default: None | Config with min_experience_bullets (default: 6) |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | dict[str, list[dict]] or None | yes | None if experience count < min_experience_bullets. Otherwise dict keyed by category: {"experience": [...], "skill": [...], "education": [...], "certification": [...], "project": [...], "summary": [...]} |

**Section Limits** (per category, from highest score):
| Category | Max Entries | Notes |
|----------|------------|-------|
| experience | 15 | Grouped by subsection (role), top entries per role |
| skill | 20 | Flat list, highest scored first |
| education | 4 | All included up to limit |
| certification | 5 | All included up to limit |
| project | 6 | All included up to limit |
| summary | 1 | Best-scoring summary entry |

**Preconditions**: Input entries already scored and filtered.
**Postconditions**: No state change.
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (pure function).

---

### 3.22 resume_assembler._build_context() (M4)

**Purpose**: Transform user profile + selected KB entries into a structured context dict for LLM prompt construction (experience grouped by company/role, skills by category).
**Category**: query (pure function)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| profile | dict | yes | Keys: full_name, email, phone, location | User profile |
| selected | dict[str, list[dict]] | yes | Output of _select_entries() | Grouped entries by category |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | dict | no | Context dict with keys: `name` (str), `email` (str), `phone` (str), `location` (str), `summary` (str), `experiences` (list[dict] with title, company, start_date, end_date, bullets), `education` (list[dict] with institution, degree, year), `skills` (list[str]), `certifications` (list[str]), `projects` (list[dict] with name, description) |

**Transformation Rules**:
- `experience` entries grouped by subsection → each group becomes one experience block with role=subsection, bullets=entry texts
- `skill` entries → flat list of entry texts
- `education` entries → parsed into institution/degree/year from entry text
- `certification` entries → flat list of entry texts
- `project` entries → parsed into name/description from entry text
- `summary` → single best entry text, or empty string if none

**Preconditions**: selected dict has expected category keys.
**Postconditions**: No state change.
**Side Effects**: None.
**Idempotency**: Yes.
**Thread Safety**: Safe (pure function).

---

### 3.23 resume_assembler.save_assembled_resume() (M4)

**Purpose**: Save assembled PDF bytes to disk and record in resume_versions table with reuse_source="kb".
**Category**: command (filesystem + DB write)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| pdf_bytes | bytes | yes | Non-empty | PDF content |
| output_dir | Path | yes | Must exist or will be created | Directory for saved PDFs |
| company | str | yes | Non-empty | Target company name (for filename) |
| job_title | str | yes | Non-empty | Target job title (for filename) |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | Path | no | Absolute path to saved PDF file |

**Filename Convention**: `{company}_{job_title}_{YYYYMMDD_HHMMSS}.pdf` (sanitized: spaces→underscores, special chars removed)

**Preconditions**: pdf_bytes is valid PDF content.
**Postconditions**: PDF file written to output_dir.
**Side Effects**: Filesystem write; creates output_dir if missing.
**Idempotency**: No (new file each call due to timestamp).
**Thread Safety**: Safe (unique filenames via timestamp).

---

### 3.24 resume_assembler.ingest_llm_resume() (M4)

**Purpose**: After a full LLM resume generation, parse the output markdown and ingest new entries back into the KB. This grows the KB over time so future assemblies have more material.
**Category**: command (KB mutation)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| resume_md | str | yes | Non-empty markdown | LLM-generated resume in markdown format |
| kb | KnowledgeBase | yes | Must have initialized DB | Knowledge base instance |
| source_doc_id | int or None | no | default: None | Source document ID for provenance tracking |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| (return) | int | no | Count of new entries ingested (0 if all duplicates or parse failure) |

**Pipeline**:
1. Call `parse_resume_md(resume_md)` → list of entry dicts
2. Call `kb.ingest_entries(entries, source_doc_id)` → count of inserted entries
3. Return count

**Preconditions**: KB initialized; resume_md is valid markdown.
**Postconditions**: 0+ new entries in knowledge_base table.
**Side Effects**: DB inserts (deduplicated via INSERT OR IGNORE).
**Idempotency**: Yes (duplicates ignored).
**Thread Safety**: Safe (SQLite WAL + Database locking).

---

### IC-043: POST /api/config/default-resume

**Purpose**: Upload a fallback resume file (PDF or DOCX) to use when KB assembly is insufficient.
**Category**: command (filesystem + config write)

**Request**:
- Content-Type: multipart/form-data
- Body: `file` field (PDF or DOCX, max 5 MB)

**Response 200**: `{ success: true, filename: str, path: str }`
**Response 400**: `{ error: str }` — No file, empty filename, or unsupported type
**Response 413**: `{ error: str }` — File exceeds 5 MB

**Side Effects**: Saves file to `~/.autoapply/default_resume.{ext}`, updates `config.profile.fallback_resume_path` via `save_config()`.
**Idempotency**: No — overwrites previous default resume on each call.
**Thread Safety**: Safe (config write serialized via save_config).

---

### IC-044: GET /api/config/default-resume

**Purpose**: Retrieve current default resume file metadata.
**Category**: query

**Request**: None

**Response 200**: `{ filename: str | null, path: str | null }`

**Preconditions**: None.
**Postconditions**: No state change.
**Idempotency**: Yes.
**Thread Safety**: Safe (read-only).

---

### IC-045: DELETE /api/config/default-resume

**Purpose**: Remove the default resume file and clear the config reference.
**Category**: command (filesystem + config write)

**Request**: None

**Response 200**: `{ success: true }`

**Side Effects**: Deletes file from `~/.autoapply/` disk, clears `config.profile.fallback_resume_path` via `save_config()`.
**Idempotency**: Yes (no-op if no default resume set).
**Thread Safety**: Safe (config write serialized via save_config).

---

## 7.5 ADR-032: KB-First Resume Generation

**Status**: accepted
**Context**: The bot's `_generate_docs()` function currently always calls the LLM to generate a fresh resume for each job application. With the Knowledge Base (M1), scoring engine (M2), and LaTeX templates (M3) in place, the system can assemble resumes from existing KB entries without an LLM call — faster, cheaper, and deterministic.

**Decision**: Try KB assembly first; fall through to full LLM generation if KB has insufficient entries. After LLM generation, ingest the output back into the KB to grow the entry pool for future assemblies.

**Flow**:
```
_generate_docs(job, profile, llm_config)
    │
    ├──▶ _try_kb_assembly(jd_text, profile, kb, reuse_config, llm_config)
    │        │
    │        ├── assemble_resume() → score KB → select → LLM generate (strict prompt) → ReportLab render
    │        │     returns dict with pdf_bytes, resume_md, entry_ids, scoring_method → use KB-assembled PDF ✓
    │        │     save_assembled_resume()
    │        │     record resume_version with reuse_source="kb"
    │        │
    │        └── assemble_resume() returns None → insufficient KB entries or AI unavailable
    │
    └──▶ (fallback) Full LLM generation via invoke_llm()
              │
              └── _ingest_llm_output(resume_md, kb)
                    ingest_llm_resume() → grow KB for next time
                    record resume_version with reuse_source=null
```

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| Always LLM | Best quality each time | Expensive ($0.05-0.20/resume), slow (3-8s), requires API key |
| Always KB | Cheapest, fastest | Quality limited to existing entries; new roles not covered |
| **KB-first with LLM fallback + ingestion** | **Fast when KB is rich; self-improving; graceful degradation** | **Two code paths; KB quality depends on ingested content** |

**Consequences**:
- Positive: Zero-cost resume generation once KB is rich enough; self-improving loop (LLM outputs feed KB); falls back gracefully when KB is sparse
- Negative: First few applications always use LLM (cold KB); assembled resumes may lack the creative phrasing of LLM-generated ones
- Risks: KB pollution from low-quality LLM outputs → mitigated by dedup on (category, text) and min_score threshold filtering during assembly

---

## 8. Design Traceability Matrix (continued — M4)

| Requirement | Type | Design Component(s) | Interface(s) | ADR |
|-------------|------|---------------------|---------------|-----|
| FR-030-26 | FR | ResumeAssembler, AI Engine, ResumeRenderer | assemble_resume() → generate_resume_from_kb() → render_resume_to_pdf() | ADR-032 |
| FR-030-27 | FR | ResumeAssembler | _select_entries() | — |
| FR-030-28 | FR | ResumeAssembler | _build_context(), _format_kb_data_for_prompt() | — |
| FR-030-29 | FR | DashboardToggles, Bot | `static/js/settings.js`, `templates/index.html`, `bot/bot.py` — initBotToggles(), _generate_docs() toggle checks | ADR-032 |
| FR-030-30 | FR | DefaultResumeManager | `routes/config.py` — POST/GET/DELETE /api/config/default-resume | IC-043, IC-044, IC-045 |
| FR-030-31 | FR | DashboardToggles, Config UI | `templates/index.html`, `static/js/settings.js`, `static/css/main.css` — toggle controls, styling | — |
| FR-030-32 | FR | KB Viewer, Resume Preview | `templates/index.html`, `static/js/knowledge-base.js`, `static/js/resume-preview.js` — KB screen + preview | — |
| NFR-030-14 | NFR | ResumeAssembler | logging.getLogger(__name__) | — |
| NFR-030-15 | NFR | Test suite (M4) | pytest | — |

---

### M4 Implementation Tasks

| Order | Task ID | Description | Depends On | Size | Risk | FR Coverage |
|-------|---------|------------|------------|------|------|-------------|
| 15 | IMPL-015 | Resume assembler module (LLM + ReportLab) | IMPL-006, IMPL-010 | L | Medium | FR-030-26, FR-030-27, FR-030-28, FR-030-29, FR-030-30 |
| 16 | IMPL-016 | Bot KB-first flow | IMPL-015 | M | Medium | FR-030-31 |
| 17 | IMPL-017 | DB resume_versions extension | IMPL-001 | S | Low | FR-030-32 |

#### IMPL-015: Resume Assembler Module
- **Creates**: `core/resume_assembler.py`
- **Contains**: `assemble_resume()`, `_select_entries()`, `_build_context()`, `_format_kb_data_for_prompt()`, `save_assembled_resume()`, `ingest_llm_resume()`
- **Dependencies**: `core/knowledge_base.py` (M1), `core/resume_scorer.py` (M2), `core/ai_engine.py` (`generate_resume_from_kb`, `check_ai_available`), `core/resume_renderer.py` (`render_resume_to_pdf` — ReportLab), `core/resume_parser.py` (M1)
- **Pipeline**: score → select → build context → LLM generate (strict KB-only prompt) → ReportLab render → return
- **Section limits**: experience(15), skill(20), education(4), certification(5), project(6), summary(1)
- **LLM prompt constraints**: exactly 1 page, min 2 bullets per role, allows rephrasing/synonyms from JD, strict "only use provided data"
- **Tests**: `tests/test_resume_assembler.py` — assembly pipeline (mocked KB + scorer + LLM), entry selection (min_experience guard, section limits, grouping), context building (all section types), save (filename sanitization, dir creation), LLM ingestion (dedup, empty input)
- **Done when**: All 5 interface contracts (§3.20-§3.24) satisfied; selection enforces min_experience_bullets; context suitable for LLM prompt; save produces valid filenames; ingest_llm_resume grows KB

#### IMPL-016: Bot KB-First Flow
- **Modifies**: `bot/bot.py` — `_generate_docs()` method
- **Adds**: `_try_kb_assembly(jd_text, profile, kb, reuse_config, llm_config)` — calls `assemble_resume()`, saves PDF, returns result or None
- **Adds**: `_ingest_llm_output(resume_md, kb)` — calls `ingest_llm_resume()` after LLM fallback generation
- **Flow**: `_generate_docs()` calls `_try_kb_assembly()` first; if None, falls through to existing LLM path; after LLM path, calls `_ingest_llm_output()` to grow KB
- **Config gate**: Only attempts KB assembly if `reuse_config.enabled` is True (default: True)
- **Logging**: INFO log when KB assembly succeeds ("Assembled resume from KB: {n} entries, {method} scoring"); INFO when falling back to LLM ("KB insufficient, falling back to LLM generation")
- **Tests**: `tests/test_bot_kb_flow.py` — KB assembly success path (mocked assembler), KB insufficient fallback to LLM, LLM output ingestion, reuse disabled config, error handling
- **Done when**: Bot tries KB first; falls back to LLM when KB insufficient; ingests LLM output; respects enabled flag; all paths logged

#### IMPL-017: DB resume_versions Extension
- **Modifies**: `db/database.py` — `save_resume_version()` method and SCHEMA_SQL
- **Adds columns**: `reuse_source TEXT` (nullable, "kb" or null), `source_entry_ids TEXT` (nullable, JSON array of int)
- **Migration**: ALTER TABLE ADD COLUMN for existing DBs (both columns nullable, no default needed)
- **Backward compat**: Existing callers of `save_resume_version()` continue to work (new params optional with default None)
- **Tests**: Covered by existing `test_resume_versions.py` + new tests for reuse_source/source_entry_ids columns
- **Done when**: New columns present in schema; migration handles existing DBs; save_resume_version accepts optional reuse_source and source_entry_ids; query returns new fields

---

## 9. Design — M5: Upload UI + KB Viewer + Preview

### §3.25 Component: KB Routes Blueprint (`routes/knowledge_base.py`)

**Responsibility**: Flask Blueprint providing 8 REST API endpoints for KB management.

**Endpoints**:
| Method | Path | Purpose | FR |
|--------|------|---------|-----|
| POST | /api/kb/upload | Upload document, extract entries | FR-030-33 |
| GET | /api/kb/stats | Entry counts by category | FR-030-34 |
| GET | /api/kb | List entries with filter/search/pagination | FR-030-35 |
| GET | /api/kb/<id> | Get single entry | FR-030-36 |
| PUT | /api/kb/<id> | Update entry text/subsection/tags | FR-030-36 |
| DELETE | /api/kb/<id> | Soft-delete entry | FR-030-36 |
| GET | /api/kb/documents | List uploaded documents | FR-030-37 |
| POST | /api/kb/preview | Preview assembled resume as PDF | FR-030-41 |

**Dependencies**: `app_state.db`, `core.i18n.t()`, `core.knowledge_base.KnowledgeBase`, `core.resume_assembler`, `core.resume_scorer`, `core.ai_engine`, `core.resume_renderer`.

### §3.26 Component: KB Frontend Module (`static/js/knowledge-base.js`)

**Responsibility**: ES module for KB viewer UI — stats display, entries table, category filter, search, pagination, upload, edit/delete overlays.

**Exports**: `loadKnowledgeBase`, `loadKBEntries`, `uploadKBDocument`, `editKBEntry`, `saveKBEntry`, `closeKBEdit`, `deleteKBEntry`, `filterKBCategory`, `searchKB`, `switchKBPage`, `loadKBDocuments`, `initKnowledgeBase`.

**Pattern**: Uses `fetch()` (auto-patched by auth.js), `escHtml()`/`escAttr()` for XSS prevention, `t()`/`_applyDataI18n()` for i18n, event delegation for dynamic buttons.

### §3.27 Component: Resume Preview Module (`static/js/resume-preview.js`)

**Responsibility**: ES module for previewing assembled resumes — template picker, JD textarea, PDF display in iframe.

**Exports**: `previewKBResume`, `closeKBPreview`, `initResumePreview`.

### §3.28 ADR-033: KB Blueprint Registration Pattern

**Context**: KB routes need to integrate with existing Flask app.
**Decision**: Register `kb_bp` Blueprint in `create_app()` alongside existing 8 blueprints. Auth, rate limiting, security headers, error handlers applied via existing middleware.
**Rationale**: Consistent with existing architecture. No special middleware needed.

### §3.29 Interface Contracts — M5

#### IC-025: Upload API
```
POST /api/kb/upload
Content-Type: multipart/form-data
Body: file=<binary>
Response 201: { success: true, entries_created: int, message: str }
Response 400: { description: str }  (no file / bad type)
Response 413: { description: str }  (file > 10 MB)
```

#### IC-026: KB List API
```
GET /api/kb?category=&search=&limit=100&offset=0
Response 200: { entries: [{id, category, text, subsection, tags, ...}], count: int }
```

#### IC-027: KB Preview API
```
POST /api/kb/preview
Content-Type: application/json
Body: { template: str, entry_ids?: int[], jd_text?: str }
Response 200: application/pdf (binary)
Response 400: { description: str }
```

### §3.30 Implementation Tasks — M5

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-018 | KB Routes Blueprint | M1 DB methods | `routes/knowledge_base.py` |
| IMPL-019 | Blueprint Registration | IMPL-018 | `app.py` |
| IMPL-020 | KB Frontend Module | IMPL-018 | `static/js/knowledge-base.js` |
| IMPL-021 | Resume Preview Module | IMPL-018 | `static/js/resume-preview.js` |
| IMPL-022 | HTML Screen + Nav Tab | IMPL-020, IMPL-021 | `templates/index.html` |
| IMPL-023 | App.js Integration | IMPL-020, IMPL-021 | `static/js/app.js`, `static/js/navigation.js` |
| IMPL-024 | i18n Keys | IMPL-022 | `static/locales/en.json`, `static/locales/es.json` |
| IMPL-025 | Route Tests | IMPL-018 | `tests/test_knowledge_base_routes.py` |

---

## 10. Design — M6: ATS Scoring + Platform Profiles + Gap Analysis

### §3.31 Component: ATSScorer (`core/ats_scorer.py`)

**Purpose**: Composite ATS compatibility scoring with 5 weighted components.

**Internal Functions**:
- `_tokenize(text)` → list[str] — Normalize text into searchable terms
- `_score_keyword_match(jd_keywords, resume_terms)` → (float, list, list) — Keyword overlap score
- `_score_section_completeness(categories_present)` → float — Required/optional section presence
- `_score_skill_match(jd_tech, resume_terms)` → (float, list, list) — Technical skill alignment
- `_score_content_length(entries)` → float — Word count against ideal range (300–800)
- `_score_format_compliance(entries, categories_present)` → float — ATS-friendly formatting checks

**Public API**:
- `score_ats(jd_text, entries, weights=None)` → dict — Composite score 0–100 with gap analysis
- `_empty_result()` → dict — Zeroed result for empty inputs

**Dependencies**: `core.jd_analyzer.analyze_jd`, `core.jd_analyzer.normalize_term`

### §3.32 Component: ATSProfiles (`core/ats_profiles.py`)

**Purpose**: Vendor-specific ATS scoring weight profiles.

**Data**: `ATS_PROFILES` dict with 7 profiles: default, greenhouse, lever, workday, ashby, icims, taleo.

**Public API**:
- `get_profile(platform)` → dict — Profile with name, description, weights (falls back to default)
- `get_weights(platform)` → dict[str, float] — Weight dict summing to 1.0
- `list_profiles()` → list[dict] — All profiles as [{id, name, description}]

### §3.33 Component: ATS Frontend (`static/js/knowledge-base.js` additions)

**Purpose**: ATS scoring UI card in KB screen.

**Functions added**:
- `analyzeATS()` — Fetches `/api/kb/ats-score`, renders results
- `renderATSResult(data, el)` — Score badge (color-coded), component progress bars, gap badges

### Interface Contracts — M6

#### IC-028: `POST /api/kb/ats-score`

**Request**: `{ jd_text: string, platform?: string, entry_ids?: int[] }`
**Response 200**: `{ score: int, platform: string, components: {name: {score, weight, weighted}}, matched_keywords: [], missing_keywords: [], matched_skills: [], missing_skills: [], categories_present: [], categories_missing: [], entry_count: int, word_count: int }`
**Response 400**: `{ error: string }` — Missing jd_text or empty KB

#### IC-029: `GET /api/kb/ats-profiles`

**Response 200**: `{ profiles: [{id, name, description}] }`

### §3.34 Implementation Tasks — M6

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-026 | ATS Scorer Module | M2 jd_analyzer | `core/ats_scorer.py` |
| IMPL-027 | ATS Profiles Module | IMPL-026 | `core/ats_profiles.py` |
| IMPL-028 | ATS Endpoints + Frontend | IMPL-026, IMPL-027, M5 KB routes | `routes/knowledge_base.py`, `static/js/knowledge-base.js`, `templates/index.html`, `static/locales/en.json`, `static/locales/es.json` |

---

## 11. Design — M7: Manual Resume Builder

### §3.35 Component: Preset CRUD (`db/database.py` + `routes/knowledge_base.py`)

**Purpose**: Store and manage named resume entry combinations.

**Database Table**: `resume_presets` (id, name, entry_ids JSON, template, created_at, updated_at)

**DB Methods**: `save_preset()`, `get_presets()`, `get_preset()`, `update_preset()`, `delete_preset()`

**Endpoints**:
- `GET /api/kb/presets` → list all presets
- `POST /api/kb/presets` → create preset (name, entry_ids, template)
- `PUT /api/kb/presets/<id>` → update preset
- `DELETE /api/kb/presets/<id>` → delete preset

### §3.36 Component: Resume Builder Frontend (`static/js/resume-builder.js`)

**Purpose**: Drag-and-drop resume building UI with presets and one-page estimation.

**Key Functions**:
- `openResumeBuilder()` / `closeResumeBuilder()` — overlay lifecycle
- `addToResume(entryId)` / `removeFromResume(section, index)` — entry management
- `moveEntryUp()` / `moveEntryDown()` — reorder within section
- `estimateLines()` / `updatePageIndicator()` — one-page mode
- `savePreset()` / `loadPreset()` / `deletePreset()` — preset management
- `previewBuilderResume()` — PDF preview via existing `/api/kb/preview`
- `autoFillFromJD()` — keyword-based auto-selection via ATS scoring

### Interface Contracts — M7

#### IC-030: `GET /api/kb/presets`
**Response 200**: `{ presets: [{id, name, entry_ids, template, created_at, updated_at}] }`

#### IC-031: `POST /api/kb/presets`
**Request**: `{ name: string, entry_ids: int[], template?: string }`
**Response 201**: `{id, name, entry_ids, template, created_at}`
**Response 400**: Missing name or invalid entry_ids

#### IC-032: `PUT /api/kb/presets/<id>`
**Request**: `{ name?: string, entry_ids?: int[], template?: string }`
**Response 200**: `{ success: true }`
**Response 404**: Preset not found

### §3.37 Implementation Tasks — M7

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-029 | Presets DB Schema + Methods | M1 DB | `db/database.py` |
| IMPL-030 | Preset API Endpoints | IMPL-029 | `routes/knowledge_base.py` |
| IMPL-031 | Resume Builder Frontend | IMPL-030, M5 KB module | `static/js/resume-builder.js`, `static/js/app.js` |
| IMPL-032 | Builder HTML + CSS | IMPL-031 | `templates/index.html`, `static/css/main.css` |
| IMPL-033 | i18n Keys | IMPL-032 | `static/locales/en.json`, `static/locales/es.json` |
| IMPL-034 | Preset Tests | IMPL-029, IMPL-030 | `tests/test_resume_builder.py` |

---

### §3.38 PDF Compilation Cache (M8)

**Module**: `core/pdf_cache.py`
**Purpose**: Content-hash LRU cache to avoid redundant pdflatex compilations.

**Data Flow**:
```
compile_latex(tex) → content_hash(tex) → SHA256[:16] → cache_dir/{hash}.pdf
  ├─ HIT  → return cached bytes, touch file (LRU update)
  └─ MISS → compile → store result → return bytes
```

**Key Functions**:
- `content_hash(tex_content: str) → str` — SHA256[:16] of LaTeX content
- `get_cached(tex_content: str) → bytes | None` — cache lookup
- `store(tex_content: str, pdf_bytes: bytes) → None` — cache write
- `evict_lru() → int` — remove oldest when > MAX_CACHE_SIZE (200)
- `clear_cache() → int` — remove all cached PDFs
- `cache_stats() → dict` — count, size_bytes, size_mb, max_size, cache_dir

**Cache Directory**: `~/.autoapply/cache/pdf/`

**Integration**: `core/latex_compiler.py:compile_latex()` checks cache before compilation, stores result after compilation. Controlled by `use_cache` parameter (default True).

### §3.39 JD Classifier (M8)

**Module**: `core/jd_classifier.py`
**Purpose**: Lightweight keyword-based job type detection for pre-filtering KB entries before scoring.

**Job Types** (9): backend, frontend, fullstack, data_engineer, data_scientist, ml_engineer, devops, mobile, security

**Algorithm**: Case-insensitive substring matching against keyword dictionaries. Scores = count of matching keywords per type. Returns types sorted by score descending. Falls back to ["general"] when no matches.

**Key Functions**:
- `classify_jd(jd_text: str) → list[str]` — classify JD into job types
- `get_relevant_types(primary_types: list[str]) → list[str]` — expand with related types
- `filter_entries_by_type(entries, job_types, min_entries=5) → list[dict]` — filter KB entries, fallback to all if < min_entries match

**Data Structures**:
- `JOB_TYPE_KEYWORDS: dict[str, set[str]]` — keyword sets per job type
- `RELATED_TYPES: dict[str, list[str]]` — related type mappings

### §3.40 Async Document Upload (M8)

**Module**: `routes/knowledge_base.py` (additions)
**Purpose**: Non-blocking document upload with background processing and status polling.

**Architecture**:
```
POST /api/kb/upload/async → validate file → save to temp → spawn daemon thread → return 202 {task_id}
                                                              ↓
                                           _run_upload_async(task_id, tmp_path, ...)
                                                              ↓
                                           KnowledgeBase.process_upload() → update _upload_tasks[task_id]

GET /api/kb/upload/status/<task_id> → read _upload_tasks[task_id] → return status
```

**Thread Safety**: `_upload_tasks: dict[str, dict]` protected by `_upload_lock: threading.Lock`

**Task States**: `processing` → `completed` | `failed`

### Interface Contracts — M8

#### IC-033: `POST /api/kb/upload/async`
**Request**: multipart/form-data with `file` field (PDF/DOCX/TXT/MD, max 10MB)
**Response 202**: `{ task_id: string, status: "processing" }`
**Response 400**: No file, empty filename, or unsupported type
**Response 413**: File exceeds 10MB

#### IC-034: `GET /api/kb/upload/status/<task_id>`
**Response 200**: `{ task_id, status, filename, entries_created, error, message }`
**Response 404**: Unknown task_id

### §3.41 Implementation Tasks — M8

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-035 | PDF Cache Module | — | `core/pdf_cache.py` |
| IMPL-036 | LaTeX Compiler Cache Integration | IMPL-035, M3 | `core/latex_compiler.py` |
| IMPL-037 | JD Classifier Module | — | `core/jd_classifier.py` |
| IMPL-038 | Async Upload Endpoints | M5 Upload | `routes/knowledge_base.py` |
| IMPL-039 | M8 Tests | IMPL-035–038 | `tests/test_performance.py` |

---

### §3.42 Outcome-Based Learning (M9)

**Module**: `db/database.py` (additions)
**Purpose**: Track KB entry usage and outcome feedback to compute effectiveness scores.

**Schema Additions**:
```sql
-- New table
CREATE TABLE kb_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES knowledge_base(id),
    application_id INTEGER REFERENCES applications(id),
    tfidf_score REAL,
    outcome TEXT,  -- "interview", "rejected", "no_response"
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- New columns on knowledge_base (via migration)
ALTER TABLE knowledge_base ADD COLUMN effectiveness_score REAL DEFAULT 0.0;
ALTER TABLE knowledge_base ADD COLUMN usage_count INTEGER DEFAULT 0;
ALTER TABLE knowledge_base ADD COLUMN last_used_at DATETIME;
```

**Key Methods**:
- `log_kb_usage(entry_ids, application_id, scores)` → int — log usage, increment counters
- `update_kb_outcome(application_id, outcome)` → int — update outcomes, recalculate effectiveness
- `get_kb_effectiveness(limit)` → list[dict] — entries ranked by effectiveness_score
- `get_reuse_stats()` → dict — aggregate KB assembly metrics

**Effectiveness Formula**: `effectiveness_score = interviews / total_uses_with_outcome`

### §3.43 Cover Letter KB Assembly (M9)

**Module**: `core/cover_letter_assembler.py`
**Purpose**: Generate cover letters from KB entries without LLM API calls.

**Pipeline**:
1. Fetch all active KB entries
2. Score against JD using existing TF-IDF scorer
3. Select top experience (3) and skill (4) entries
4. Compose template-based cover letter with greeting, intro, body paragraphs, closing

**Key Function**: `assemble_cover_letter(jd_text, profile, kb, job_title, company, reuse_config) → str | None`

### §3.44 Intelligence Integration (M9)

**Modifications**:
- `core/resume_assembler.py`: Pre-filters KB entries using `classify_jd()` + `filter_entries_by_type()` before scoring
- `core/resume_scorer.py`: Blends effectiveness_score into TF-IDF: `final = (tfidf × 0.7) + (effectiveness × 0.3)` when effectiveness > 0
- `routes/analytics.py`: New `GET /api/analytics/reuse-stats` endpoint

### Interface Contracts — M9

#### IC-035: `POST /api/kb/feedback`
**Request**: `{ application_id: int, outcome: "interview" | "rejected" | "no_response" }`
**Response 200**: `{ success: true, updated: int }`
**Response 400**: Missing/invalid application_id or outcome

#### IC-036: `GET /api/kb/effectiveness`
**Response 200**: `[{id, category, text, subsection, effectiveness_score, usage_count, last_used_at}]`

#### IC-037: `GET /api/analytics/reuse-stats`
**Response 200**: `{total_assemblies, total_entries_used, unique_entries_used, interviews_from_kb, avg_effectiveness, top_categories}`

### §3.45 Implementation Tasks — M9

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-040 | kb_usage_log Table + Migration | M1 DB | `db/database.py` |
| IMPL-041 | Usage Log + Outcome DB Methods | IMPL-040 | `db/database.py` |
| IMPL-042 | Cover Letter Assembler | M2 Scorer | `core/cover_letter_assembler.py` |
| IMPL-043 | JD Classifier Integration | M8 Classifier | `core/resume_assembler.py` |
| IMPL-044 | Effectiveness Weighting | IMPL-041 | `core/resume_scorer.py` |
| IMPL-045 | Feedback + Effectiveness Endpoints | IMPL-041 | `routes/knowledge_base.py` |
| IMPL-046 | Reuse Stats Endpoint | IMPL-041 | `routes/analytics.py` |
| IMPL-047 | M9 Tests | IMPL-040–046 | `tests/test_intelligence.py` |

---

### §3.46 KB Migrator (M10)

**Module**: `core/kb_migrator.py`
**Purpose**: Auto-migrate legacy `.txt` experience files and `.md` resumes into KB entries on first startup.

**Components**:
- `needs_migration(data_dir)` → bool — checks for `.kb_migrated` marker file
- `mark_migrated(data_dir)` → None — writes marker file
- `migrate_experience_files(experience_dir, kb)` → int — parses .txt line-by-line
- `migrate_resume_files(resumes_dir, kb)` → int — uses `parse_resume_md`, tags as "migrated"
- `run_migration(data_dir, kb)` → dict — full pipeline (check → migrate → mark)
- `_parse_txt_to_entries(content, filename)` → list[dict] — splits lines, strips bullets, skips <5 chars
- `_guess_category(text)` → str — keyword heuristics for skill/education/certification/experience

**Pipeline**:
```
run_migration(data_dir, kb)
    ├── needs_migration? → False → return {migrated: false, skipped_reason: "already_migrated"}
    ├── migrate_experience_files(data_dir/profile/experiences, kb)
    │     ├── glob *.txt (skip README.txt)
    │     ├── _parse_txt_to_entries() per file
    │     └── kb.ingest_entries() per file
    ├── migrate_resume_files(data_dir/resumes, kb)
    │     ├── glob *.md
    │     ├── parse_resume_md() per file
    │     ├── tag entries with "migrated"
    │     └── kb.ingest_entries() per file
    └── mark_migrated(data_dir) → always, even if 0 entries
```

### §3.47 LaTeX Escaping Hardening (M10)

**Module**: `core/latex_compiler.py` (modification)
**Purpose**: Fix backslash escaping to prevent double-escaping of braces.

**Technique**: Placeholder-based escaping
1. Replace `\` with `\x00BACKSLASH\x00` (null-byte delimited placeholder)
2. Run regex escaping for 9 special chars (`& % $ # _ { } ~ ^`)
3. Replace placeholder with `\textbackslash{}`

This prevents the `{` and `}` in `\textbackslash{}` from being re-escaped by the regex pass.

### §3.48 Implementation Tasks — M10

| Task | Name | Depends On | Files |
|------|------|------------|-------|
| IMPL-048 | KB Migrator Module | M1 KB, M1 ResumeParser | `core/kb_migrator.py` |
| IMPL-049 | LaTeX Backslash Escaping | M3 LaTeX | `core/latex_compiler.py` |
| IMPL-050 | M10 Tests | IMPL-048, IMPL-049 | `tests/test_migration.py` |

---

## System Architecture -- GATE 4 OUTPUT

**Document**: SAD-TASK-030-smart-resume-reuse
**Components**: 32 components defined (7 M1 + 2 M2 + 3 M3 + 3 M4 + 4 M5 + 2 M6 + 2 M7 + 3 M8 + 4 M9 + 2 M10)
**Interfaces**: 37 contracts specified (10 M1 + 4 M2 + 5 M3 + 5 M4 + 3 M5 + 2 M6 + 3 M7 + 2 M8 + 3 M9 + 0 M10)
**Entities**: 6 data entities modeled (5 new tables + 1 modified with 5 new columns)
**ADRs**: 7 decisions documented (ADR-027 to ADR-033)
**Impl Tasks**: 50 tasks in dependency order (8 M1 + 3 M2 + 3 M3 + 3 M4 + 8 M5 + 3 M6 + 6 M7 + 5 M8 + 8 M9 + 3 M10)
**Traceability**: 104/104 requirements mapped (100%)
**Checklist**: 50/50 items passed

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| Backend Developer | Interface contracts, data model, impl plan |
| Unit Tester | Interface contracts for test generation |
| Integration Tester | API contracts, integration points |
