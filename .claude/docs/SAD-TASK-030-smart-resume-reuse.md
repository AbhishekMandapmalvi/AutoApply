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

**Completeness**: 12/12 FRs mapped, 6/6 NFRs mapped. Zero gaps.

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

#### IMPL-008: Unit Tests
- **Creates**: 6 test files, 89+ tests
- **Done when**: All tests pass; ruff clean; coverage > 80% on new modules

---

## System Architecture -- GATE 4 OUTPUT

**Document**: SAD-TASK-030-smart-resume-reuse
**Components**: 7 components defined
**Interfaces**: 10 contracts specified
**Entities**: 4 data entities modeled (3 new tables + 1 modified)
**ADRs**: 2 decisions documented (ADR-027, ADR-028)
**Impl Tasks**: 8 tasks in dependency order
**Traceability**: 18/18 requirements mapped (100%)
**Checklist**: 20/20 items passed

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| Backend Developer | Interface contracts, data model, impl plan |
| Unit Tester | Interface contracts for test generation |
| Integration Tester | API contracts, integration points |
